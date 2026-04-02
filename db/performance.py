from datetime import datetime
from db.supabase_client import supabase


def log_performance(total_value: float):
    supabase.table("performance").insert(
        {"date": datetime.now().strftime("%Y-%m-%d"), "total_value": float(total_value)}
    ).execute()
