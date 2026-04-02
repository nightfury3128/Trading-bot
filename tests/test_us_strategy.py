import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from strategy.us_strategy import handle_sell

def test_us_strategy_strict_rules():
    # Mock position
    today = datetime.now().strftime("%Y-%m-%d")
    pos = {
        "ticker": "AAPL",
        "buy_date": today, # Same day
        "buy_price": 150.0,
        "shares": 10.0
    }
    
    # Mocking dependencies
    with patch("strategy.us_strategy.remove_position") as mock_remove, \
         patch("strategy.us_strategy.log_trade") as mock_log, \
         patch("strategy.us_strategy.business_days_since") as mock_days:
        
        # Scenario 1: Same day sell attempt
        mock_days.return_value = 0
        reason, proceeds = handle_sell("AAPL", pos, 130.0, 0.5) # Stop loss price
        assert reason is None
        assert proceeds == 0.0
        mock_remove.assert_not_called()
        
        # Scenario 2: Different day but < 7 days
        pos_old = pos.copy()
        pos_old["buy_date"] = "2026-03-31" # Let's say 2 days ago
        mock_days.return_value = 2
        reason, proceeds = handle_sell("AAPL", pos_old, 130.0, 0.5)
        assert reason is None
        assert proceeds == 0.0
        mock_remove.assert_not_called()
        
        # Scenario 3: Passed 7 days, Stop Loss triggered
        mock_days.return_value = 10
        reason, proceeds = handle_sell("AAPL", pos_old, 130.0, 0.5)
        assert reason == "STOP_LOSS"
        assert proceeds > 0
        mock_remove.assert_called_once()
        
        # Reset mocks
        mock_remove.reset_mock()
        mock_log.reset_mock()
        
        # Scenario 4: Passed 7 days, Model Sell triggered
        reason, proceeds = handle_sell("AAPL", pos_old, 150.0, 0.3) # Score 0.3
        assert reason == "MODEL_SELL"
        assert proceeds > 0
        mock_remove.assert_called_once()
