"""Intraday trading strategy for the Indian market (NSE).

Features
--------
- 5-minute candle signals: VWAP, momentum, rolling volume, volatility
- Time-aware confidence scaling via ``time_factor()``
- 15-minute per-ticker trade cooldown to prevent overtrading
- 2 % stop-loss and 2 % profit-target exits
- End-of-day (3:15–3:25 PM IST) conversion evaluation:
    - Strong positions (pnl > 1 %, price > MA20, MA20 > MA50, confidence > 0.6)
      are converted to swing trades with a wider 7 % stop-loss.
    - All other positions are closed.
- Intraday capital capped at 30 % of available India cash.

This module is INDEPENDENT from the swing strategy (strategy/india_strategy.py).
Do NOT use it for swing positions and do NOT mix the two position sets.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import pytz

from config import (
    COST_BUY,
    COST_SELL,
    INTRADAY_CAPITAL_FRACTION,
    INTRADAY_CONVERSION_MIN_CONFIDENCE,
    INTRADAY_CONVERSION_MIN_PNL,
    INTRADAY_COOLDOWN_MINUTES,
    INTRADAY_PROFIT_TARGET_PCT,
    INTRADAY_STOP_LOSS_PCT,
    INTRADAY_SWING_STOP_LOSS_PCT,
)
from db.portfolio import add_position, remove_position
from db.trades import log_trade
from utils.logger import log

IST = pytz.timezone("Asia/Kolkata")

# ──────────────────────────────────────────────────────────────────────────────
# Module-level session state
# ──────────────────────────────────────────────────────────────────────────────

# Intraday positions opened in the current process lifetime.
# { ticker: {"entry_price": float, "entry_time": datetime, "shares": float} }
_intraday_positions: dict[str, dict] = {}

# Last trade timestamp per ticker (used for cooldown enforcement).
_last_trade_time: dict[str, datetime] = {}


# ──────────────────────────────────────────────────────────────────────────────
# Time-aware confidence
# ──────────────────────────────────────────────────────────────────────────────

def time_factor(current_time: datetime) -> float:
    """Return a confidence multiplier in [0.5, 1.0] based on IST time of day.

    Schedule (IST):
      - 09:15–09:30  Very early open           → 0.50
      - 09:30–10:15  Early session              → 0.70
      - 10:15–11:30  Strong morning hours       → 1.00
      - 11:30–13:00  Midday lull                → 0.85
      - 13:00–14:30  Strong afternoon hours     → 1.00
      - 14:30–15:00  Pre-EOD caution            → 0.80
      - 15:00+       EOD zone                   → 0.60
    """
    if current_time.tzinfo is None:
        current_time = IST.localize(current_time)
    else:
        current_time = current_time.astimezone(IST)

    t = current_time.hour + current_time.minute / 60.0

    if t < 9.5:
        return 0.50
    if t < 10.25:
        return 0.70
    if t < 11.5:
        return 1.00
    if t < 13.0:
        return 0.85
    if t < 14.5:
        return 1.00
    if t < 15.0:
        return 0.80
    return 0.60


# ──────────────────────────────────────────────────────────────────────────────
# Intraday feature computation
# ──────────────────────────────────────────────────────────────────────────────

def compute_intraday_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute intraday indicators on 5-minute OHLCV data.

    Adds columns:
      - ``vwap``             – cumulative VWAP for the trading session
      - ``momentum``         – 6-period (~30 min) price return
      - ``rolling_avg_volume``– 20-period rolling mean volume (~100 min)
      - ``returns``          – 1-period close-to-close return
      - ``volatility``       – 20-period rolling std of ``returns``
    """
    df = df.copy()

    # VWAP: cumulative (typical_price × volume) / cumulative volume
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    cum_vol = df["Volume"].cumsum()
    # Guard against zero cumulative volume
    df["vwap"] = (typical_price * df["Volume"]).cumsum() / cum_vol.replace(0, np.nan)

    # Short-term momentum: 6-period return (~30 min)
    df["momentum"] = df["Close"].pct_change(periods=6)

    # Rolling average volume: 20-period window, at least 5 periods
    df["rolling_avg_volume"] = (
        df["Volume"].rolling(window=20, min_periods=5).mean()
    )

    # Returns and volatility
    df["returns"] = df["Close"].pct_change()
    df["volatility"] = df["returns"].rolling(window=20, min_periods=5).std()

    return df


