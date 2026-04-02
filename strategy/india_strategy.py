from config import STOP_LOSS_IN, TAKE_PROFIT, COST_SELL, COST_BUY
from utils.logger import log
from db.portfolio import remove_position, add_position
from db.trades import log_trade

RISK_STOP_LOSS_MAP = {
    "LOW": 0.50,
    "MEDIUM": 0.75,
    "HIGH": 0.85,
}


def classify_india_risk(volatility: float) -> str:
    """Classify India risk level from volatility metric."""
    # Volatility thresholds per spec.
    if volatility < 0.02:
        return "LOW"
    if volatility < 0.05:
        return "MEDIUM"
    return "HIGH"


def get_india_stop_loss(risk_level: str) -> float:
    """Map risk level to stop-loss multiplier."""
    return float(RISK_STOP_LOSS_MAP.get(risk_level, STOP_LOSS_IN))


def get_india_risk_and_stop_loss(volatility: float) -> tuple[str, float]:
    """Compute (risk_level, stop_loss) from volatility."""
    risk_level = classify_india_risk(float(volatility))
    stop_loss = get_india_stop_loss(risk_level)
    return risk_level, stop_loss


def handle_sell(ticker, pos, price, score):
    """Executes India market sell logic with relaxed rules."""
    buy_price = float(pos["buy_price"])
    shares = float(pos["shares"])

    # India specific: Allow immediate sell if signals trigger
    sell_reason = None

    # Risk-based stop-loss (stored at buy time in portfolio).
    # Fallback to STOP_LOSS_IN if older positions don't have stop_loss yet.
    stop_loss = float(pos.get("stop_loss", STOP_LOSS_IN))

    if ticker.endswith(".NS") and price < buy_price * stop_loss:
        log.info(f"Stop loss triggered for {ticker}")
        sell_reason = "STOP_LOSS"
    elif price > buy_price * TAKE_PROFIT:
        sell_reason = "TAKE_PROFIT"
    elif score is not None and score < 0.4:
        # We already passed any hold_days check if we were using it, but India doesn't strictly need it
        sell_reason = "MODEL_SELL"

    if sell_reason:
        execution_price = price * COST_SELL
        proceeds = shares * execution_price
        pnl = (execution_price - buy_price) * shares
        pnl_pct = ((execution_price / buy_price) - 1) * 100
        
        log_trade(sell_reason, ticker, execution_price, shares, pnl=pnl, pnl_pct=pnl_pct)
        remove_position(ticker)
        log.info("Execution (India): Sold %s: %s @ %.2f (proceeds %.2f, P/L %.2f)", ticker, sell_reason, execution_price, proceeds, pnl)
        return sell_reason, proceeds

    return None, 0.0

def handle_buy(ticker, execution_price, shares):
    """Executes India market buy logic."""
    add_position(ticker, shares, execution_price)
    log_trade("BUY", ticker, execution_price, shares)
    log.info("Bought %s (India): %.4f shares @ %.2f", ticker, shares, execution_price)
