import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def mock_ohlcv_data():
    """Generates synthetic OHLCV data for testing."""
    dates = pd.date_range(start="2024-01-01", periods=150)
    data = {
        "Open": np.random.uniform(100, 110, size=150),
        "High": np.random.uniform(110, 120, size=150),
        "Low": np.random.uniform(90, 100, size=150),
        "Close": np.random.uniform(100, 110, size=150),
        "Volume": np.random.randint(1_000_000, 5_000_000, size=150),
    }
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture
def mock_portfolio():
    return [
        {"ticker": "AAPL", "shares": 1.5, "buy_price": 180.0, "buy_date": "2024-01-01"},
        {"ticker": "MSFT", "shares": 0.5, "buy_price": 400.0, "buy_date": "2024-01-01"},
    ]


@pytest.fixture
def mock_prices():
    return {"AAPL": 190.0, "MSFT": 410.0}


@pytest.fixture
def mock_scores():
    return {"AAPL": 0.05, "MSFT": 0.02, "GOOGL": 0.03}
