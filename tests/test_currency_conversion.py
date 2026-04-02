import pytest
from utils.currency import normalize_to_usd, get_currency

def test_get_currency():
    assert get_currency("AAPL") == "USD"
    assert get_currency("RELIANCE.NS") == "INR"
    assert get_currency("TSLA") == "USD"
    assert get_currency("TCS.NS") == "INR"

def test_normalize_to_usd():
    inr_to_usd = 0.012 # 1/83.33 approx
    
    # USD stays same
    assert normalize_to_usd(100.0, "USD", inr_to_usd) == 100.0
    
    # INR converted
    assert normalize_to_usd(1000.0, "INR", inr_to_usd) == 12.0
    
    # Zero stays zero
    assert normalize_to_usd(0.0, "INR", inr_to_usd) == 0.0
