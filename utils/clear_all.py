"""
Utility to wipe ALL database tables and reset the account to fresh starting balances.
Run: python -m utils.clear_all
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.supabase_client import supabase
from utils.logger import setup_logger

log = setup_logger("db_cleaner")

STARTING_USD = 500.0
STARTING_INR = 5000.0


def clear_all():
    # 1. Trades (must go first — no FK issues)
    log.info("Clearing TRADES table...")
    try:
        supabase.table("trades").delete().neq("ticker", "").execute()
        log.info("  ✓ Trades cleared.")
    except Exception as e:
        log.error("  ✗ Trades: %s", e)

    # 2. Portfolio
    log.info("Clearing PORTFOLIO table...")
    try:
        supabase.table("portfolio").delete().neq("ticker", "").execute()
        log.info("  ✓ Portfolio cleared.")
    except Exception as e:
        log.error("  ✗ Portfolio: %s", e)

    # 3. Performance
    log.info("Clearing PERFORMANCE table...")
    try:
        supabase.table("performance").delete().filter("total_value", "gte", 0).execute()
        log.info("  ✓ Performance cleared.")
    except Exception as e:
        log.error("  ✗ Performance: %s", e)

    # 4. Reset Account cash to starting balances
    log.info("Resetting ACCOUNT to $%.2f USD / ₹%.2f INR...", STARTING_USD, STARTING_INR)
    try:
        supabase.table("account").update({
            "cash_usd": STARTING_USD,
            "cash_inr": STARTING_INR
        }).eq("id", 1).execute()
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
