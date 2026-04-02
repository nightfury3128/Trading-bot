from datetime import datetime
from config import (
    TAKE_PROFIT,
    MIN_HOLD_DAYS,
    COST_SELL,
    COST_BUY,
    TOP_BUY_PICKS,
    MIN_PREDICTED_RETURN,
    MIN_PREDICTED_RETURN_BUY,
)
from utils.logger import log
from utils.time_utils import days_since, business_days_since
from db.portfolio import get_portfolio, remove_position, add_position
from db.trades import log_trade, get_recent_sells
from strategy.risk import calculate_industry_exposures, check_industry_cap
from utils.currency import get_currency, get_conversion_rates, normalize_to_usd
from strategy import us_strategy, india_strategy


def get_strategy(ticker):
    """Routing logic for market-specific strategies."""
    if ticker.endswith(".NS"):
        return india_strategy
    else:
        return us_strategy


def run_sell_phase(positions: dict, prices: dict, scores: dict, cash: float, vol_map: dict = None) -> float:
    """Evaluates and executes SELL rules routing to US/India strategies."""
    log.info("---------- SELL PHASE ----------")
    
    inr_to_usd, usd_to_inr = get_conversion_rates()

    for ticker, pos in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue

        strategy = get_strategy(ticker)
        score = scores.get(ticker)
        vol = vol_map.get(ticker, 0.02) if vol_map else 0.02
        
        sell_reason, proceeds = strategy.handle_sell(ticker, pos, price, score, volatility=vol)
        
        if sell_reason:
            # Normalize proceeds to USD for the cash balance if needed
            currency = get_currency(ticker)
            proceeds_usd = normalize_to_usd(proceeds, currency, inr_to_usd)
            cash += proceeds_usd
            log.info("Execution: %s Sold %s for %.2f (%s) -> Normalized: $%.2f", 
                     currency, ticker, proceeds, currency, proceeds_usd)

    return cash


def run_buy_phase(
    top_picks: list[tuple[str, float]],
    prices: dict,
    scores: dict,
    cash: float,
    portfolio: list,
    base_currency: str = "USD",
    other_cash: float = 0.0,
    vol_map: dict[str, float] | None = None
) -> float:
    """Evaluates and executes BUY rules using the UNIFIED ALLOCATOR."""
    log.info("---------- SMART BUY PHASE (%s) ----------", base_currency)
    
    from strategy.allocator import allocate_portfolio
    from utils.notifications import send_discord
    inr_to_usd, usd_to_inr = get_conversion_rates()
    
    if not top_picks:
        log.info("No candidates for Buy phase.")
        return cash

    # 1. PRE-FILTER: Filter candidates to ONLY include current market + not in portfolio
    market_portfolio_tickers = [p["ticker"] for p in portfolio if (base_currency == "INR" and p["ticker"].endswith(".NS")) or (base_currency == "USD" and not p["ticker"].endswith(".NS"))]
    
    # Filter candidates: must match market and not be already owned
    candidates = []
    for t, s in top_picks:
        is_in_market = (base_currency == "INR" and t.endswith(".NS")) or (base_currency == "USD" and not t.endswith(".NS"))
        if is_in_market and t not in market_portfolio_tickers:
            candidates.append(t)
            
    if not candidates:
        log.info("All candidates already in portfolio or wrong market.")
        return cash

    # 2. RUN UNIFIED ALLOCATOR
    # Passing Price * COST_BUY to ensure accurate share counts after commissions
    prices_with_cost = {t: prices[t] * COST_BUY for t in candidates if t in prices}
    
    alloc_result = allocate_portfolio(
        tickers=candidates,
        predictions=scores,
        volatilities=vol_map or {},
        prices=prices_with_cost,
        total_capital=cash,
        market=base_currency
    )
    
    if not alloc_result:
        log.info("Allocator returned no allocations.")
        return cash

    # 3. EXECUTE TRADES
    for ticker, info in alloc_result.items():
        shares = float(info.get("shares", 0))
        cost_local = float(info.get("allocation", 0))
        
        if shares <= 0:
            log.info("Skipped %s: zero or unfilled allocation", ticker)
            continue

        price = prices.get(ticker)
        if price is None: continue

        currency = get_currency(ticker)
        execution_price_local = price * COST_BUY
        # Final safety check vs cash
        if cost_local > cash + 0.01:
            log.warning("Allocation exceeds cash for %s. Capping.", ticker)
            cost_local = cash
            shares = cost_local / execution_price_local
            if ticker.endswith(".NS"): shares = float(int(shares))
            if shares <= 0: continue
            cost_local = shares * execution_price_local

        cost_usd = normalize_to_usd(cost_local, currency, inr_to_usd)

        cash -= cost_local
        cash = max(0.0, cash)

        # Strategy Overrides (e.g. India stop-loss)
        risk_level, stop_loss = None, None
        if ticker.endswith(".NS"):
            volatility = float(vol_map.get(ticker, 0.02)) if vol_map else 0.02
            risk_level, stop_loss = india_strategy.get_india_risk_and_stop_loss(volatility)

        add_position(
            ticker, 
            shares, 
            execution_price_local, 
            currency=currency, 
            local_val=cost_local, 
            usd_val=cost_usd,
            risk_level=risk_level,
            stop_loss=stop_loss,
        )
        log_trade("BUY", ticker, execution_price_local, shares)
        
        # Log and Alert
        weight_pct = info.get("weight", 0) * 100
        log.info("SMART ALLOCATION: %s | Weight: %.1f%% | Capital: %.2f %s | Shares: %.4f", 
                    ticker, weight_pct, cost_local, currency, shares)
        
        try:
            msg = f"🛒 **SMART BUY**: {ticker}\n• Weight: {weight_pct:.1f}%\n• Allocated: {cost_local:.2f} {currency}\n• Units: {shares:.4f}"
            send_discord(msg)
        except: pass

    return cash


