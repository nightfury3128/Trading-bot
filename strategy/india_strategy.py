from config import STOP_LOSS_IN, TAKE_PROFIT, COST_SELL, COST_BUY
from utils.logger import log
from db.portfolio import remove_position, add_position, update_position
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


def handle_sell(ticker, pos, price, score, volatility=0.02):
    """Executes India market sell logic with a multi-condition exit system."""
    buy_price = float(pos["buy_price"])
    shares = float(pos["shares"])
    pred = float(score if score is not None else 0.0)
    pnl_pct_current = ((price / buy_price) - 1)

    sell_reason = None
    
    # Risk-based stop-loss fallback
    stop_loss = float(pos.get("stop_loss", STOP_LOSS_IN))

    # 1. HARD STOP LOSS (ALWAYS FIRST)
    # Stop loss logic overrides EVERYTHING, even positive signals
    if price < buy_price * stop_loss:
        sell_reason = "STOP_LOSS"

    # Strong Positive Signal Exception: Always hold winners with high confidence
    elif pred > 0.2:
        log.info("Hold %s (India): Strong positive signal (%.2f%%)", ticker, pred * 100)
        return None, 0.0

    # 2. STRONG NEGATIVE SIGNAL
    elif pred < -0.01:
        sell_reason = "NEGATIVE_SIGNAL"
    # 3. WEAK SIGNAL + LOSING POSITION
    elif pred < 0.1 and pnl_pct_current < 0:
        sell_reason = "RISK_REDUCTION"
    # 4. WEAK SIGNAL + PROFIT
    elif pred < 0.1 and pnl_pct_current > 0:
        sell_reason = "PROFIT_LOCK"
    # 5. STRONG PROFIT PROTECTION
    elif pnl_pct_current > 0.10:
        sell_reason = "PROFIT_LOCK"

    if sell_reason:
        # Dynamic Sell Fraction Logic
        risk_score = min(max(float(volatility), 0), 1)
        base = 0.2
        risk_adjustment = min(risk_score * 2, 0.4)
        signal_adjustment = max(0, -pred * 2)
        
        sell_fraction = base + risk_adjustment + signal_adjustment
        
        # Priority Weight Adjustments
        if sell_reason == "STOP_LOSS":
            sell_fraction = min(1.0, sell_fraction + 0.3)
        if sell_reason == "NEGATIVE_SIGNAL" and pred < -0.05:
            sell_fraction = max(sell_fraction, 0.8)
            
        # Rule 6: DO NOT SELL WINNERS TOO EARLY
        if pnl_pct_current > 0 and pred > 0:
            sell_fraction *= 0.5
            
        sell_fraction = min(max(sell_fraction, 0.1), 1.0)
        
        log.info(f"Sell triggered for {ticker}: {sell_reason}")
        log.info(f"PnL: {pnl_pct_current*100:+.2f}%, Pred: {pred*100:.2f}%, Vol: {volatility:.4f}")
        log.info(f"Dynamic fraction: {sell_fraction*100:.1f}%")

        shares_to_sell = float(int(shares * sell_fraction))
        if shares_to_sell == 0 and sell_fraction > 0:
            shares_to_sell = 1.0 # Sell at least 1 share
            
        remaining_shares = shares - shares_to_sell
        
        # India Dust: ₹500 threshold
        if remaining_shares < 1.0 or remaining_shares * price < 500.0:
            sell_fraction = 1.0
            shares_to_sell = shares
            remaining_shares = 0

        execution_price = price * COST_SELL
        proceeds = shares_to_sell * execution_price
        
        # Realized PNL for the chunk being sold
        realized_pnl = (execution_price - buy_price) * shares_to_sell
        pnl_pct_realized = ((execution_price / buy_price) - 1) * 100
        
        log_trade(sell_reason, ticker, execution_price, shares_to_sell, pnl=realized_pnl, pnl_pct=pnl_pct_realized, 
                  entry_price=buy_price, entry_date=pos["buy_date"], remaining_shares=remaining_shares)
        
        if remaining_shares > 0:
            update_position(ticker, remaining_shares, execution_price)
            log.info("Execution (India): Partial %s %s @ %.2f (sold %d shares, remaining %d)", 
                     sell_reason, ticker, execution_price, int(shares_to_sell), int(remaining_shares))
        else:
            remove_position(ticker)
            log.info("Execution (India): Full %s %s @ %.2f (proceeds %.2f, P/L %.2f)", 
                     sell_reason, ticker, execution_price, proceeds, realized_pnl)
            
        return sell_reason, proceeds

    return None, 0.0

    return None, 0.0

def handle_buy(ticker, execution_price, shares):
    """Executes India market buy logic."""
    add_position(ticker, shares, execution_price)
    log_trade("BUY", ticker, execution_price, shares)
    log.info("Bought %s (India): %.4f shares @ %.2f", ticker, shares, execution_price)
