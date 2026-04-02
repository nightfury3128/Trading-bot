import yfinance as yf
from utils.logger import log

def get_currency(ticker: str) -> str:
    """Returns the currency for a given ticker."""
    if ticker.endswith(".NS"):
        return "INR"
    return "USD"

def get_market(ticker: str) -> str:
    """Returns the market for a given ticker."""
    if ticker.endswith(".NS"):
        return "INDIA"
    return "US"

def get_fx_rate() -> float:
    """Fetches the current USDINR exchange rate."""
    try:
        ticker = yf.Ticker("USDINR=X")
        # Get the most recent closing price
        hist = ticker.history(period="1d")
        if not hist.empty:
            rate = hist["Close"].iloc[-1]
            return float(rate)
        else:
            # Fallback if no data today (e.g. weekend)
            hist = ticker.history(period="5d")
            rate = hist["Close"].iloc[-1]
            return float(rate)
    except Exception as e:
        log.error("Error fetching FX rate: %s", e)
        # return a reasonable default or re-raise
        return 83.0 # Approximate fallback

def get_conversion_rates():
    """Returns inr_to_usd and usd_to_inr rates."""
    usdinr = get_fx_rate()
    log.info("USD/INR rate: %.2f", usdinr)
    return 1.0 / usdinr, usdinr

def normalize_to_usd(value: float, currency: str, inr_to_usd: float) -> float:
    """Normalizes a value to USD."""
    if currency == "INR":
        return value * inr_to_usd
    return value

def format_currency(value: float, currency: str, inr_to_usd: float = None) -> str:
    """Formats a value with the appropriate currency symbol and optional USD conversion."""
    if currency == "INR":
        s = f"₹{value:.2f}"
        if inr_to_usd:
            usd_val = value * inr_to_usd
            s += f" (~${usd_val:.2f})"
        return s
    return f"${value:.2f}"
