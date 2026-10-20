"""Create the bot's tables (if missing) and seed the $258 starting account.

Usage:  python -m db.init_db
Requires DATABASE_URL (or SUPABASE_DB_PASSWORD) — see config.py.
"""
from pathlib import Path

from config import INITIAL_CAPITAL_USD
from db.supabase_client import get_connection
from utils.logger import log


def init_db() -> None:
    schema = (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.execute(schema)
    log.info("Supabase tables ready. Account id=1 seeded with $%.2f if it was missing.", INITIAL_CAPITAL_USD)


if __name__ == "__main__":
    init_db()
