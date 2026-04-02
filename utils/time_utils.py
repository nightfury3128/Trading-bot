import time
from datetime import datetime


def _t0():
    return time.perf_counter()


def _dt(start):
    return (time.perf_counter() - start) * 1000.0


def days_since(date_str: str) -> int:
    try:
        d1 = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - d1).days
    except:
        return 0
