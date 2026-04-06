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
    strategy_type: str = None,
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
    if strategy_type is not None:
        data["strategy_type"] = str(strategy_type)

    supabase.table("portfolio").insert(data).execute()


def update_position(ticker: str, new_shares: float, current_price: float):
    # Fetch current to preserve some data if needed, but mainly we update shares and calculated values
    res = supabase.table("portfolio").select("*").eq("ticker", ticker).single().execute()
    if not res.data:
        return
    
    pos = res.data
    buy_price = float(pos["buy_price"])
    from utils.currency import get_currency, get_conversion_rates
    currency = pos.get("currency", get_currency(ticker))
    inr_to_usd, _ = get_conversion_rates()
    
    new_local_val = new_shares * buy_price # Book value update? Or current value? 
    # Usually portfolio table stores "invested" value. But let's check add_position.
    # add_position uses shares * price (execution price).
    
    new_usd_val = new_local_val
    if currency == "INR":
        new_usd_val = new_local_val * inr_to_usd
    
    data = {
        "shares": float(new_shares),
        "local_value": float(new_local_val),
        "usd_value": float(new_usd_val)
    }
    
    supabase.table("portfolio").update(data).eq("ticker", ticker).execute()


def remove_position(ticker: str):
    # Constraint removed - we can now delete from portfolio while keeping trade history!
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()
