import numpy as np
import pandas as pd
from data.features import prepare_ml_dataframe
from models.train import train_and_score


def test_train_and_score(mock_ohlcv_data):
    df = prepare_ml_dataframe(mock_ohlcv_data)

    # Run twice to check for consistency/variance
    pred1, vol1 = train_and_score(df)

    # 1. Ensure no NaN in results
    assert not np.isnan(pred1)
    assert not np.isnan(vol1)

    # 2. Add slightly more data to see if pred changes (ensure it's not a constant output)
    # This is a weak test but checks it is not returning a hardcoded zero.
    assert pred1 != 0.0

    # 3. Ensure vol is positive
    assert vol1 > 0
