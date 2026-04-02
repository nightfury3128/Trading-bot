from datetime import datetime
from config import (
    STOP_LOSS,
    TAKE_PROFIT,
    MIN_HOLD_DAYS,
    COST_SELL,
    COST_BUY,
    TOP_BUY_PICKS,
    MIN_PREDICTED_RETURN,
    INDUSTRY_CAP,
)
from utils.logger import log
from utils.time_utils import days_since
from db.portfolio import get_portfolio, remove_position, add_position
from db.trades import log_trade, get_recent_sells
from strategy.risk import calculate_industry_exposures, check_industry_cap


def run_sell_phase(positions: dict, prices: dict, scores: dict, cash: float) -> float:
    """Evaluates and executes SELL rules. Returns updated cash."""
    log.info("---------- SELL PHASE ----------")

    for ticker, pos in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue

        hold_days = days_since(pos["buy_date"])
        buy_price = float(pos["buy_price"])
        shares = float(pos["shares"])

        # Rule 11: Strict No Day-Trading
        if datetime.now().strftime("%Y-%m-%d") == pos["buy_date"]:
            log.info("SELL skip %s: bought today (Day-trading protection)", ticker)
            continue

        sell_reason = None
        if price < buy_price * STOP_LOSS:
            sell_reason = "STOP_LOSS"
        elif price > buy_price * TAKE_PROFIT:
            sell_reason = "TAKE_PROFIT"
        elif ticker in scores and scores[ticker] < 0.4 and hold_days >= MIN_HOLD_DAYS:
            sell_reason = "MODEL_SELL"

        if sell_reason:
            execution_price = price * COST_SELL
            proceeds = shares * execution_price
            cash += proceeds
            log_trade(sell_reason, ticker, execution_price, shares)
            remove_position(ticker)
            log.info(
                "Sold %s: %s @ %.2f (proceeds %.2f)",
                ticker,
                sell_reason,
                execution_price,
                proceeds,
            )

    return cash


def run_buy_phase(
    top_picks: list[tuple[str, float]],
    prices: dict,
    scores: dict,
    cash: float,
    portfolio: list,
) -> float:
    """Evaluates and executes BUY rules. Returns updated cash."""
    log.info("---------- BUY PHASE ----------")

    positions = {p["ticker"]: p for p in portfolio}
    cooldown_tickers = get_recent_sells()

    # Calculate industry limits
    total_portfolio_value, industry_exposure = calculate_industry_exposures(
        positions, prices
    )
    total_portfolio_value += cash  # Total value for sizing includes current cash

    log.info("Total Portfolio Value for Sizing: $%.2f", total_portfolio_value)
    log.info("Current Industry Exposures: %s", industry_exposure)

    if not top_picks:
        log.info("No picks provided for Buy phase.")
        return cash

    remaining_risk_score = sum(rs for _, rs in top_picks)

    for ticker, rs in top_picks:
        if cash <= 5.1:  # Buffer for transaction costs
            log.info("Skipped %s: out of cash ($%.2f remaining)", ticker, cash)
            break

        price = prices.get(ticker)
        if price is None:
            remaining_risk_score -= rs
            continue

        weight = rs / remaining_risk_score if remaining_risk_score > 0 else 1.0
        allocation = cash * weight

        if allocation < 5.0:
            log.info("Skipped %s: allocation too small ($%.2f)", ticker, allocation)
            remaining_risk_score -= rs
            continue

        # Industry Cap Check
        if not check_industry_cap(
            ticker, allocation, total_portfolio_value, industry_exposure, INDUSTRY_CAP
        ):
            remaining_risk_score -= rs
            continue

        # Execute Buy
        execution_price = price * COST_BUY
        shares = float(allocation / execution_price)
        cost = shares * execution_price

        if cost <= cash + 1e-6:
            cash -= cost
            cash = max(0.0, cash)
            remaining_risk_score -= rs

            add_position(ticker, shares, execution_price)
            log_trade("BUY", ticker, execution_price, shares)

            # Update industry tracking for next picks in this same run
            from strategy.risk import get_industry

            ind = get_industry(ticker)
            industry_exposure[ind] = industry_exposure.get(ind, 0.0) + cost

            log.info(
                "Bought %s: %.4f shares @ %.2f (cost %.2f)",
                ticker,
                shares,
                execution_price,
                cost,
            )
            log.info(
                "DEBUG BUY | Pred Return: %.4f | Alloc: $%.2f | Cash Remaining: $%.2f",
                scores[ticker],
                allocation,
                cash,
            )
        else:
            log.info("Skipped %s: insufficient cash for %.4f shares", ticker, shares)
            remaining_risk_score -= rs

    return cash
