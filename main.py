import logging
from datetime import datetime
import numpy as np

from utils.logger import log
from utils.time_utils import _t0, _dt
from utils.notifications import (
    discord_error,
    discord_no_trade,
    discord_portfolio_summary,
)

from config import TOP_ML_COUNT, TOP_BUY_PICKS, MIN_PREDICTED_RETURN
from db.account import get_account, update_cash
from db.portfolio import get_portfolio
from db.performance import log_performance

from data.fetch import fetch_sp500_tickers, bulk_download_by_ticker
from data.features import prepare_ml_dataframe
from models.train import train_and_score

from strategy.ranking import get_market_regime, normalize_scores, rank_candidates
from strategy.risk import calculate_industry_exposures
from execution.trading import run_sell_phase, run_buy_phase


def main():
    RUN_T0 = _t0()
    log.info("========== BOT RUN START %s ==========", datetime.now().isoformat())

    # Rule 10: Time-based execution
    hour_utc = datetime.now().hour
    MODE = "OPEN" if hour_utc < 16 else "CLOSE"
    log.info("Time Check: Hour=%d, MODE=%s", hour_utc, MODE)

    try:
        # Initial State
        account = get_account()
        cash = float(account["cash"])
        portfolio = get_portfolio()
        positions = {p["ticker"]: p for p in portfolio}
        market_regime_bullish = get_market_regime()

        log.info("Startup: cash=%.2f, positions=%s", cash, list(positions.keys()))

        # Data Fetching
        sp500 = fetch_sp500_tickers()
        filter_map = bulk_download_by_ticker(sp500, "6mo")

        # Momentum Filter
        ranked_mom = []
        for t, df in filter_map.items():
            if len(df) < 50:
                continue
            px = df["Close"].astype(float)
            mom = float(px.iloc[-1] / px.iloc[-21] - 1.0)
            if mom > 0:
                ranked_mom.append((t, mom))

        ranked_mom.sort(key=lambda x: -x[1])
        top_tickers = [t for t, _ in ranked_mom[:TOP_ML_COUNT]]

        # ML Scoring
        scores, vol_map, prices = {}, {}, {}
        ml_list = list(set(top_tickers + list(positions.keys())))
        ohlcv_1y = bulk_download_by_ticker(ml_list, "1y")

        for ticker, df in ohlcv_1y.items():
            ml_df = prepare_ml_dataframe(df)
            if not ml_df.empty:
                pred, vol = train_and_score(ml_df)
                scores[ticker] = pred
                vol_map[ticker] = vol
                prices[ticker] = float(df["Close"].dropna().iloc[-1])

        if not scores:
            log.warning("No ML scores generated. Skipping trade cycle.")
            return

        # Normalization and Ranking
        z_scores = normalize_scores(scores)
        ranked_candidates = rank_candidates(z_scores)

        # SELL PHASE (CLOSE mode)
        if MODE == "CLOSE":
            cash = run_sell_phase(positions, prices, scores, cash)
        else:
            log.info("Skipping SELL phase (Rules: Only allow SELL when MODE == CLOSE)")

        # Refresh state for Buy phase
        portfolio = get_portfolio()
        positions = {p["ticker"]: p for p in portfolio}

        # BUY PHASE (OPEN mode)
        top_picks = []
        if MODE == "OPEN":
            if not market_regime_bullish:
                log.info("BUY disabled: Market Regime is BEARISH (MA50 < MA200)")
            else:
                eligible = []
                for t, zs in ranked_candidates:
                    if scores[t] > MIN_PREDICTED_RETURN and t not in positions:
                        vol = vol_map.get(t, 0.02)
                        risk_score = scores[t] / (vol if vol > 0 else 0.02)
                        eligible.append((t, risk_score))
                    if len(eligible) >= 10:
                        break

                top_picks_raw = eligible[:TOP_BUY_PICKS]
                cash = run_buy_phase(top_picks_raw, prices, scores, cash, portfolio)
                top_picks = top_picks_raw
        else:
            log.info("Skipping BUY phase (Rules: Only allow BUY when MODE == OPEN)")

        # Wrap up
        update_cash(cash)

        # Final reporting
        final_portfolio = get_portfolio()
        final_total_val, _ = calculate_industry_exposures(
            {p["ticker"]: p for p in final_portfolio}, prices
        )
        final_total_val += cash

        log_performance(final_total_val)

        pl_unrealized = 0.0
        for p in final_portfolio:
            px = prices.get(p["ticker"], float(p["buy_price"]))
            shares = float(p["shares"])
            pl_unrealized += (px - float(p["buy_price"])) * shares

        discord_portfolio_summary(
            run_date=datetime.now().strftime("%Y-%m-%d"),
            cash=cash,
            invested=final_total_val - cash,
            total_value=final_total_val,
            pl_unrealized=pl_unrealized,
            top_picks=[(t, scores[t]) for t, _ in top_picks],
            positions={p["ticker"]: p for p in final_portfolio},
            prices=prices,
        )

    except Exception as e:
        log.exception("Fatal error in main orchestration loop.")
        try:
            discord_error(str(e))
        except:
            pass

    log.info("========== BOT RUN END wall_ms=%.2f ==========", _dt(RUN_T0))


if __name__ == "__main__":
    main()
