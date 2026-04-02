import os
from pathlib import Path
from dotenv import load_dotenv

_dotenv_path = Path(__file__).resolve().parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

# ===== SUPABASE =====
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()

# ===== DISCORD =====
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")

# ===== TRADING PARAMETERS =====
STOP_LOSS = 0.95
TAKE_PROFIT = 1.10
MIN_HOLD_DAYS = 7
MIN_REBUY_DAYS = 5
TOP_BUY_PICKS = 5
FUTURE_RETURN_DAYS = 5
MIN_PREDICTED_RETURN = 0.0
MIN_PREDICTED_RETURN_BUY = 0.01  # 1% minimum for new buys
INDUSTRY_CAP = 0.10  # 10%

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
