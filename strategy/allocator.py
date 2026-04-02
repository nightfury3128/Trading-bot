from utils.logger import log
from strategy.risk import get_industry
import numpy as np

def allocate_portfolio(tickers, predictions, volatilities, prices, total_capital, market="US"):
    """
    Unified Portfolio Allocator for US and Indian Markets.
    - US: Fractional shares, full deployment.
    - India: Whole shares with proportional capital redistribution for leftovers.
    """
    if not tickers or not predictions or total_capital <= 0:
        return {}

    log.info(f"--- UNIFIED ALLOCATOR START ({market}) ---")
    log.info(f"Total Candidates: {len(tickers)} | Pool: {total_capital:.2f}")

    # 1. SCORING LOGIC (SHARED)
    # score = predicted_return / (1 + volatility)
    # Ignore stocks with negative predicted_return.
    scored_data = []
    for t in tickers:
        pred = float(predictions.get(t, 0))
        if pred <= 0:
            continue
        
        vol = float(volatilities.get(t, 0.02))
        score = pred / (1 + vol)
        scored_data.append({
            "ticker": t,
            "score": score,
            "industry": get_industry(t),
            "price": float(prices.get(t, 999999))
        })

    if not scored_data:
        log.info("No candidates with positive scores.")
        return {}

    # 2. NORMALIZE INTO WEIGHTS
    total_raw_score = sum(d["score"] for d in scored_data)
    for d in scored_data:
        d["weight"] = d["score"] / total_raw_score

    # 3. APPLY SOFT INDUSTRY PENALTY
    # penalty = 1 / (1 + industry_weight * 1.5)
    industry_weights = {}
    for d in scored_data:
        ind = d["industry"]
        industry_weights[ind] = industry_weights.get(ind, 0.0) + d["weight"]
    
    for d in scored_data:
        ind = d["industry"]
        penalty = 1.0 / (1.0 + industry_weights[ind] * 1.5)
        d["score"] *= penalty # Adjust score by penalty

    # Recompute weights after penalty
    total_adj_score = sum(d["score"] for d in scored_data)
    for d in scored_data:
        d["weight"] = d["score"] / total_adj_score

    log.info("Weights before execution: %s", {d["ticker"]: f"{d['weight']*100:.1f}%" for d in scored_data})

    # 4. ALLOCATION & EXECUTION
    final_allocations = []
    
    if market in ["US", "USD"]:
        # US MARKET: Fractional shares, full deployment.
        for d in scored_data:
            allocation = total_capital * d["weight"]
            shares = allocation / d["price"]
            final_allocations.append({
                "ticker": d["ticker"],
                "shares": float(shares),
                "weight": float(d["weight"]),
                "allocation": float(allocation)
            })
    else:
        # INDIAN MARKET: Whole shares only + Redistribution.
        for d in scored_data:
            allocation = total_capital * d["weight"]
            shares = np.floor(allocation / d["price"])
            d["shares"] = float(shares)
            d["actual_spent"] = d["shares"] * d["price"]
        
        # Redistribution Logic
        iteration = 0
        while iteration < 10: # Limit iterations to prevent infinite loops
            leftover = total_capital - sum(d["actual_spent"] for d in scored_data)
            
            # Find candidates that "can accept more" (stocks with weight > 0)
            # Prompt: "distribute it among stocks with valid shares proportional to weights"
            # We'll use all stocks that were initially selected.
            valid_targets = [d for d in scored_data if d["weight"] > 0]
            if not valid_targets or leftover < min(d["price"] for d in valid_targets):
                break
            
            log.info(f"Iteration {iteration}: Redistributing Leftover Capital: {leftover:.2f} {market}")
            
            # Redistribute proportionally to their original weights
            target_total_weight = sum(d["weight"] for d in valid_targets)
            added_any = False
            
            for d in valid_targets:
                # How much of the leftover belongs to this stock?
                extra_budget = leftover * (d["weight"] / target_total_weight)
                # How many MORE shares can it buy?
                # We check the total possible with (old_spent + extra_budget)
                total_possible_shares = (d["actual_spent"] + extra_budget) // d["price"]
                new_shares = total_possible_shares - d["shares"]
                
                if new_shares > 0:
                    d["shares"] += new_shares
                    d["actual_spent"] = d["shares"] * d["price"]
                    added_any = True
            
            if not added_any:
                break
            iteration += 1

        for d in scored_data:
            final_allocations.append({
                "ticker": d["ticker"],
                "shares": float(d["shares"]),
                "weight": float(d["weight"]),
                "allocation": float(d["actual_spent"]),
                "unfilled": d["shares"] == 0
            })
        
        final_leftover = total_capital - sum(d["allocation"] for d in final_allocations)
        log.info(f"Final Leftover Capital ({market}): {final_leftover:.2f}")

    log.info("Final Allocations (%s):", market)
    for a in final_allocations:
        log.info(f"- {a['ticker']}: {a['shares']:.4f} shares | Value: {a['allocation']:.2f}")

    return {a["ticker"]: a for a in final_allocations}

class SmartAllocator:
    """Class wrapper for the unified allocate_portfolio function for backward compatibility."""
    def __init__(self, tickers, scores, volomap, total_capital, prices, market="US"):
        self.tickers = tickers
        self.scores = scores
        self.volomap = volomap
        self.total_capital = total_capital
        self.prices = prices
        self.market = market

    def allocate(self):
        alloc_map = allocate_portfolio(
            self.tickers, 
            self.scores, 
            self.volomap, 
            self.prices, 
            self.total_capital, 
            market=self.market
        )
        # Return simple weight map for backward compatibility
        return {t: info["weight"] for t, info in alloc_map.items()}
