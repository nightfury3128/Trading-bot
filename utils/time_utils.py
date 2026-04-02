import time
from datetime import datetime


def _t0():
    return time.perf_counter()


def _dt(start):
    return (time.perf_counter() - start) * 1000.0


def days_since(date_str: str) -> int:
    """Calendar days count."""
    try:
        d1 = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - d1).days
    except:
        return 0

def business_days_since(date_str: str) -> int:
    """Business days count (excludes weekends)."""
    import pandas as pd
    import numpy as np
    try:
        start = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        if start >= today: return 0
        return int(np.busday_count(start, today))
    except:
        return 0
