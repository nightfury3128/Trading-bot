from datetime import datetime, timedelta
from db.supabase_client import supabase
from utils.logger import log
from utils.notifications import discord_trade_alert


def log_trade(action: str, ticker: str, price: float, shares: float):
    log.info(
        "TRADE: action=%s ticker=%s price=%.6f shares=%s",
        action,
        ticker,
        float(price),
        shares,
    )
    try:
        discord_trade_alert(action, ticker, float(price), float(shares))
    except Exception as e:
        log.debug("discord_trade_alert failed: %s", e)

    supabase.table("trades").insert(
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "action": action,
            "ticker": ticker,
            "price": float(price),
            "shares": float(shares),
        }
    ).execute()


def get_recent_sells() -> set:
    try:
        # Rule 6: Track last sell date per ticker from trades table.
        five0_days_ago = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
        res = (
            supabase.table("trades")
            .select("ticker,date")
            .filter("action", "in", '("SELL","STOP_LOSS","TAKE_PROFIT")')
            .gte("date", five0_days_ago)
            .execute()
        )
        return {r["ticker"] for r in (res.data or [])}
    except Exception as e:
        log.warning("get_recent_sells failed: %s", e)
        return set()
