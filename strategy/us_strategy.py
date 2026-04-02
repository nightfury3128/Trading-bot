from datetime import datetime
from config import STOP_LOSS_US, TAKE_PROFIT, MIN_HOLD_DAYS, COST_SELL, COST_BUY
from utils.logger import log
from utils.time_utils import business_days_since
from db.portfolio import remove_position, add_position, update_position
from db.trades import log_trade

def handle_sell(ticker, pos, price, score, volatility=0.02):
    """Executes US market sell logic with a multi-condition exit system."""
    hold_days = business_days_since(pos["buy_date"])
    buy_price = float(pos["buy_price"])
    shares = float(pos["shares"])
    today = datetime.now().strftime("%Y-%m-%d")
    pred = float(score if score is not None else 0.0)
    pnl_pct_current = ((price / buy_price) - 1)

    # Rule: Strict No Day-Trading (Explicit same-day block)
    if today == pos["buy_date"]:
        log.info("Sell blocked on %s (US): same-day check (No intraday trading allowed)", ticker)
        return None, 0.0

    # Rule: MIN_HOLD_DAYS check MUST pass before any exit logic
    if hold_days < MIN_HOLD_DAYS:
        log.info("Sell blocked on %s (US) due to MIN_HOLD_DAYS. Days held: %d/%d", ticker, hold_days, MIN_HOLD_DAYS)
        return None, 0.0

    sell_reason = None
    
    # 1. HARD STOP LOSS (ALWAYS FIRST)
    # Stop loss logic overrides EVERYTHING, even positive signals
    stop_loss_val = float(pos.get("stop_loss", STOP_LOSS_US))
    if price < buy_price * stop_loss_val:
        sell_reason = "STOP_LOSS"
    
    # Strong Positive Signal Exception: Always hold winners with high confidence
    elif pred > 0.2:
        log.info("Hold %s (US): Strong positive signal (%.2f%%)", ticker, pred * 100)
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

        shares_to_sell = shares * sell_fraction
        # Ensure we don't end up with dust positions
        remaining_shares = shares - shares_to_sell
        
        if remaining_shares < (shares * 0.05) or remaining_shares * price < 5.0:
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
            log.info("Execution (US): Partial %s %s @ %.2f (sold %.1f%%, remaining %.4f shares)", 
                     sell_reason, ticker, execution_price, sell_fraction*100, remaining_shares)
        else:
            remove_position(ticker)
            log.info("Execution (US): Full %s %s @ %.2f (proceeds %.2f, P/L %.2f)", 
                     sell_reason, ticker, execution_price, proceeds, realized_pnl)
            
        return sell_reason, proceeds

    return None, 0.0

    return None, 0.0

def handle_buy(ticker, execution_price, shares):
    """Executes US market buy logic."""
    add_position(ticker, shares, execution_price)
    log_trade("BUY", ticker, execution_price, shares)
    log.info("Bought %s (US): %.4f shares @ %.2f", ticker, shares, execution_price)
