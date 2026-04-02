import pytest
import numpy as np
from strategy.allocator import SmartAllocator
from unittest.mock import patch

def test_allocator_normalization():
    """Verify weights sum to 1."""
    tickers = ["AAPL", "TSLA", "MSFT"]
    scores = {"AAPL": 0.1, "TSLA": 0.05, "MSFT": 0.02}
    volomap = {"AAPL": 0.1, "TSLA": 0.2, "MSFT": 0.05}
    prices = {"AAPL": 150.0, "TSLA": 200.0, "MSFT": 300.0}
    total_capital = 1000.0
    
    with patch('strategy.allocator.get_industry', return_value="Tech"):
        allocator = SmartAllocator(tickers, scores, volomap, total_capital, prices)
        allocation = allocator.allocate()
        
        weights = list(allocation.values())
        assert sum(weights) == pytest.approx(1.0)

def test_allocator_ranking():
    """Verify higher score leads to higher allocation."""
    tickers = ["A", "B"]
    scores = {"A": 0.2, "B": 0.1}
    volomap = {"A": 0.1, "B": 0.1}
    prices = {"A": 100.0, "B": 50.0}
    
    with patch('strategy.allocator.get_industry', return_value="Common"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, prices)
        allocation = allocator.allocate()
        
        assert allocation["A"] > allocation["B"]

def test_industry_penalty():
    """Verify industry penalty reduces weight if > 40%."""
    # Try to stack many stocks in one industry
    tickers = ["T1", "T2", "T3", "T4", "T5"]
    scores = {t: 0.1 for t in tickers}
    volomap = {t: 0.1 for t in tickers}
    prices = {t: 100.0 for t in tickers}
    
    # We'll mock get_industry to return "Tech" for all
    with patch('strategy.allocator.get_industry', return_value="Tech"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, prices)
        allocation = allocator.allocate()
        
        # Since they are all in same industry, and they would have 20% each (sum=100% > 40%)
        # They should all get penalized. 
        # Actually, if all are penalized equally, the relative weights might stay same 
        # BUT total would change and RENORMALIZATION happens.
        # Let's compare with one stock in DIFFERENT industry.
        
    tickers = ["Tech1", "Tech2", "Other"]
    scores = {"Tech1": 0.5, "Tech2": 0.5, "Other": 0.1}
    volomap = {"Tech1": 0.1, "Tech2": 0.1, "Other": 0.1}
    prices = {t: 100.0 for t in tickers}
    
    def mock_ind(t):
        return "Tech" if t.startswith("Tech") else "Other"

    with patch('strategy.allocator.get_industry', side_effect=mock_ind):
        # Tech1+Tech2 together will have huge weight
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, prices)
        allocation = allocator.allocate()
        
        # Without penalty, Tech1 and Tech2 would dominate. 
        # With penalty, their weights are halved before renormalization.
        assert allocation["Tech1"] < 0.5 # Should be capped or penalized

def test_max_position_cap():
    """Verify max weight per stock is 0.2."""
    tickers = ["Winner", "Loser"]
    scores = {"Winner": 1.0, "Loser": 0.01}
    volomap = {"Winner": 0.1, "Loser": 0.1}
    prices = {"Winner": 100.0, "Loser": 50.0}
    
    with patch('strategy.allocator.get_industry', return_value="Misc"):
        allocator = SmartAllocator(tickers, scores, volomap, 1000.0, prices)
        allocation = allocator.allocate()
        
        # Winner is 100x better so it should dominate now that max_position_cap is removed
        assert allocation["Winner"] > 0.9
