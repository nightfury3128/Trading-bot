"""
Utility to wipe ALL database tables and reset the account to a fresh $258 starting balance.
Run: python -m utils.clear_all
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import INITIAL_CASH_USD  # noqa: E402
from db.supabase_client import execute  # noqa: E402
from utils.logger import setup_logger  # noqa: E402

log = setup_logger("db_cleaner")

STARTING_USD = INITIAL_CASH_USD  # $258
STARTING_INR = 0.0  # US-only mode


def clear_all():
    for table in ("trades", "portfolio", "performance"):
        log.info("Clearing %s table...", table.upper())
        try:
            execute(f"delete from {table}")
            log.info("  ✓ %s cleared.", table)
        except Exception as e:
            log.error("  ✗ %s: %s", table, e)

    log.info("Resetting ACCOUNT to $%.2f USD / ₹%.2f INR...", STARTING_USD, STARTING_INR)
    try:
        execute(
            "insert into account (id, cash_usd, cash_inr) values (1, %s, %s) "
            "on conflict (id) do update set cash_usd = excluded.cash_usd, cash_inr = excluded.cash_inr",
            (STARTING_USD, STARTING_INR),
        )
        log.info("  ✓ Account reset.")
    except Exception as e:
        log.error("  ✗ Account: %s", e)

    log.info("=== ALL TABLES CLEARED. Fresh start ready! ===")


if __name__ == "__main__":
    confirm = input("⚠️  This will DELETE all trades, positions, and performance data. Type 'yes' to confirm: ")
    if confirm.strip().lower() == "yes":
        clear_all()
    else:
        print("Aborted.")