# ──────────────────────────────────────────────────────────────────────────────
# Cooldown helper
# ──────────────────────────────────────────────────────────────────────────────

def _is_on_cooldown(ticker: str, now: datetime) -> bool:
    """Return True if the ticker is within the 15-minute trade cooldown."""
    last = _last_trade_time.get(ticker)
    if last is None:
        return False
    if now.tzinfo is None:
        now = IST.localize(now)
    if last.tzinfo is None:
        last = IST.localize(last)
    return (now - last).total_seconds() < INTRADAY_COOLDOWN_MINUTES * 60


# ──────────────────────────────────────────────────────────────────────────────
# Buy signal evaluation
# ──────────────────────────────────────────────────────────────────────────────

def should_buy(
    ticker: str,
    df: pd.DataFrame,
    model_score: float,
    current_time: Optional[datetime] = None,
) -> tuple[bool, float, str]:
    """Evaluate whether an intraday buy signal is valid.

    Conditions (all must pass):
      1. price > VWAP
      2. momentum > 0
      3. current volume > rolling average volume
      4. final_score = model_score × time_factor > 0
      5. not currently on cooldown
      6. volatility < 0.05 (otherwise position size is reduced but trade can proceed
         if other conditions are strong; if volatility >= 0.05 → skip)

    Returns
    -------
    (signal: bool, final_score: float, reason: str)
    """
    if current_time is None:
        current_time = datetime.now(IST)

    if df is None or len(df) < 20:
        return False, 0.0, "INSUFFICIENT_DATA"

    if ticker in _intraday_positions:
        return False, 0.0, "ALREADY_HELD"

    if _is_on_cooldown(ticker, current_time):
        return False, 0.0, "COOLDOWN"

    row = df.iloc[-1]
    price = float(row["Close"])
    vwap = float(row.get("vwap", price))
    momentum = float(row.get("momentum", 0.0))
    volume = float(row.get("Volume", 0.0))
    avg_volume = float(row.get("rolling_avg_volume", volume))
    volatility = float(row.get("volatility", 0.02))

    # Guard invalid VWAP
    if not math.isfinite(vwap) or vwap <= 0:
        return False, 0.0, "INVALID_VWAP"

    # 1. Price above VWAP
    if price <= vwap:
        return False, 0.0, "BELOW_VWAP"

    # 2. Positive momentum
    if not math.isfinite(momentum) or momentum <= 0:
        return False, 0.0, "NEGATIVE_MOMENTUM"

    # 3. Volume filter
    if avg_volume > 0 and volume <= avg_volume:
        return False, 0.0, "LOW_VOLUME"

    # 4. Time-adjusted model score
    tf = time_factor(current_time)
    final_score = float(model_score) * tf
    if final_score <= 0:
        return False, final_score, "LOW_MODEL_SCORE"

    # 5. Volatility filter: skip trade if excessively high
    if math.isfinite(volatility) and volatility >= 0.05:
        log.info(
            "Intraday [%s]: High volatility (%.4f) — skipping buy",
            ticker, volatility,
        )
        return False, final_score, "HIGH_VOLATILITY"

    vol_ratio = volume / max(avg_volume, 1.0)
    reason = (
        f"price={price:.2f}>vwap={vwap:.2f}, "
        f"momentum={momentum:.4f}, "
        f"vol_ratio={vol_ratio:.2f}x, "
        f"tf={tf:.2f}, score={final_score:.4f}"
    )
    return True, final_score, reason


# ──────────────────────────────────────────────────────────────────────────────
# Position sizing
# ──────────────────────────────────────────────────────────────────────────────

def compute_intraday_position_size(
    price: float,
    available_capital: float,
    volatility: float,
    final_score: float,
) -> float:
    """Return whole-share count for a new intraday position (INR market).

    Capital fraction based on volatility:
      - vol < 0.02  → up to 25 % of available intraday capital
      - vol < 0.04  → up to 15 %
      - vol >= 0.04 → up to 8 %

    A confidence boost (capped at 1.0) is applied from the final score.
    """
    if price <= 0 or available_capital <= 0:
        return 0.0

    if volatility < 0.02:
        fraction = 0.25
    elif volatility < 0.04:
        fraction = 0.15
    else:
        fraction = 0.08

    # Confidence boost: score * 10, clamped to [0.5, 1.0]
    confidence_boost = min(1.0, max(0.5, float(final_score) * 10))
    allocation = available_capital * fraction * confidence_boost
    shares = math.floor(allocation / price)
    return float(shares)


