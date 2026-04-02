import pandas as pd
import numpy as np
from config import FEATURE_COLUMNS, FUTURE_RETURN_DAYS
from utils.logger import log


def prepare_ml_dataframe(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Rule 1 & 2: Feature Engineering & Target Improvement."""
    try:
        df = ohlcv.copy()
        if df.empty or "Close" not in df.columns:
            return pd.DataFrame()

        # Core returns
        df["returns"] = df["Close"].pct_change()

        # Existing MA
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()

        # New Features (Rule 1)
        df["momentum_5"] = df["Close"].pct_change(5)
        df["momentum_10"] = df["Close"].pct_change(10)
        df["momentum_20"] = df["Close"].pct_change(20)
        df["volatility_10"] = df["returns"].rolling(10).std()
        df["volatility_20"] = df["returns"].rolling(20).std()
        if "Volume" in df.columns:
            df["volume_change"] = df["Volume"].pct_change()
        else:
            df["volume_change"] = 0

        # Ratios (Rule 1 / Rule 13 safety)
        df["ma_ratio"] = df["MA20"] / df["MA50"].replace(0, np.nan)
        df["price_vs_ma"] = df["Close"] / df["MA20"].replace(0, np.nan)

        # Target (Rule 2)
        df["target"] = (df["Close"].shift(-FUTURE_RETURN_DAYS) - df["Close"]) / df[
            "Close"
        ]

        out = df.dropna(subset=FEATURE_COLUMNS + ["target"])
        return out
    except Exception as e:
        log.debug("prepare_ml_dataframe error: %s", e)
        return pd.DataFrame()
