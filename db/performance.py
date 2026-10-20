from datetime import datetime

from db.supabase_client import execute


def log_performance(total_value: float):
    execute(
        "insert into performance (date, total_value) values (%s, %s)",
        (datetime.now().strftime("%Y-%m-%d"), float(total_value)),
    )
