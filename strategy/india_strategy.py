from config import STOP_LOSS, TAKE_PROFIT, COST_SELL, COST_BUY
from utils.logger import log
from db.portfolio import remove_position, add_position
from db.trades import log_trade

def handle_sell(ticker, pos, price, score):
    """Executes India market sell logic with relaxed rules."""
    buy_price = float(pos["buy_price"])
    shares = float(pos["shares"])

    # India specific: Allow immediate sell if signals trigger
    sell_reason = None
    if price < buy_price * STOP_LOSS:
        sell_reason = "STOP_LOSS"
    elif price > buy_price * TAKE_PROFIT:
        sell_reason = "TAKE_PROFIT"
    elif score is not None and score < 0.4:
        # We already passed any hold_days check if we were using it, but India doesn't strictly need it
        sell_reason = "MODEL_SELL"

    if sell_reason:
        execution_price = price * COST_SELL
        proceeds = shares * execution_price
        log_trade(sell_reason, ticker, execution_price, shares)
        remove_position(ticker)
        log.info("Execution (India): Sold %s: %s @ %.2f (proceeds %.2f)", ticker, sell_reason, execution_price, proceeds)
        return sell_reason, proceeds

    return None, 0.0

def handle_buy(ticker, execution_price, shares):
    """Executes India market buy logic."""
    add_position(ticker, shares, execution_price)
    log_trade("BUY", ticker, execution_price, shares)
    log.info("Bought %s (India): %.4f shares @ %.2f", ticker, shares, execution_price)
