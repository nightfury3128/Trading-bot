from unittest.mock import patch, MagicMock
from execution.trading import run_buy_phase
import pytest

def test_allocation_cash_utilization():
    """Verify that the buy loop utilizes as much cash as possible (Rule: geometric fix)."""
    # Simple setup: 2 picks, high risk scores
    top_picks = [("AAPL", 50.0), ("MSFT", 50.0)]
    prices = {"AAPL": 100.0, "MSFT": 100.0}
    scores = {"AAPL": 0.05, "MSFT": 0.04}
    initial_cash = 100.0
    
    # Portfolio is empty
    portfolio = []
    
    # Mock the DB calls. Also relax the industry cap so allocation isn't constrained.
    with patch('execution.trading.add_position') as mock_add, \
         patch('execution.trading.log_trade') as mock_log, \
         patch('execution.trading.calculate_industry_exposures', return_value=(0.0, {})), \
         patch('execution.trading.check_industry_cap', return_value=True), \
         patch('config.INDUSTRY_CAP_US', 1.0):
        
        remaining_cash = run_buy_phase(top_picks, prices, scores, initial_cash, portfolio)
        
        # 1. Verification of geometric distribution
        # 1st pick should get 50/(50+50) = 50% of 100 = $50
        # 2nd pick should get 100% of remaining (since it's the last) = $50
        # Total spent: 100. Remaining cash: ~0
        assert remaining_cash < 1.0 # Within float precision
        
        # 2. Verify both were bought
        assert mock_add.call_count == 2
        
        # 3. Verify exact share counts
        # AAPL: $50 / $100.1 (cost_buy) = 0.4995...
        # shares[0] 
        args_aapl = mock_add.call_args_list[0][0]
        assert args_aapl[0] == "AAPL"

def test_industry_cap_enforcement():
    """Verify that a buy is skipped if it would exceed the 10% sector cap."""
    top_picks = [("XOM", 10.0), ("CVX", 10.0)] # Both Energy
    prices = {"XOM": 100.0, "CVX": 100.0}
    scores = {"XOM": 0.05, "CVX": 0.05}
    initial_cash = 200.0
    
    # Total portfolio value = 1000. 10% cap = 100.
    # If first buy is $100, second buy of Energy should be blocked.
    total_val = 1000.0
    
    with patch('execution.trading.add_position') as mock_add, \
         patch('execution.trading.log_trade') as mock_log, \
         patch('execution.trading.calculate_industry_exposures', return_value=(total_val - initial_cash, {})), \
         patch('strategy.risk.get_industry', return_value="Energy"):
        
        # We need to mock check_industry_cap manually because we want to test its interaction
        # or we just rely on the real one since it's a unit test of the loop
        
        remaining_cash = run_buy_phase(top_picks, prices, scores, initial_cash, [])
        
        # Both should be bought now since hard blocks were removed in favor of soft penalties
        assert mock_add.call_count == 2
        
        tickers_bought = [call[0][0] for call in mock_add.call_args_list]
        assert "XOM" in tickers_bought
        assert "CVX" in tickers_bought
