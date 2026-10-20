from config import INITIAL_CASH_INR, INITIAL_CASH_USD
from db.supabase_client import execute, fetch_one


def get_account():
    # Seed the $258 starting balance on first run against a fresh database.
    execute(
        "insert into account (id, cash_usd, cash_inr) values (1, %s, %s) "
        "on conflict (id) do nothing",
        (float(INITIAL_CASH_USD), float(INITIAL_CASH_INR)),
    )
    row = fetch_one("select * from account where id = 1")
    if not row:
        return {"cash_usd": float(INITIAL_CASH_USD), "cash_inr": float(INITIAL_CASH_INR)}
    return row


def update_cash(new_cash_usd: float, new_cash_inr: float = 0.0):
    execute(
        "insert into account (id, cash_usd, cash_inr) values (1, %s, %s) "
        "on conflict (id) do update set cash_usd = excluded.cash_usd, cash_inr = excluded.cash_inr",
        (float(new_cash_usd), float(new_cash_inr)),
    )
