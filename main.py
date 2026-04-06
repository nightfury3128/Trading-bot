import logging
from datetime import datetime, time as dtime
import numpy as np
import pytz

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

from data.fetch import fetch_sp500_tickers, fetch_nifty500_tickers, bulk_download_by_ticker, fetch_intraday_ohlcv
from data.features import prepare_ml_dataframe
from models.train import train_and_score

from strategy.ranking import get_market_regime, normalize_scores, rank_candidates
from strategy.risk import calculate_industry_exposures, check_industry_cap
from execution.trading import run_sell_phase, run_buy_phase
from utils.currency import get_conversion_rates, normalize_to_usd, get_currency
from utils.market_hours import is_market_open
import strategy.intraday_india as intraday_india

def is_close_to(target_dt, now, tolerance_minutes=30):
    """Return True if *now* is within ±tolerance_minutes of *target_dt* (both naive, same tz)."""
    from datetime import timedelta
    delta = abs((now - target_dt).total_seconds())
    return delta <= tolerance_minutes * 60


def should_run_now():
    """Return (should_run, window_label) based on US/India schedule windows."""
    utc_now = datetime.now(pytz.utc)

    ny_tz = pytz.timezone("America/New_York")
    ist_tz = pytz.timezone("Asia/Kolkata")

    now_ny = utc_now.astimezone(ny_tz)
    now_ist = utc_now.astimezone(ist_tz)

    # US (New York) schedule times
    us_windows = [
        (dtime(9, 30), "US 9:30 AM ET"),
        (dtime(15, 0), "US 3:00 PM ET"),
    ]

    # India (IST) schedule times
    india_windows = [
        (dtime(9, 15),  "India 9:15 AM IST"),
        (dtime(12, 0),  "India 12:00 PM IST"),
        (dtime(14, 0),  "India 2:00 PM IST"),
        (dtime(15, 30), "India 3:30 PM IST"),
    ]

    for t, label in us_windows:
        target = now_ny.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if is_close_to(target, now_ny):
            return True, label

    for t, label in india_windows:
        target = now_ist.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if is_close_to(target, now_ist):
            return True, label

    return False, None


def main():
    scheduled, window = should_run_now()
    if not scheduled:
        log.info("Not scheduled time → skipping run")
        return
    log.info("Scheduled window triggered: %s", window)

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

        # Market Open Checks
        us_open = is_market_open("US")
        india_open = is_market_open("INDIA")
        
        if not us_open and not india_open:
            log.info("All markets closed. Skipping run.")
            return

        # Data Fetching (Both Markets)
        tickers_us = fetch_sp500_tickers() if us_open else []
        tickers_in = fetch_nifty500_tickers() if india_open else []
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
        if us_open:
            if us_positions:
                new_cash_usd = run_sell_phase_local(us_positions, prices, scores, cash_usd, "USD", vol_map=vol_map)
                if new_cash_usd > cash_usd: proceeds_generated = True
                cash_usd = new_cash_usd
        else:
            log.info("US market closed")
        
        # IN SELLS (Only Indian tickers, impact Indian cash)
        in_positions = {t: p for t, p in positions.items() if t.endswith(".NS")}
        if india_open:
            if in_positions:
                new_cash_inr = run_sell_phase_local(in_positions, prices, scores, cash_inr, "INR", vol_map=vol_map)
                if new_cash_inr > cash_inr: proceeds_generated = True
                cash_inr = new_cash_inr
        else:
            log.info("India market closed")

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
        if us_open:
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
        if india_open:
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

        # ── INTRADAY PHASE (India only) ──────────────────────────────────────
        if india_open:
            cash_inr = run_intraday_phase(
                cash_inr=cash_inr,
                scores=scores,
                prices=prices,
                ohlcv_daily=ohlcv_1y,
            )
            # Persist updated INR cash after intraday activity
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

