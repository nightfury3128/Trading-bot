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
    positions: dict, prices: dict
) -> tuple[float, dict[str, float]]:
    """Calculate total portfolio value and current industry exposures."""
    total_portfolio_value = 0.0
    industry_exposure = {}

    for ticker, pos in positions.items():
        px = prices.get(ticker, float(pos["buy_price"]))
        val = float(pos["shares"]) * px
        total_portfolio_value += val

        ind = get_industry(ticker)
        industry_exposure[ind] = industry_exposure.get(ind, 0.0) + val

    return total_portfolio_value, industry_exposure


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
