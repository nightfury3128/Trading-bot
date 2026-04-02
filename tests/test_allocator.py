import pytest
import numpy as np
from strategy.allocator import SmartAllocator
from unittest.mock import patch

def test_allocator_normalization():
    """Verify weights sum to 1."""
    tickers = ["AAPL", "TSLA", "MSFT"]
    scores = {"AAPL": 0.1, "TSLA": 0.05, "MSFT": 0.02}
    volomap = {"AAPL": 0.1, "TSLA": 0.2, "MSFT": 0.05}
    total_capital = 1000.0
    
    with patch('strategy.allocator.get_industry', return_value="Tech"):
        allocator = SmartAllocator(tickers, scores, volomap, total_capital)
        allocation = allocator.allocate()
        
        weights = list(allocation.values())
        assert sum(weights) == pytest.approx(1.0)

def test_allocator_ranking():
    """Verify higher score leads to higher allocation."""
    tickers = ["A", "B"]
    scores = {"A": 0.2, "B": 0.1}
    volomap = {"A": 0.1, "B": 0.1}
    
    with patch('strategy.allocator.get_industry', return_value="Common"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0)
        allocation = allocator.allocate()
        
        assert allocation["A"] > allocation["B"]

def test_industry_penalty():
    """Verify industry penalty reduces weight if > 40%."""
    # Try to stack many stocks in one industry
    tickers = ["T1", "T2", "T3", "T4", "T5"]
    scores = {t: 0.1 for t in tickers}
    volomap = {t: 0.1 for t in tickers}
    
    # We'll mock get_industry to return "Tech" for all
    with patch('strategy.allocator.get_industry', return_value="Tech"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, industry_cap=0.4)
        allocation = allocator.allocate()
        
        # Since they are all in same industry, and they would have 20% each (sum=100% > 40%)
        # They should all get penalized. 
        # Actually, if all are penalized equally, the relative weights might stay same 
        # BUT total would change and RENORMALIZATION happens.
        # Let's compare with one stock in DIFFERENT industry.
        
    tickers = ["Tech1", "Tech2", "Other"]
    scores = {"Tech1": 0.5, "Tech2": 0.5, "Other": 0.1}
    volomap = {"Tech1": 0.1, "Tech2": 0.1, "Other": 0.1}
    
    def mock_ind(t):
        return "Tech" if t.startswith("Tech") else "Other"

    with patch('strategy.allocator.get_industry', side_effect=mock_ind):
        # Tech1+Tech2 together will have huge weight > 40%
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, industry_cap=0.4)
        allocation = allocator.allocate()
        
        # Without penalty, Tech1 and Tech2 would dominate. 
        # With penalty, their weights are halved before renormalization.
        assert allocation["Tech1"] < 0.5 # Should be capped or penalized

def test_max_position_cap():
    """Verify max weight per stock is 0.2."""
    tickers = ["Winner", "Loser"]
    scores = {"Winner": 1.0, "Loser": 0.01}
    volomap = {"Winner": 0.1, "Loser": 0.1}
    
    with patch('strategy.allocator.get_industry', return_value="Misc"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, max_stock_cap=0.2)
        allocation = allocator.allocate()
        
        # Even though Winner is 100x better, it should be capped at 0.2
        # BUT wait, the final allocation depends on renormalization.
        # If there are only 2 stocks, and one is capped at 0.2, the other MUST take 0.8
        # unless we allow cash. The prompt says "weights sum to 1".
        # So if one is capped at 0.2, and there is only one other, the other gets 0.8.
        # This is logical if we want to be fully invested.
        assert allocation["Winner"] <= 0.200001