def run_intraday_phase(
    cash_inr: float,
    scores: dict,
    prices: dict,
    ohlcv_daily: dict,
) -> float:
    """Execute the full intraday trading cycle for the India market.

    Steps:
      1. Fetch 5-minute OHLCV data for the top India candidates.
      2. Compute intraday features (VWAP, momentum, volume, volatility).
      3. If in the EOD window (3:15–3:25 PM IST): evaluate all open intraday
         positions for swing conversion or exit.
      4. Otherwise: run intraday sell phase, then intraday buy phase
         (capped at 30 % of available India cash).

    Returns updated cash_inr.
    """
    ist_tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist_tz)

    log.info("---------- INTRADAY PHASE (India) @ %s ----------", now_ist.strftime("%H:%M IST"))

    # Top India tickers by score (up to 30 candidates)
    india_scored = sorted(
        [(t, s) for t, s in scores.items() if t.endswith(".NS")],
        key=lambda x: -float(x[1]),
    )
    india_tickers = [t for t, _ in india_scored[:30]]

    if not india_tickers:
        log.info("Intraday: no India candidates — skipping")
        return cash_inr

    # Fetch 5-minute intraday data
    intraday_raw = fetch_intraday_ohlcv(india_tickers, period="1d")

    # Compute features for each ticker with sufficient data
    intraday_features: dict = {}
    for t, df in intraday_raw.items():
        if len(df) >= 20:
            intraday_features[t] = intraday_india.compute_intraday_features(df)

    # ── EOD evaluation window ────────────────────────────────────────────────
    if intraday_india.is_eod_window(now_ist):
        log.info("Intraday: EOD window detected — evaluating conversion/exit")
        open_intraday = list(intraday_india._intraday_positions.keys())
        if open_intraday:
            proceeds = intraday_india.handle_eod_positions(
                intraday_tickers=open_intraday,
                prices=prices,
                daily_data=ohlcv_daily,
                model_scores=scores,
                current_time=now_ist,
            )
            cash_inr += proceeds
            log.info(
                "Intraday EOD: proceeds returned=%.2f INR | remaining_open=%d",
                proceeds, len(intraday_india._intraday_positions),
            )
        else:
            log.info("Intraday EOD: no open intraday positions to evaluate")
        return cash_inr

    # ── Regular intraday cycle ───────────────────────────────────────────────

    # 1. SELL PHASE: evaluate existing intraday positions
    from db.portfolio import get_portfolio
    portfolio_map = {p["ticker"]: p for p in get_portfolio()}

    for ticker in list(intraday_india._intraday_positions.keys()):
        pos = portfolio_map.get(ticker)
        current_price = prices.get(ticker)
        if pos is None or current_price is None:
            intraday_india._intraday_positions.pop(ticker, None)
            continue
        df_feat = intraday_features.get(ticker)
        reason, proceeds = intraday_india.handle_intraday_sell(
            ticker, pos, current_price, df_feat, now_ist
        )
        if reason:
            cash_inr += proceeds

    # 2. BUY PHASE: capital-controlled intraday buys
    capital_limit = intraday_india.get_intraday_capital_limit(cash_inr)
    current_exposure = intraday_india.get_current_intraday_exposure(prices)
    available_intraday_capital = max(0.0, capital_limit - current_exposure)

    log.info(
        "Intraday capital: limit=%.2f INR | exposure=%.2f INR | available=%.2f INR",
        capital_limit, current_exposure, available_intraday_capital,
    )

    for ticker, _ in india_scored:
        if available_intraday_capital <= 0:
            break
        df_feat = intraday_features.get(ticker)
        if df_feat is None:
            continue
        model_score = float(scores.get(ticker, 0.0))
        _, capital_spent = intraday_india.handle_intraday_buy(
            ticker=ticker,
            df=df_feat,
            model_score=model_score,
            available_intraday_capital=available_intraday_capital,
            current_time=now_ist,
        )
        if capital_spent > 0:
            cash_inr -= capital_spent
            available_intraday_capital -= capital_spent

    return cash_inr


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
