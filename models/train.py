import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from config import FEATURE_COLUMNS
from utils.logger import log

def get_model(market):
    if market == "INDIA":
        return GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=3,
            random_state=42
        )
    else:
        return RandomForestRegressor(
            n_estimators=50,
            random_state=42
        )

def train_and_score(df: pd.DataFrame, ticker: str = ""):
    """Rule 1: Update feature list used in model with Market Detection."""
    try:
        is_india = ticker.endswith(".NS")
        market = "INDIA" if is_india else "US"
        
        # India-Specific additional features
        market_features = []
        if is_india:
            market_features = ["momentum_3", "breakout", "volume_spike", "acceleration", "trend_strength"]
        
        all_features = FEATURE_COLUMNS + market_features
        X = df[all_features].copy()
        y = df["target"]
        
        # Normalization (INDIA ONLY)
        if market == "INDIA":
            # (X - X.mean()) / X.std()
            X = (X - X.mean()) / X.std().replace(0, 1.0) # Handle div by zero
        
        # Ensure we have enough data to train
        if len(df) < 10:
            return 0.0, 0.02

        log.info("Using %s model for %s", market, ticker)
        model = get_model(market)
        model.fit(X, y)

        last_row = df.iloc[-1:]
        X_last = last_row[all_features].copy()
        if market == "INDIA":
            X_last = (X_last - df[all_features].mean()) / df[all_features].std().replace(0, 1.0)

        pred_return = float(model.predict(X_last)[0])

        # Need volatility_10 for position sizing (Rule 4)
        vol_10 = float(last_row["volatility_10"].iloc[0])

        return pred_return, vol_10
    except Exception as e:
        log.warning("train_and_score failed for %s: %s", ticker, e)
        return 0.0, 0.02
