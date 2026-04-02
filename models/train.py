import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from config import FEATURE_COLUMNS


def train_and_score(df: pd.DataFrame):
    """Rule 1: Update feature list used in model."""
    X = df[FEATURE_COLUMNS]
    y = df["target"]
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    last_row = df.iloc[-1:]
    pred_return = float(model.predict(last_row[FEATURE_COLUMNS])[0])

    # Need volatility_10 for position sizing (Rule 4)
    vol_10 = float(last_row["volatility_10"].iloc[0])

    return pred_return, vol_10
