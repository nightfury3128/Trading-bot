from datetime import datetime
from db.supabase_client import supabase


def get_portfolio():
    return supabase.table("portfolio").select("*").execute().data or []


def add_position(ticker: str, shares: float, price: float, currency: str = "USD", local_val: float = None, usd_val: float = None):
    supabase.table("portfolio").insert(
        {
            "ticker": ticker,
            "shares": float(shares),
            "buy_price": float(price),
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
            "currency": currency,
            "local_value": float(local_val) if local_val is not None else float(shares * price),
            "usd_value": float(usd_val) if usd_val is not None else float(shares * price) # If local_val was USD already
        }
    ).execute()


def remove_position(ticker: str):
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()
