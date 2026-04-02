import logging
from datetime import datetime
import numpy as np

from utils.logger import log
from utils.time_utils import _t0, _dt, days_since
from utils.notifications import (
    discord_error,
    discord_no_trade,
    discord_portfolio_summary,
)

from config import TOP_ML_COUNT, TOP_BUY_PICKS, MIN_PREDICTED_RETURN, MIN_PREDICTED_RETURN_BUY, INDUSTRY_CAP_US, INDUSTRY_CAP_IN
from db.account import get_account, update_cash
from db.portfolio import get_portfolio
from db.performance import log_performance

from data.fetch import fetch_sp500_tickers, fetch_nifty500_tickers, bulk_download_by_ticker
from data.features import prepare_ml_dataframe
from models.train import train_and_score

from strategy.ranking import get_market_regime, normalize_scores, rank_candidates
from strategy.risk import calculate_industry_exposures, check_industry_cap
from execution.trading import run_sell_phase, run_buy_phase
from utils.currency import get_conversion_rates, normalize_to_usd, get_currency


def main():
    RUN_T0 = _t0()
    log.info("========== BOT RUN START %s ==========", datetime.now().isoformat())

    # Get conversion rates once for the run
    inr_to_usd, usd_to_inr = get_conversion_rates()

    try:
        # Initial State (Separate Cash)
        account = get_account()
        cash_usd = float(account.get("cash_usd", 0.0))
        cash_inr = float(account.get("cash_inr", 0.0))
        
        portfolio = get_portfolio()
        positions = {p["ticker"]: p for p in portfolio}
        market_regime_bullish = get_market_regime()

        log.info("Startup: cash_usd=%.2f, cash_inr=%.2f, positions=%d total", 
                 cash_usd, cash_inr, len(positions))

        # Data Fetching (Both Markets)
        tickers_us = fetch_sp500_tickers()
        tickers_in = fetch_nifty500_tickers()
        all_market_tickers = tickers_us + tickers_in
        
        filter_map = bulk_download_by_ticker(all_market_tickers, "6mo")

        # Momentum Filter (Split by Market to prevent starving)
        US_PER_MARKET = TOP_ML_COUNT // 2
        
        mom_us = []
        mom_in = []
        
        for t, df in filter_map.items():
            if len(df) < 50:
                continue
            px = df["Close"].astype(float)
            mom = float(px.iloc[-1] / px.iloc[-21] - 1.0)
            if mom > 0:
                if t.endswith(".NS"):
                    mom_in.append((t, mom))
                else:
                    mom_us.append((t, mom))

        mom_us.sort(key=lambda x: -x[1])
        mom_in.sort(key=lambda x: -x[1])
        
        top_us = [t for t, _ in mom_us[:US_PER_MARKET]]
        top_in = [t for t, _ in mom_in[:US_PER_MARKET]]
        
        log.info("Momentum Filter: US=%d/%d, INDIA=%d/%d", 
                 len(top_us), len(mom_us), len(top_in), len(mom_in))
        
        top_tickers = list(set(top_us + top_in))

        # ML Scoring
        scores, vol_map, prices = {}, {}, {}
        ml_list = list(set(top_tickers + list(positions.keys())))
        ohlcv_1y = bulk_download_by_ticker(ml_list, "1y")

        for ticker, df in ohlcv_1y.items():
            ml_df = prepare_ml_dataframe(df, ticker=ticker)
            if not ml_df.empty:
                pred, vol = train_and_score(ml_df, ticker=ticker)
                scores[ticker] = pred
                vol_map[ticker] = vol
                prices[ticker] = float(df["Close"].dropna().iloc[-1])

        if not scores:
            log.warning("No ML scores generated. Skipping trade cycle.")
            return

        # Print top 5 Indian predictions separately for debug
        india_scores = {t: s for t, s in scores.items() if t.endswith(".NS")}
        if india_scores:
            top_5_in = sorted(india_scores.items(), key=lambda x: -x[1])[:5]
            log.info("Top 5 INDIA Predictions: %s", top_5_in)

        # Normalization and Ranking
        z_scores = normalize_scores(scores)
        ranked_candidates = rank_candidates(z_scores)

        # 1. SEPARATE SELL PHASES
        proceeds_generated = False
        
        # US SELLS (Only US tickers, impact US cash)
        us_positions = {t: p for t, p in positions.items() if not t.endswith(".NS")}
        if us_positions:
            new_cash_usd = run_sell_phase_local(us_positions, prices, scores, cash_usd, "USD", vol_map=vol_map)
            if new_cash_usd > cash_usd: proceeds_generated = True
            cash_usd = new_cash_usd
        
        # IN SELLS (Only Indian tickers, impact Indian cash)
        in_positions = {t: p for t, p in positions.items() if t.endswith(".NS")}
        if in_positions:
            new_cash_inr = run_sell_phase_local(in_positions, prices, scores, cash_inr, "INR", vol_map=vol_map)
            if new_cash_inr > cash_inr: proceeds_generated = True
            cash_inr = new_cash_inr

        # Refresh state for Buy phase
        portfolio = get_portfolio()
        positions = {p["ticker"]: p for p in portfolio}

        # 2. SEPARATE BUY PHASES
        def get_best_candidates(market_type: str, owned_tickers: list):
            # market_type: "USD" or "INR"
            is_in = (market_type == "INR")
            market_cands = []
            
            scanned_count = 0
            for t in scores.keys():
                is_ticker_in = t.endswith(".NS")
                if is_ticker_in == is_in:
                    scanned_count += 1
                    if t not in owned_tickers:
                        pred = float(scores[t])
                        vol = float(vol_map.get(t, 0.02))
                        score = pred / (1 + vol)
                        market_cands.append((t, score))
            
            # Sort by risk-adjusted score
            market_cands.sort(key=lambda x: -x[1])
            
            # Select TOP 15
            final_selection = market_cands[:15]
            
            log.info("[%s Selection] Scanned: %d | Eligible: %d | Selected: %d", 
                     market_type, scanned_count, len(market_cands), len(final_selection))
            return final_selection

        top_picks_combined = []
        def is_recent_buy(p): return days_since(p["buy_date"]) < 3
        owned = list(positions.keys())
        
        # A. US BUYS
        recent_buys_us = [p for t, p in positions.items() if not t.endswith(".NS") and is_recent_buy(p)]
        if recent_buys_us:
            log.info("Skipping US BUY (Rule 4): Recent activity")
        elif not market_regime_bullish:
            log.info("US BUY disabled: BEARISH SPY")
        else:
            candidates_us = get_best_candidates("USD", owned)
            if candidates_us:
                cash_usd = run_buy_phase_local(
                    candidates_us,
                    prices,
                    scores,
                    cash_usd,
                    portfolio,
                    "USD",
                    other_cash=cash_inr,
                    vol_map=vol_map,
                )
                top_picks_combined.extend(candidates_us)

        # B. IN BUYS
        candidates_in = get_best_candidates("INR", owned)
        if candidates_in:
            cash_inr = run_buy_phase_local(
                candidates_in,
                prices,
                scores,
                cash_inr,
                portfolio,
                "INR",
                other_cash=cash_usd,
                vol_map=vol_map,
            )
            top_picks_combined.extend(candidates_in)

        # Wrap up (Updated separate cash columns)
        update_cash(cash_usd, cash_inr)

        # Final reporting (Normalized calculation for final total value in USD)
        final_portfolio = get_portfolio()
        final_total_val_usd, _ = calculate_industry_exposures(
            {p["ticker"]: p for p in final_portfolio}, prices, inr_to_usd
        )
        # Total USD cash including INR normalized
        total_cash_usd = cash_usd + (cash_inr * inr_to_usd)
        final_total_val_usd += total_cash_usd

        log_performance(final_total_val_usd)

        # Unrealized P/L calculation in USD
        pl_unrealized_usd = 0.0
        for p in final_portfolio:
            px = prices.get(p["ticker"], float(p["buy_price"]))
            buy_px = float(p["buy_price"])
            sh = float(p["shares"])
            curr = p.get("currency", get_currency(p["ticker"]))
            pnl_local = (px - buy_px) * sh
            pl_unrealized_usd += normalize_to_usd(pnl_local, curr, inr_to_usd)

        discord_portfolio_summary(
            run_date=datetime.now().strftime("%Y-%m-%d"),
            cash_usd=cash_usd,
            cash_inr=cash_inr,
            pl_unrealized_usd=pl_unrealized_usd,
            top_picks=[(t, scores[t]) for t, _ in top_picks_combined[:10]],
            positions={p["ticker"]: p for p in final_portfolio},
            prices=prices,
        )

    except Exception as e:
        log.exception("Fatal error in main orchestration loop.")
        try: discord_error(str(e))
        except: pass

    log.info("========== BOT RUN END wall_ms=%.2f ==========", _dt(RUN_T0))

def run_sell_phase_local(positions, prices, scores, cash, currency_filter, vol_map=None):
    """Helper to run sell phase and return local currency cash."""
    from execution.trading import get_strategy
    log.info("---------- SELL PHASE (%s) ----------", currency_filter)
    for t, pos in list(positions.items()):
        px = prices.get(t)
        if px is None: continue
        strategy = get_strategy(t)
        vol = vol_map.get(t, 0.02) if vol_map else 0.02
        res, proceeds = strategy.handle_sell(t, pos, px, scores.get(t), volatility=vol)
        if res:
            cash += proceeds
            log.info("Execution (%s): Sold %s @ %.2f -> Proceeds: %.2f", currency_filter, t, px, proceeds)
    return cash

def run_buy_phase_local(top_picks, prices, scores, cash, portfolio, currency, other_cash=0.0, vol_map=None):
    """Helper to run buy phase with local currency cash."""
    from execution.trading import run_buy_phase
    return run_buy_phase(
        top_picks,
        prices,
        scores,
        cash,
        portfolio,
        base_currency=currency,
        other_cash=other_cash,
        vol_map=vol_map,
    )


if __name__ == "__main__":
    main()
