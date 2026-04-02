import pytest
from unittest.mock import patch, MagicMock
from strategy.india_strategy import handle_sell

def test_india_strategy_relaxed_rules():
    # Mock position
    pos = {
        "ticker": "RELIANCE.NS",
        "buy_date": "2026-04-02", # Today
        "buy_price": 2500.0,
        "shares": 10.0
    }
    
    # Mocking dependencies
    with patch("strategy.india_strategy.remove_position") as mock_remove, \
         patch("strategy.india_strategy.log_trade") as mock_log:
        
        # Test 1: Stop Loss Trigger (Even on same day)
        reason, proceeds = handle_sell("RELIANCE.NS", pos, 2300.0, 0.5)
        assert reason == "STOP_LOSS"
        assert proceeds > 0
        mock_remove.assert_called_once()
        
        # Reset mocks
        mock_remove.reset_mock()
        mock_log.reset_mock()
        
        # Test 2: Take Profit Trigger (Even on same day)
        reason, proceeds = handle_sell("RELIANCE.NS", pos, 3000.0, 0.5)
        assert reason == "TAKE_PROFIT"
        assert proceeds > 0
        mock_remove.assert_called_once()
        
        # Reset mocks
        mock_remove.reset_mock()
        mock_log.reset_mock()
        
        # Test 3: Model Sell (Even on same day)
        reason, proceeds = handle_sell("RELIANCE.NS", pos, 2500.0, 0.3)
        assert reason == "MODEL_SELL"
        assert proceeds > 0
        mock_remove.assert_called_once()