# ──────────────────────────────────────────────────────────────────────────────
# Intraday sell signal evaluation
# ──────────────────────────────────────────────────────────────────────────────

def should_sell_intraday(
    ticker: str,
    pos: dict,
    current_price: float,
    df: Optional[pd.DataFrame],
) -> tuple[bool, str]:
    """Evaluate intraday sell conditions.

    Sell when:
      - Stop loss: price dropped ≥ 2 % below entry
      - Profit target: price rose ≥ 2 % above entry
      - VWAP cross: current price fell below current VWAP
    """
    entry_price = float(pos.get("entry_price", pos.get("buy_price", current_price)))
    pnl_pct = (current_price - entry_price) / entry_price

    if pnl_pct <= -INTRADAY_STOP_LOSS_PCT:
        return True, "INTRADAY_STOP_LOSS"

    if pnl_pct >= INTRADAY_PROFIT_TARGET_PCT:
        return True, "INTRADAY_PROFIT_TARGET"

    if df is not None and len(df) > 0:
        vwap = float(df.iloc[-1].get("vwap", current_price))
        if math.isfinite(vwap) and vwap > 0 and current_price < vwap:
            return True, "INTRADAY_BELOW_VWAP"

    return False, ""


# ──────────────────────────────────────────────────────────────────────────────
# EOD conversion evaluation
# ──────────────────────────────────────────────────────────────────────────────

def _compute_conversion_metrics(
    pos: dict,
    current_price: float,
    daily_df: Optional[pd.DataFrame],
    model_confidence: float,
) -> dict:
    """Derive metrics used to decide whether to convert an intraday position to swing.

    Metrics returned:
      - pnl            – (current_price − entry_price) / entry_price
      - price_vs_ma20  – True if current_price > MA20
      - ma20_vs_ma50   – True if MA20 > MA50
      - confidence     – model_confidence value
      - ma20, ma50     – computed MA values (or None)
    """
    entry_price = float(pos.get("entry_price", pos.get("buy_price", current_price)))
    pnl = (current_price - entry_price) / entry_price

    ma20_val: Optional[float] = None
    ma50_val: Optional[float] = None
    price_vs_ma20 = False
    ma20_vs_ma50 = False

    if daily_df is not None and len(daily_df) >= 50:
        closes = daily_df["Close"].astype(float).dropna()
        if len(closes) >= 50:
            ma20_val = float(closes.iloc[-20:].mean())
            ma50_val = float(closes.iloc[-50:].mean())
            price_vs_ma20 = current_price > ma20_val
            ma20_vs_ma50 = ma20_val > ma50_val

    return {
        "pnl": pnl,
        "price_vs_ma20": price_vs_ma20,
        "ma20_vs_ma50": ma20_vs_ma50,
        "confidence": float(model_confidence),
        "ma20": ma20_val,
        "ma50": ma50_val,
    }


def evaluate_eod_conversion(
    ticker: str,
    pos: dict,
    current_price: float,
    daily_df: Optional[pd.DataFrame],
    model_confidence: float,
) -> tuple[str, dict]:
    """Decide whether to convert or exit an intraday position at end of day.

    Convert to swing if ALL conditions are met:
      - pnl > 1 %
      - price > MA20
      - MA20 > MA50
      - model_confidence > 0.6

    Returns
    -------
    (decision: "CONVERT" | "EXIT", metrics: dict)
    """
    metrics = _compute_conversion_metrics(pos, current_price, daily_df, model_confidence)

    convert = (
        metrics["pnl"] > INTRADAY_CONVERSION_MIN_PNL
        and metrics["price_vs_ma20"]
        and metrics["ma20_vs_ma50"]
        and metrics["confidence"] > INTRADAY_CONVERSION_MIN_CONFIDENCE
    )
    decision = "CONVERT" if convert else "EXIT"

    log.info(
        "EOD Conversion [%s]: decision=%s | pnl=%.2f%% | price_vs_ma20=%s | "
        "ma20_vs_ma50=%s | confidence=%.3f",
        ticker, decision,
        metrics["pnl"] * 100,
        metrics["price_vs_ma20"],
        metrics["ma20_vs_ma50"],
        metrics["confidence"],
    )

    return decision, metrics


