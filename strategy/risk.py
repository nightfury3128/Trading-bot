import yfinance as yf
from utils.logger import log


def get_industry(ticker: str) -> str:
    """Fetch sector/industry mapping from Yahoo Finance."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception as e:
        log.debug("get_industry error %s: %s", ticker, e)
        return "Unknown"


def calculate_industry_exposures(
    positions: dict, prices: dict, inr_to_usd: float = 1.0
) -> tuple[float, dict[str, float]]:
    """Calculate total portfolio value and current industry exposures, normalized to USD."""
    from utils.currency import normalize_to_usd, get_currency
    total_portfolio_value_usd = 0.0
    industry_exposure_usd = {}

    for ticker, pos in positions.items():
        px = prices.get(ticker, float(pos.get("buy_price", 0)))
        currency = pos.get("currency", get_currency(ticker))
        
        local_val = float(pos.get("shares", 0)) * px
        usd_val = normalize_to_usd(local_val, currency, inr_to_usd)
        
        total_portfolio_value_usd += usd_val
        ind = get_industry(ticker)
        industry_exposure_usd[ind] = industry_exposure_usd.get(ind, 0.0) + usd_val

    return total_portfolio_value_usd, industry_exposure_usd


def check_industry_cap(
    ticker: str,
    allocation: float,
    total_portfolio_value: float,
    industry_exposure: dict,
    cap: float = 0.10,
) -> bool:
    """True if trade is within cap, False otherwise."""
    if total_portfolio_value <= 0:
        return True

    ind = get_industry(ticker)
    projected_ind_value = industry_exposure.get(ind, 0.0) + allocation
    projected_weight = projected_ind_value / total_portfolio_value

    if projected_weight > cap:
        log.info(
            "Skipped %s: industry cap exceeded (%s at %.2f%%)",
            ticker,
            ind,
            projected_weight * 100,
        )
        return False

    return True
