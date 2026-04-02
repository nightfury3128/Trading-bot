import logging
import os


def setup_logger(name: str):
    _LOG_LEVEL = getattr(
        logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO
    )

    logger = logging.getLogger(name)
    logger.setLevel(_LOG_LEVEL)

    # Check if handler already exists to avoid duplicate logs in some environments
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Silence noisy loggers
    for noisy_logger in ("yfinance", "httpx", "httpcore", "hpack", "peewee"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return logger


log = setup_logger("trading_bot")