def _convert_position_to_swing(ticker: str, new_stop_loss: float) -> None:
    """Update the portfolio DB record with swing stop-loss.

    The ``strategy_type`` tag is intentionally left as-is in the DB because
    the swing strategy's own execution loop will pick up the position
    naturally via its ticker suffix (``.NS``).
    """
    from db.supabase_client import supabase
    try:
        supabase.table("portfolio").update(
            {"stop_loss": new_stop_loss}
        ).eq("ticker", ticker).execute()
        log.info(
            "Converted [%s] → SWING: stop_loss updated to %.1f%%",
            ticker, (1.0 - new_stop_loss) * 100,
        )
    except Exception as exc:
        log.warning(
            "Could not update stop_loss for %s during conversion: %s", ticker, exc
        )


# ──────────────────────────────────────────────────────────────────────────────
# High-level trade execution helpers
# ──────────────────────────────────────────────────────────────────────────────

def handle_intraday_buy(
    ticker: str,
    df: pd.DataFrame,
    model_score: float,
    available_intraday_capital: float,
    current_time: Optional[datetime] = None,
) -> tuple[float, float]:
    """Attempt to execute an intraday buy.

    Returns
    -------
    (shares_bought: float, capital_spent: float)
        Both are 0.0 when no trade is executed.
    """
    if current_time is None:
        current_time = datetime.now(IST)

    ok, final_score, reason = should_buy(ticker, df, model_score, current_time)
    if not ok:
        log.debug("Intraday [%s]: No buy — %s", ticker, reason)
        return 0.0, 0.0

    row = df.iloc[-1]
    price = float(row["Close"])
    volatility = float(row.get("volatility", 0.02))
    if not math.isfinite(volatility):
        volatility = 0.02

    shares = compute_intraday_position_size(
        price, available_intraday_capital, volatility, final_score
    )
    if shares <= 0:
        log.info(
            "Intraday [%s]: No buy — insufficient capital for even 1 share", ticker
        )
        return 0.0, 0.0

    execution_price = price * COST_BUY
    capital_spent = shares * execution_price
    if capital_spent > available_intraday_capital:
        log.info(
            "Intraday [%s]: No buy — allocation (%.2f) exceeds available capital (%.2f)",
            ticker, capital_spent, available_intraday_capital,
        )
        return 0.0, 0.0

    tf = time_factor(current_time)

    # Register in module state
    _intraday_positions[ticker] = {
        "entry_price": execution_price,
        "entry_time": current_time,
        "shares": shares,
    }
    _last_trade_time[ticker] = current_time

    # Persist to DB
    add_position(
        ticker,
        shares,
        execution_price,
        currency="INR",
        local_val=capital_spent,
        strategy_type="INTRADAY",
    )
    log_trade("INTRADAY_BUY", ticker, execution_price, shares)

    log.info(
        "Intraday BUY [%s]: %.0f shares @ %.2f | spent=%.2f INR | "
        "entry_reason=%s | time_factor=%.2f | score=%.4f",
        ticker, shares, execution_price, capital_spent, reason, tf, final_score,
    )

    return shares, capital_spent


def handle_intraday_sell(
    ticker: str,
    pos: dict,
    current_price: float,
    df: Optional[pd.DataFrame],
    current_time: Optional[datetime] = None,
) -> tuple[Optional[str], float]:
    """Evaluate and execute intraday sell logic.

    Returns
    -------
    (sell_reason | None, proceeds_inr: float)
    """
    if current_time is None:
        current_time = datetime.now(IST)

    do_sell, reason = should_sell_intraday(ticker, pos, current_price, df)
    if not do_sell:
        return None, 0.0

    shares = float(pos.get("shares", 0.0))
    entry_price = float(pos.get("entry_price", pos.get("buy_price", current_price)))
    execution_price = current_price * COST_SELL
    proceeds = shares * execution_price
    pnl = (execution_price - entry_price) * shares
    pnl_pct = ((execution_price / entry_price) - 1) * 100

    # Update cooldown and remove from session state
    _last_trade_time[ticker] = current_time
    _intraday_positions.pop(ticker, None)

    remove_position(ticker)
    log_trade(
        reason, ticker, execution_price, shares,
        pnl=pnl, pnl_pct=pnl_pct, entry_price=entry_price,
    )

    log.info(
        "Intraday SELL [%s]: reason=%s | %.0f shares @ %.2f | "
        "proceeds=%.2f INR | pnl=%.2f INR (%.2f%%)",
        ticker, reason, shares, execution_price, proceeds, pnl, pnl_pct,
    )

    return reason, proceeds


