import pytest
import pandas as pd
import numpy as np
from data.features import prepare_ml_dataframe
from models.train import train_and_score

def test_india_model_training():
    # 1. Create synthetic India data
    dates = pd.date_range(start="2024-01-01", periods=100)
    # Generate some momentum-driven data
    close = 100 * (1 + 0.01 * np.random.randn(100)).cumsum()
    volume = np.random.randint(1000, 5000, size=100)
    
    df = pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": volume
    }, index=dates)
    
    ticker = "RELIANCE.NS"
    
    # 2. Test Feature Engineering
    ml_df = prepare_ml_dataframe(df, ticker=ticker)
    
    # Ensure India-specific features exist
    india_features = ["momentum_3", "breakout", "volume_spike", "acceleration", "trend_strength"]
    for feat in india_features:
        assert feat in ml_df.columns, f"Feature {feat} missing in India ML dataframe"
    
    # 3. Test Model Training
    pred, vol = train_and_score(ml_df, ticker=ticker)
    
    # Ensure predictions are not NaN
    assert not np.isnan(pred), "Prediction is NaN"
    assert not np.isnan(vol), "Volatility is NaN"
    
    # 4. Test Prediction Variation
    # (Optional: small variance check)
    preds = []
    for _ in range(5):
        # vary data slightly
        df_variant = df.copy()
        df_variant["Close"] = df_variant["Close"] * (1 + 0.001 * np.random.randn(100))
        ml_df_v = prepare_ml_dataframe(df_variant, ticker=ticker)
        p, _ = train_and_score(ml_df_v, ticker=ticker)
        preds.append(p)
    
    # Check if predictions are not all the same (unless lucky)
    assert len(set(preds)) > 1, f"Predictions are constant: {preds}"

def test_market_detection_logic():
    from utils.currency import get_market
    assert get_market("RELIANCE.NS") == "INDIA"
    assert get_market("AAPL") == "US"
