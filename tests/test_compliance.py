import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from execution.trading import run_sell_phase, run_buy_phase
from config import MIN_HOLD_DAYS, MIN_PREDICTED_RETURN_BUY

def test_min_hold_days_strict_enforcement():
    """Test that sell is blocked if days_held < 7 (Rule 1)."""
    # Position only held for 2 days
    buy_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    positions = {"AAPL": {"ticker": "AAPL", "shares": 10, "buy_price": 150.0, "buy_date": buy_date}}
    prices = {"AAPL": 140.0} # Hit stop loss at 0.95, but hold period should block
    scores = {"AAPL": 0.1} # Weak signal too
    
    with patch('execution.trading.remove_position') as mock_remove:
        new_cash = run_sell_phase(positions, prices, scores, 1000.0)
        # Cash shouldn't change, and remove_position shouldn't be called
        assert new_cash == 1000.0
        mock_remove.assert_not_called()

def test_same_day_sell_block():
    """Test that sell is blocked on the exact same day of purchase (Rule 2)."""
    buy_date = datetime.now().strftime("%Y-%m-%d")
    positions = {"MSFT": {"ticker": "MSFT", "shares": 5, "buy_price": 300.0, "buy_date": buy_date}}
    prices = {"MSFT": 400.0} # Take profit hit, but same-day block should trigger
    scores = {"MSFT": 0.5}
    
    with patch('execution.trading.remove_position') as mock_remove:
        new_cash = run_sell_phase(positions, prices, scores, 1000.0)
        assert new_cash == 1000.0
        mock_remove.assert_not_called()

def test_override_safety_caps():
    """Ensure stop loss & take profit cannot override the 7-day hold (Rule 1c)."""
    # Held for 5 days (not enough)
    buy_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    positions = {"TSLA": {"ticker": "TSLA", "shares": 20, "buy_price": 200.0, "buy_date": buy_date}}
    
    # 1. Test Stop loss override failure
    prices_sl = {"TSLA": 180.0} # < 200 * 0.95
    with patch('execution.trading.remove_position') as mock_remove:
        run_sell_phase(positions, prices_sl, {}, 1000.0)
        mock_remove.assert_not_called()
        
    # 2. Test Take profit override failure
    prices_tp = {"TSLA": 250.0} # > 200 * 1.10
    with patch('execution.trading.remove_position') as mock_remove:
        run_sell_phase(positions, prices_tp, {}, 1000.0)
        mock_remove.assert_not_called()

def test_business_days_weekend_handling():
    """Verify that weekends are skipped for the 7-day hold rule (Rule: 7 Business Days)."""
    # Assume today is Monday 2026-04-06 (Monday).
    # Buying 3 calendar days ago (Friday 2026-04-03).
    # Business days is only 1 (Friday -> Monday).
    
    # We'll use absolute dates for testing
    from datetime import date
    buy_date = "2026-04-03" # Friday
    positions = {"AAPL": {"ticker": "AAPL", "shares": 1, "buy_price": 100.0, "buy_date": buy_date}}
    prices = {"AAPL": 150.0}
    
    with patch('execution.trading.datetime') as mock_dt, \
         patch('execution.trading.remove_position') as mock_remove:
        # Mock "today" to be Monday April 6th, 2026
        mock_dt.now.return_value = datetime(2026, 4, 6)
        mock_dt.strftime = datetime.strftime # keep utility
        
        new_cash = run_sell_phase(positions, prices, {}, 1000.0)
        # Should be BLOCKED because only 1 business day passed (Friday to Monday)
        mock_remove.assert_not_called()

def test_low_activity_signal_filter():
    """Test that BUY phase is skipped if best signal < 1% (Rule 7)."""
    top_picks = [("META", 0.05)] # Strong risk score, but...
    scores = {"META": 0.005} # Absolute prediction is 0.5% (too low)
    prices = {"META": 500.0}
    cash = 1000.0
    
    with patch('execution.trading.add_position') as mock_add:
        run_buy_phase(top_picks, prices, scores, cash, [])
        mock_add.assert_not_called()
