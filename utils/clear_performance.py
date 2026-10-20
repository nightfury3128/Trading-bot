from db.supabase_client import execute
from utils.logger import setup_logger

log = setup_logger("performance_cleaner")


def clear_performance():
    log.info("Deleting all rows from performance table...")
    execute("delete from performance")
    log.info("SUCCESS: Performance table cleared.")


if __name__ == "__main__":
    clear_performance()
