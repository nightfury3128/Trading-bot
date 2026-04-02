from datetime import datetime, timedelta
from db.supabase_client import supabase
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
        remaining_shares if remaining_shares is not None else 0.0
    )
    try:
        discord_trade_alert(action, ticker, float(price), float(shares), remaining_shares=remaining_shares, pnl_pct=pnl_pct)
    except Exception as e:
        log.debug("discord_trade_alert failed: %s", e)

    try:
        data = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "action": action,
            "ticker": ticker,
            "price": float(price),
            "shares": float(shares),
            "currency": currency,
            "realized_pnl": float(pnl) if pnl is not None else 0.0,
            "pnl_pct": float(pnl_pct) if pnl_pct is not None else 0.0
        }
        if entry_price is not None:
             data["entry_price"] = float(entry_price)
        if entry_date is not None:
             data["entry_date"] = str(entry_date)
        if remaining_shares is not None:
             data["remaining_shares"] = float(remaining_shares)

        supabase.table("trades").insert(data).execute()
    except Exception as e:
        # Fallback if new columns don't exist yet in Supabase schema cache
        log.warning("Primary insert failed, likely missing columns (entry_price/entry_date): %s", e)
        try:
             minimal_data = {
                 "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                 "action": action,
                 "ticker": ticker,
                 "price": float(price),
                 "shares": float(shares),
                 "currency": currency,
                 "realized_pnl": float(pnl) if pnl is not None else 0.0,
                 "pnl_pct": float(pnl_pct) if pnl_pct is not None else 0.0
             }
             supabase.table("trades").insert(minimal_data).execute()
        except Exception as e2:
             log.error("Final DB fallback failed: %s", e2)


def get_recent_sells() -> set:
    try:
        # Rule 6: Track last sell date per ticker from trades table.
        five0_days_ago = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
        res = (
            supabase.table("trades")
            .select("ticker,date")
            # Treat MODEL_SELL as a sell action for consistency with UI aggregation.
            .filter("action", "in", '("SELL","STOP_LOSS","TAKE_PROFIT","MODEL_SELL")')
            .gte("date", five0_days_ago)
            .execute()
        )
        return {r["ticker"] for r in (res.data or [])}
    except Exception as e:
        log.warning("get_recent_sells failed: %s", e)
        return set()
