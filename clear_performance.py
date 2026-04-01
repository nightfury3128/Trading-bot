#!/usr/bin/env python3
"""Delete all rows from public.performance via Supabase REST.

Loads .env next to this script; needs SUPABASE_URL and SUPABASE_KEY.
PostgREST needs a filter; we use date >= 1900-01-01 which matches typical rows.

If this fails with 401/403, use the SQL Editor instead:
    DELETE FROM public.performance;
    -- or: TRUNCATE public.performance RESTART IDENTITY;
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


def main() -> None:
    dotenv_path = Path(__file__).resolve().parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_KEY") or "").strip()
    if not url or not key:
        print(
            "Missing SUPABASE_URL / SUPABASE_KEY (set env vars or create .env; see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    sb = create_client(url, key)
    res = sb.table("performance").delete().gte("date", "1900-01-01").execute()
    # returned body may be empty for delete
    print("delete request finished; check Supabase Table Editor for performance count.")


if __name__ == "__main__":
    main()
