import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

_dotenv_path = Path(__file__).resolve().parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ===== SUPABASE (Python: direct Postgres, not the JS supabase-js client) =====
# JS:  createClient('https://ibmhrlcocptfjlwmrkdo.supabase.co', anonKey)
# Py:  psycopg.connect('postgresql://postgres:<password>@db.ibmhrlcocptfjlwmrkdo.supabase.co:5432/postgres')
#
# Set ONE of these (GitHub Actions: use the DATABASE_URL secret):
#   DATABASE_URL=postgresql://postgres:<url-encoded-password>@db.ibmhrlcocptfjlwmrkdo.supabase.co:5432/postgres
# or:
#   SUPABASE_DB_PASSWORD=<your database password>   (host/db/user below are filled in)
SUPABASE_PROJECT_REF = (os.environ.get("SUPABASE_PROJECT_REF") or "ibmhrlcocptfjlwmrkdo").strip()
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or f"https://{SUPABASE_PROJECT_REF}.supabase.co").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()  # only used by legacy JS/Streamlit code

SUPABASE_DB_HOST = (os.environ.get("SUPABASE_DB_HOST") or f"db.{SUPABASE_PROJECT_REF}.supabase.co").strip()
SUPABASE_DB_PORT = int(os.environ.get("SUPABASE_DB_PORT") or "5432")
SUPABASE_DB_NAME = (os.environ.get("SUPABASE_DB_NAME") or "postgres").strip()
SUPABASE_DB_USER = (os.environ.get("SUPABASE_DB_USER") or "postgres").strip()
SUPABASE_DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD") or ""

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
if not DATABASE_URL and SUPABASE_DB_PASSWORD:
    DATABASE_URL = (
        f"postgresql://{SUPABASE_DB_USER}:{quote(SUPABASE_DB_PASSWORD, safe='')}"
        f"@{SUPABASE_DB_HOST}:{SUPABASE_DB_PORT}/{SUPABASE_DB_NAME}"
    )

# ===== DISCORD =====
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

# ===== BOT MODE =====
# US market only, alert-only for now: analyse + Discord alert, never place/record trades.
MARKET = (os.environ.get("MARKET") or "US").strip().upper()
US_ONLY = MARKET == "US"
ALERT_ONLY = _env_bool("ALERT_ONLY", True)

# ===== CAPITAL =====
INITIAL_CAPITAL_USD = float(os.environ.get("INITIAL_CAPITAL_USD") or "258")
INITIAL_CASH_USD = INITIAL_CAPITAL_USD
INITIAL_CASH_INR = 0.0  # US-only mode

# ===== TRADING PARAMETERS =====
STOP_LOSS_US = 0.95  # 5% drop for US
STOP_LOSS_IN = 0.75  # 25% drop for India (unused while US_ONLY)
TAKE_PROFIT = 1.10
MIN_HOLD_DAYS = 7
MIN_REBUY_DAYS = 5
TOP_BUY_PICKS = 5
FUTURE_RETURN_DAYS = 5
MIN_PREDICTED_RETURN = 0.0
MIN_PREDICTED_RETURN_BUY = 0.01  # 1% minimum for new buys
INDUSTRY_CAP_US = 0.10  # 10% for US market
INDUSTRY_CAP_IN = 0.25  # 25% for Indian market

# Transaction Costs
COST_BUY = 1.001
COST_SELL = 0.999

# ===== DATA PARAMETERS =====
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FILTER_PERIOD = "6mo"
MIN_FILTER_ROWS = 100
MIN_AVG_VOLUME = 1_000_000
TOP_ML_COUNT = 50
BULK_CHUNK = 120
MAX_ML_WORKERS = 16

FEATURE_COLUMNS = [
    "returns",
    "MA20",
    "MA50",
    "momentum_5",
    "momentum_10",
    "momentum_20",
    "volatility_10",
    "volatility_20",
    "volume_change",
    "ma_ratio",
    "price_vs_ma",
]
