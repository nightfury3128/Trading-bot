from datetime import datetime
from config import STOP_LOSS, TAKE_PROFIT, MIN_HOLD_DAYS, COST_SELL, COST_BUY
from utils.logger import log
from utils.time_utils import business_days_since
from db.portfolio import remove_position, add_position
from db.trades import log_trade

def handle_sell(ticker, pos, price, score):
    """Executes US market sell logic with strict rules."""
    hold_days = business_days_since(pos["buy_date"])
    buy_price = float(pos["buy_price"])
    shares = float(pos["shares"])
    today = datetime.now().strftime("%Y-%m-%d")

    # Rule: Strict No Day-Trading (Explicit same-day block)
    if today == pos["buy_date"]:
        log.info("Sell blocked on %s (US): same-day check (No intraday trading allowed)", ticker)
        return None, 0.0

    # Rule: MIN_HOLD_DAYS check MUST pass before any exit logic
    if hold_days < MIN_HOLD_DAYS:
        log.info("Sell blocked on %s (US) due to MIN_HOLD_DAYS. Days held: %d/%d", ticker, hold_days, MIN_HOLD_DAYS)
        return None, 0.0

    sell_reason = None
    if price < buy_price * STOP_LOSS:
        sell_reason = "STOP_LOSS"
    elif price > buy_price * TAKE_PROFIT:
        sell_reason = "TAKE_PROFIT"
    elif score is not None and score < 0.4:
        sell_reason = "MODEL_SELL"

    if sell_reason:
        execution_price = price * COST_SELL
        proceeds = shares * execution_price
        log_trade(sell_reason, ticker, execution_price, shares)
        remove_position(ticker)
        log.info("Execution (US): Sold %s: %s @ %.2f (proceeds %.2f)", ticker, sell_reason, execution_price, proceeds)
        return sell_reason, proceeds

    return None, 0.0

def handle_buy(ticker, execution_price, shares):
    """Executes US market buy logic."""
    add_position(ticker, shares, execution_price)
    log_trade("BUY", ticker, execution_price, shares)
    log.info("Bought %s (US): %.4f shares @ %.2f", ticker, shares, execution_price)
