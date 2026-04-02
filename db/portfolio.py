from datetime import datetime
from db.supabase_client import supabase


def get_portfolio():
    return supabase.table("portfolio").select("*").execute().data or []


def add_position(ticker: str, shares: float, price: float):
    supabase.table("portfolio").insert(
        {
            "ticker": ticker,
            "shares": float(shares),
            "buy_price": float(price),
            "buy_date": datetime.now().strftime("%Y-%m-%d"),
        }
    ).execute()


def remove_position(ticker: str):
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()
