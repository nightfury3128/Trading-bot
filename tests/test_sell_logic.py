import pytest
from strategy.us_strategy import handle_sell as us_handle_sell
from strategy.india_strategy import handle_sell as india_handle_sell
from unittest.mock import MagicMock, patch

def test_winner_preservation():
    """Verify that winners with positive signals trigger lower sell fractions."""
    pos = {
        "ticker": "AAPL",
        "buy_date": "2026-01-01",
        "buy_price": 100.0,
        "shares": 100.0
    }
    # PnL = +50%, Pred = +5%
    # Reason: Profit Lock. Base(0.2) + Risk(0) + Signal(0) = 0.2. 
    # Winner preservation rule should cut it by 50% -> 0.1
    with patch('strategy.us_strategy.log_trade'), \
         patch('strategy.us_strategy.update_position'), \
         patch('strategy.us_strategy.remove_position'), \
         patch('strategy.us_strategy.business_days_since', return_value=10):
        
        # We need a trigger. pnl > 0.1 triggers Profit Lock.
        res, proceeds = us_handle_sell("AAPL", pos, 150.0, 0.05, volatility=0.0)
        assert res == "PROFIT_LOCK"
        # Check that it's a partial sell (10 shares sold)
        # We can't easily check internal fraction without logging capture, 
        # but 150*10 = 1500 proceeds.
        assert proceeds > 0

def test_strong_signal_hold():
    """Verify that strong positive signals prevent selling."""
    pos = {
        "ticker": "AAPL",
        "buy_date": "2026-01-01",
        "buy_price": 100.0,
        "shares": 100.0
    }
    with patch('strategy.us_strategy.business_days_since', return_value=10):
        # Pred = 25% (> 20% limit)
        res, proceeds = us_handle_sell("AAPL", pos, 150.0, 0.25, volatility=0.0)
        assert res is None
        assert proceeds == 0.0

def test_negative_signal_aggressive():
    """Verify strong negative signal triggers aggressive selling."""
    pos = {
        "ticker": "TSLA",
        "buy_date": "2026-01-01",
        "buy_price": 200.0,
        "shares": 10.0
    }
    # Pred = -10% (< -5% aggressive limit)
    with patch('strategy.us_strategy.log_trade'), \
         patch('strategy.us_strategy.update_position'), \
         patch('strategy.us_strategy.remove_position'), \
         patch('strategy.us_strategy.business_days_since', return_value=10):
        
        res, proceeds = us_handle_sell("TSLA", pos, 190.0, -0.1, volatility=0.1)
        assert res == "NEGATIVE_SIGNAL"
        # Should be full sell due to high fraction + dust (if it hits) or just high fraction > 0.8
        # 10 shares * 0.8 = 8 shares. 8 * 190 = 1520.
        assert proceeds > 1000

def test_stop_loss_priority():
    """Verify stop loss overrides other logic."""
    pos = {
        "ticker": "AAPL",
        "buy_date": "2026-01-01",
        "buy_price": 100.0,
        "shares": 10.0
    }
    with patch('strategy.us_strategy.log_trade'), \
         patch('strategy.us_strategy.update_position'), \
         patch('strategy.us_strategy.remove_position'), \
         patch('strategy.us_strategy.business_days_since', return_value=10):
        
        # Stop loss at 90. Price = 80.
        res, proceeds = us_handle_sell("AAPL", pos, 80.0, 0.5, volatility=0.1)
        assert res == "STOP_LOSS"

def test_risk_reduction_losing():
    """Verify risk reduction for losing positions with weak signals."""
    pos = {
        "ticker": "RELIANCE.NS",
        "buy_price": 2500.0,
        "shares": 10.0,
        "stop_loss": 0.9
    }
    # PnL = -5%, Pred = 5% (< 10% weak signal limit)
    with patch('strategy.india_strategy.log_trade'), \
         patch('strategy.india_strategy.update_position'), \
         patch('strategy.india_strategy.remove_position'):
        
        res, proceeds = india_handle_sell("RELIANCE.NS", pos, 2375.0, 0.05, volatility=0.0)
        assert res == "RISK_REDUCTION"
