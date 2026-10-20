"""Direct Postgres connection to Supabase (Python equivalent of the JS setup).

JS (supabase-js) uses the REST endpoint + anon key:
    createClient('https://ibmhrlcocptfjlwmrkdo.supabase.co', SUPABASE_KEY)

Python here uses the database connection string directly via psycopg:
    postgresql://postgres:[YOUR-PASSWORD]@db.ibmhrlcocptfjlwmrkdo.supabase.co:5432/postgres

Provide it as the DATABASE_URL env var / GitHub secret (percent-encode any
special characters in the password), or set SUPABASE_DB_PASSWORD and the
host/port/db/user defaults in config.py are used to build it.

This module keeps its historic name so existing `db.*` imports don't break,
but it no longer uses the supabase-py PostgREST client.
"""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlparse

from config import DATABASE_URL
from utils.logger import log

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - exercised only without deps installed
    psycopg = None
    dict_row = None


def _normalize(value):
    """Convert Postgres types to the plain types the rest of the bot expects."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def normalize_row(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {k: _normalize(v) for k, v in row.items()}


@contextmanager
def get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Run: pip install -r requirements.txt")
    if not DATABASE_URL:
        raise RuntimeError(
            "No Supabase database connection configured. Set DATABASE_URL="
            "'postgresql://postgres:<password>@db.ibmhrlcocptfjlwmrkdo.supabase.co:5432/postgres' "
            "(locally in .env, in GitHub as the DATABASE_URL secret), or set SUPABASE_DB_PASSWORD."
        )
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)
    except psycopg.OperationalError as e:
        host = urlparse(DATABASE_URL).hostname or ""
        if host.startswith("db.") and host.endswith(".supabase.co"):
            raise RuntimeError(
                f"Cannot reach the direct Supabase host {host}: it is IPv6-only and this "
                "network (e.g. GitHub Actions) is IPv4-only. Replace the DATABASE_URL secret "
                "with the Session pooler string from Supabase -> Connect -> Session pooler "
                "(host *.pooler.supabase.com, port 5432, user postgres.ibmhrlcocptfjlwmrkdo), "
                "or set SUPABASE_POOLER_HOST + SUPABASE_DB_PASSWORD instead."
            ) from e
        raise RuntimeError(
            f"Cannot connect to Supabase Postgres at {host or 'unknown host'}: {e}"
        ) from e
    with conn:
        yield conn


def fetch_all(sql: str, params: tuple | dict = ()) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [normalize_row(r) for r in rows]


def fetch_one(sql: str, params: tuple | dict = ()) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return normalize_row(row)


def execute(sql: str, params: tuple | dict = ()) -> None:
    with get_connection() as conn:
        conn.execute(sql, params)


if not DATABASE_URL:
    log.warning("DATABASE_URL not set. Supabase (Postgres) operations will fail!")
