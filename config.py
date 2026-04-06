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
STOP_LOSS_US = 0.95 # 5% drop for US
STOP_LOSS_IN = 0.75 # 25% drop for India
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

# ===== INTRADAY PARAMETERS (India) =====
INTRADAY_STOP_LOSS_PCT = 0.02       # 2% stop loss
INTRADAY_PROFIT_TARGET_PCT = 0.02   # 2% profit target
INTRADAY_SWING_STOP_LOSS_PCT = 0.07 # 7% stop loss after conversion to swing
INTRADAY_COOLDOWN_MINUTES = 15      # Minimum minutes between trades per ticker
INTRADAY_CAPITAL_FRACTION = 0.30    # Max 30% of India cash for intraday
INTRADAY_CONVERSION_MIN_PNL = 0.01         # 1% PnL required for swing conversion
INTRADAY_CONVERSION_MIN_CONFIDENCE = 0.60  # Model confidence required for conversion

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
