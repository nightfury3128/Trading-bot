import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    import pytz as tz
    ZoneInfo = tz.timezone

import holidays
from utils.logger import log

def is_market_open(market: str) -> bool:
    """Check if the given market is currently open for trading."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    if market.upper() == "US":
        tz = ZoneInfo("US/Eastern")
        now_local = now_utc.astimezone(tz)
        hols = holidays.NYSE()
        start = datetime.time(9, 30)
        end = datetime.time(16, 0)
    elif market.upper() == "INDIA":
        tz = ZoneInfo("Asia/Kolkata")
        now_local = now_utc.astimezone(tz)
        hols = holidays.XNSE()
        start = datetime.time(9, 15)
        end = datetime.time(15, 30)
    else:
        log.error(f"Unknown market: {market}")
        return False
        
    date_local = now_local.date()
    time_local = now_local.time()
    
    current_time_str = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    # 5 is Saturday, 6 is Sunday
    if date_local.weekday() >= 5:
        log.info(f"[{market}] {current_time_str} | Market status: CLOSED | Reason: Weekend")
        return False
        
    if date_local in hols:
        holiday_name = hols.get(date_local)
        log.info(f"[{market}] {current_time_str} | Market status: CLOSED | Reason: Holiday ({holiday_name})")
        return False
        
    if not (start <= time_local <= end):
        log.info(f"[{market}] {current_time_str} | Market status: CLOSED | Reason: Outside hours ({start.strftime('%H:%M')} - {end.strftime('%H:%M')})")
        return False
        
    # log.info(f"[{market}] {current_time_str} | Market status: OPEN")
    return True
