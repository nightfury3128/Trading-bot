import pandas as pd
from data.features import prepare_ml_dataframe
from config import FEATURE_COLUMNS


def test_prepare_ml_dataframe(mock_ohlcv_data):
    df = prepare_ml_dataframe(mock_ohlcv_data)

    # Check no NaN in target or features
    assert not df[FEATURE_COLUMNS + ["target"]].isnull().values.any()

    # Check all features are present
    for col in FEATURE_COLUMNS:
        assert col in df.columns

    # Check target is present
    assert "target" in df.columns

    # Ensure dataframe didn't completely disappear
    assert len(df) > 50
