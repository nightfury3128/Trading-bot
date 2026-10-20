from datetime import datetime, timedelta

from db.supabase_client import execute, fetch_all
from utils.logger import log
from utils.notifications import discord_trade_alert


def log_trade(action: str, ticker: str, price: float, shares: float, pnl: float = None, pnl_pct: float = None, entry_price: float = None, entry_date: str = None, remaining_shares: float = None):
    from utils.currency import get_currency

    currency = get_currency(ticker)

    log.info(
        "TRADE: action=%s ticker=%s price=%.6f shares=%s currency=%s P/L=%.2f (%.2f%%) remaining=%s",
        action,
        ticker,
        float(price),
        shares,
        currency,
        pnl if pnl is not None else 0.0,
        pnl_pct if pnl_pct is not None else 0.0,
        remaining_shares if remaining_shares is not None else 0.0,
    )
    try:
        discord_trade_alert(action, ticker, float(price), float(shares), remaining_shares=remaining_shares, pnl_pct=pnl_pct)
    except Exception as e:
        log.debug("discord_trade_alert failed: %s", e)

    try:
        execute(
            """
            insert into trades
                (date, action, ticker, price, shares, currency, realized_pnl, pnl_pct,
                 entry_price, entry_date, remaining_shares)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                action,
                ticker,
                float(price),
                float(shares),
                currency,
                float(pnl) if pnl is not None else 0.0,
                float(pnl_pct) if pnl_pct is not None else 0.0,
                float(entry_price) if entry_price is not None else None,
                str(entry_date) if entry_date is not None else None,
                float(remaining_shares) if remaining_shares is not None else None,
            ),
        )
    except Exception as e:
        log.error("Failed to write trade to Supabase: %s", e)


def get_recent_sells() -> set:
    try:
        six_days_ago = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
        rows = fetch_all(
            "select ticker, date from trades "
            "where action in ('SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'MODEL_SELL') and date >= %s",
            (six_days_ago,),
        )
        return {r["ticker"] for r in rows}
    except Exception as e:
        log.warning("get_recent_sells failed: %s", e)
        return set()
