from db.supabase_client import supabase
from utils.logger import setup_logger

log = setup_logger("performance_cleaner")


def clear_performance():
    log.info("Deleting all rows from performance table...")
    supabase.table("performance").delete().filter("id", "gt", 0).execute()
    log.info("SUCCESS: Performance table cleared.")


if __name__ == "__main__":
    clear_performance()
