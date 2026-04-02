from datetime import datetime
from db.supabase_client import supabase


def get_portfolio():
    return supabase.table("portfolio").select("*").execute().data or []


def add_position(
    ticker: str,
    shares: float,
    price: float,
    currency: str = "USD",
    local_val: float = None,
    usd_val: float = None,
    risk_level: str = None,
    stop_loss: float = None,
):
    data = {
        "ticker": ticker,
        "shares": float(shares),
        "buy_price": float(price),
        "buy_date": datetime.now().strftime("%Y-%m-%d"),
        "currency": currency,
        "local_value": float(local_val) if local_val is not None else float(shares * price),
        # If local_val was USD already, caller should pass usd_val; otherwise default conversion happens upstream.
        "usd_value": float(usd_val) if usd_val is not None else float(shares * price),
    }

    # Supabase table extension: risk_level/stop_loss are optional.
    if risk_level is not None:
        data["risk_level"] = str(risk_level)
    if stop_loss is not None:
        data["stop_loss"] = float(stop_loss)

    supabase.table("portfolio").insert(data).execute()


def remove_position(ticker: str):
    # Constraint removed - we can now delete from portfolio while keeping trade history!
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()