def handle_eod_positions(
    intraday_tickers: list[str],
    prices: dict[str, float],
    daily_data: dict[str, pd.DataFrame],
    model_scores: dict[str, float],
    current_time: Optional[datetime] = None,
) -> float:
    """Process all open intraday positions at end of day.

    For each position either:
      - Converts to swing (updates stop-loss, keeps position open), or
      - Exits the position (sells at current price).

    Returns
    -------
    proceeds_inr: float  – cash returned from all closed (non-converted) positions
    """
    if current_time is None:
        current_time = datetime.now(IST)

    from db.portfolio import get_portfolio
    portfolio = {p["ticker"]: p for p in get_portfolio()}

    proceeds_inr = 0.0

    for ticker in list(intraday_tickers):
        pos = portfolio.get(ticker)
        current_price = prices.get(ticker)

        if pos is None or current_price is None:
            _intraday_positions.pop(ticker, None)
            continue

        daily_df = daily_data.get(ticker)
        confidence = float(model_scores.get(ticker, 0.0))

        decision, metrics = evaluate_eod_conversion(
            ticker, pos, current_price, daily_df, confidence
        )

        shares = float(pos.get("shares", 0.0))
        entry_price = float(pos.get("entry_price", pos.get("buy_price", current_price)))
        pnl = (current_price - entry_price) * shares
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        if decision == "CONVERT":
            new_stop_loss = 1.0 - INTRADAY_SWING_STOP_LOSS_PCT
            _convert_position_to_swing(ticker, new_stop_loss)
            log_trade(
                "INTRADAY_TO_SWING", ticker, current_price, shares,
                pnl=pnl, pnl_pct=pnl_pct, entry_price=entry_price,
            )
            log.info(
                "EOD CONVERT [%s]: INTRADAY → SWING | new_stop_loss=%.1f%% | "
                "pnl=%.2f INR (%.2f%%) | confidence=%.3f",
                ticker, INTRADAY_SWING_STOP_LOSS_PCT * 100, pnl, pnl_pct, confidence,
            )
        else:
            execution_price = current_price * COST_SELL
            p = shares * execution_price
            proceeds_inr += p
            remove_position(ticker)
            log_trade(
                "INTRADAY_EOD_EXIT", ticker, execution_price, shares,
                pnl=pnl, pnl_pct=pnl_pct, entry_price=entry_price,
            )
            log.info(
                "EOD EXIT [%s]: proceeds=%.2f INR | pnl=%.2f INR (%.2f%%)",
                ticker, p, pnl, pnl_pct,
            )

        _intraday_positions.pop(ticker, None)

    return proceeds_inr


# ──────────────────────────────────────────────────────────────────────────────
# Capital control helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_intraday_capital_limit(cash_inr: float) -> float:
    """Return the maximum INR capital allowed for all open intraday positions."""
    return cash_inr * INTRADAY_CAPITAL_FRACTION


def get_current_intraday_exposure(prices: dict[str, float]) -> float:
    """Return total current INR market value of open intraday positions."""
    total = 0.0
    for ticker, pos_data in _intraday_positions.items():
        px = prices.get(ticker, pos_data.get("entry_price", 0.0))
        total += float(pos_data.get("shares", 0.0)) * px
    return total


# ──────────────────────────────────────────────────────────────────────────────
# EOD window check
# ──────────────────────────────────────────────────────────────────────────────

def is_eod_window(current_time: Optional[datetime] = None) -> bool:
    """Return True if the current IST time is in the EOD window (3:15–3:25 PM)."""
    if current_time is None:
        current_time = datetime.now(IST)
    if current_time.tzinfo is None:
        current_time = IST.localize(current_time)
    else:
        current_time = current_time.astimezone(IST)
    t = current_time.hour + current_time.minute / 60.0
    # 3:15 PM = 15.25, 3:25 PM ≈ 15.417
    return 15.25 <= t <= 15.417
