from datetime import datetime

from db.supabase_client import execute, fetch_all, fetch_one


def get_portfolio():
    return fetch_all("select * from portfolio order by ticker")


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
    execute(
        """
        insert into portfolio
            (ticker, shares, buy_price, buy_date, currency, local_value, usd_value, risk_level, stop_loss)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ticker,
            float(shares),
            float(price),
            datetime.now().strftime("%Y-%m-%d"),
            currency,
            float(local_val) if local_val is not None else float(shares * price),
            float(usd_val) if usd_val is not None else float(shares * price),
            str(risk_level) if risk_level is not None else None,
            float(stop_loss) if stop_loss is not None else None,
        ),
    )


def update_position(ticker: str, new_shares: float, current_price: float):
    pos = fetch_one("select * from portfolio where ticker = %s", (ticker,))
    if not pos:
        return

    buy_price = float(pos["buy_price"])
    from utils.currency import get_currency, get_conversion_rates

    currency = pos.get("currency", get_currency(ticker))
    inr_to_usd, _ = get_conversion_rates()

    new_local_val = new_shares * buy_price
    new_usd_val = new_local_val * inr_to_usd if currency == "INR" else new_local_val

    execute(
        "update portfolio set shares = %s, local_value = %s, usd_value = %s where ticker = %s",
        (float(new_shares), float(new_local_val), float(new_usd_val), ticker),
    )


def remove_position(ticker: str):
    execute("delete from portfolio where ticker = %s", (ticker,))
