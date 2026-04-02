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


def run_sell_phase(positions: dict, prices: dict, scores: dict, cash: float) -> float:
    """Evaluates and executes SELL rules routing to US/India strategies."""
    log.info("---------- SELL PHASE ----------")
    
    inr_to_usd, usd_to_inr = get_conversion_rates()

    for ticker, pos in list(positions.items()):
        price = prices.get(ticker)
        if price is None:
            continue

        strategy = get_strategy(ticker)
        score = scores.get(ticker)
        
        sell_reason, proceeds = strategy.handle_sell(ticker, pos, price, score)
        
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
    """Evaluates and executes BUY rules with multi-currency handling."""
    log.info("---------- BUY PHASE (%s) ----------", base_currency)
    
    from config import INDUSTRY_CAP_US, INDUSTRY_CAP_IN
    from strategy.risk import get_industry
    inr_to_usd, usd_to_inr = get_conversion_rates()
    market_cap = INDUSTRY_CAP_IN if base_currency == "INR" else INDUSTRY_CAP_US
    
    # Rule 7: "Low Activity" Filter
    if top_picks:
        best_ticker, _ = top_picks[0]
        best_pred = scores.get(best_ticker, 0.0)
        if best_pred < MIN_PREDICTED_RETURN_BUY:
            log.info("Skipping trades due to low signal: best prediction (%.2f%%) < required (%.2f%%)", 
                     best_pred * 100, MIN_PREDICTED_RETURN_BUY * 100)
            return cash

    # SEPARATE MARKET RISK: Filter portfolio to ONLY include current market tickers
    market_portfolio = [p for p in portfolio if (base_currency == "INR" and p["ticker"].endswith(".NS")) or (base_currency == "USD" and not p["ticker"].endswith(".NS"))]
    positions_map = {p["ticker"]: p for p in market_portfolio}
    
    # Local market value and exposure calculation
    total_market_value_local = 0.0
    industry_exposure_local = {}
    for t, pos in positions_map.items():
        px = prices.get(t, float(pos.get("buy_price", 0)))
        val = float(pos.get("shares", 0)) * px
        total_market_value_local += val
        ind = get_industry(t)
        industry_exposure_local[ind] = industry_exposure_local.get(ind, 0.0) + val
    
    # Current pool AUM (Cash + Market Positions)
    total_market_value_local += cash

    log.info("Total %s Market Capital: %.2f", base_currency, total_market_value_local)
    
    if not top_picks:
        log.info("No picks provided for Buy phase.")
        return cash

    remaining_risk_score = sum(rs for _, rs in top_picks)

    for ticker, rs in top_picks:
        # Buffer check in local currency (roughly equivalent to $5.1 USD)
        buffer = 5.1 if base_currency == "USD" else 5.1 * usd_to_inr
        if cash <= buffer:
            log.info("Skipped %s: out of cash (%.2f remaining)", ticker, cash)
            break

        price = prices.get(ticker)
        if price is None:
            remaining_risk_score -= rs
            continue

        # Sizing relative to THIS pool only
        weight = rs / remaining_risk_score if remaining_risk_score > 0 else 1.0
        allocation_local = min(
            cash * weight, 
            total_market_value_local * (market_cap * 0.95)
        )
        allocation_usd = normalize_to_usd(allocation_local, base_currency, inr_to_usd)
            
        if allocation_local < (5.1 if base_currency == "USD" else 5.1 * usd_to_inr):
            log.info("Skipped %s: allocation too small (%.2f %s)", ticker, allocation_local, base_currency)
            remaining_risk_score -= rs
            continue

        # Industry Cap Check (using local market values and local cap)
        ind = get_industry(ticker)
        curr_ind_exp = industry_exposure_local.get(ind, 0.0)
        if (curr_ind_exp + allocation_local) / total_market_value_local > market_cap:
            log.info("Skipped %s: %s industry cap exceeded (%.2f%% > %.0f%%)", 
                     ticker, ind, ((curr_ind_exp + allocation_local) / total_market_value_local) * 100, market_cap * 100)
            remaining_risk_score -= rs
            continue

        currency = get_currency(ticker)
        
        # NOTE: Since pools are separate, we expect ticker currency to match base_currency 
        # or we might need explicit conversion if they differ. 
        # For now, if ticker is INR and base is INR, execution_price is in INR.
        
        # Execute Buy
        execution_price_local = price * COST_BUY
        shares = float(allocation_local / execution_price_local)
        
        # Rule: Indian market does not allow fractional shares
        if ticker.endswith(".NS"):
            shares = float(int(shares))
            if shares == 0:
                log.info("Skipped %s: allocation not enough for 1 full share", ticker)
                remaining_risk_score -= rs
                continue
                
        cost_local = shares * execution_price_local
        cost_usd = normalize_to_usd(cost_local, currency, inr_to_usd)

        if cost_local <= cash + 1e-6:
            cash -= cost_local
            cash = max(0.0, cash)
            remaining_risk_score -= rs

            risk_level = None
            stop_loss = None
            # India-only: compute and persist volatility-based stop-loss.
            if ticker.endswith(".NS"):
                volatility = float(vol_map.get(ticker, 0.02)) if vol_map else 0.02
                risk_level, stop_loss = india_strategy.get_india_risk_and_stop_loss(volatility)
                log.info(f"Ticker {ticker} risk={risk_level} stop_loss={stop_loss:.2f}")

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

            # Update industry tracking for next picks (Local)
            ind = get_industry(ticker)
            industry_exposure_local[ind] = industry_exposure_local.get(ind, 0.0) + cost_local

            log.info("Bought %s: %.4f shares @ %.2f (%s)", 
                     ticker, shares, execution_price_local, currency)
        else:
            log.info("Skipped %s: insufficient local cash", ticker)
            remaining_risk_score -= rs

    return cash


