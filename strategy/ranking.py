import yfinance as yf
import numpy as np
from utils.logger import log


def get_market_regime() -> bool:
    """Rule 3: SPY MA50 vs MA200 filter."""
    try:
        spy = yf.download("SPY", period="2y", progress=False)
        if spy.empty:
            return True
        spy["MA50"] = spy["Close"].rolling(50).mean()
        spy["MA200"] = spy["Close"].rolling(200).mean()
        ma50 = spy["MA50"].iloc[-1]
        ma200 = spy["MA200"].iloc[-1]
        log.info("Market Regime: SPY MA50=%.2f, MA200=%.2f", ma50, ma200)
        return ma50 >= ma200
    except Exception as e:
        log.warning("Market regime check failed: %s", e)
        return True


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Rule 8: Cross-sectional Normalization."""
    if not scores:
        return {}
    pred_values = list(scores.values())
    mean_pred = np.mean(pred_values)
    std_pred = np.std(pred_values) or 1.0
    return {t: (s - mean_pred) / std_pred for t, s in scores.items()}


def rank_candidates(z_scores: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(z_scores.items(), key=lambda x: -x[1])
