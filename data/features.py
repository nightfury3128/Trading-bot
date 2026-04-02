import pandas as pd
import numpy as np
from config import FEATURE_COLUMNS, FUTURE_RETURN_DAYS
from utils.logger import log


def prepare_ml_dataframe(ohlcv: pd.DataFrame, ticker: str = "") -> pd.DataFrame:
    """Rule 1 & 2: Feature Engineering & Target Improvement with Market Detection."""
    try:
        df = ohlcv.copy()
        if df.empty or "Close" not in df.columns:
            return pd.DataFrame()

        is_india = ticker.endswith(".NS")

        # Core returns
        df["returns"] = df["Close"].pct_change()

        # Existing MA
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()

        # Shared Momentum (Refined for India if needed)
        df["momentum_5"] = df["Close"].pct_change(5)
        df["momentum_10"] = df["Close"].pct_change(10)
        df["momentum_20"] = df["Close"].pct_change(20)

        market_features = []
        if is_india:
            # India-Specific Momentum Logic
            df["momentum_3"] = df["Close"].pct_change(3)
            # Breakout strength
            df["high_20"] = df["Close"].rolling(20).max()
            df["breakout"] = df["Close"] / df["high_20"].replace(0, np.nan)
            # Volume spike detection
            if "Volume" in df.columns:
                df["volume_spike"] = df["Volume"] / df["Volume"].rolling(20).mean().replace(0, np.nan)
            else:
                df["volume_spike"] = 1.0
            # Momentum acceleration
            df["acceleration"] = df["momentum_5"] - df["momentum_10"]
            # Trend confirmation
            df["trend_strength"] = df["MA20"] - df["MA50"]
            
            market_features = ["momentum_3", "breakout", "volume_spike", "acceleration", "trend_strength"]

        # Shared/US Features
        df["volatility_10"] = df["returns"].rolling(10).std()
        df["volatility_20"] = df["returns"].rolling(20).std()
        if "Volume" in df.columns:
            df["volume_change"] = df["Volume"].pct_change()
        else:
            df["volume_change"] = 0

        # Ratios
        df["ma_ratio"] = df["MA20"] / df["MA50"].replace(0, np.nan)
        df["price_vs_ma"] = df["Close"] / df["MA20"].replace(0, np.nan)

        # Target (Market Specific)
        horizon = 3 if is_india else FUTURE_RETURN_DAYS
        df["target"] = (df["Close"].shift(-horizon) - df["Close"]) / df[
            "Close"
        ].replace(0, np.nan)

        # Cleanup
        current_features = FEATURE_COLUMNS + market_features
        df = df.replace([np.inf, -np.inf], np.nan)
        out = df.dropna(subset=current_features + ["target"]).copy()
        
        # Robustness: Clip values to avoid float32 overflow
        for col in current_features:
            if col in out.columns:
                out[col] = out[col].clip(lower=-1e9, upper=1e9)
        
        return out
    except Exception as e:
        log.debug("prepare_ml_dataframe error for %s: %s", ticker, e)
        return pd.DataFrame()
