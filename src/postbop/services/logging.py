import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "postbop"

def get_log_directory() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")

    if state_home:
        log_directory = Path(state_home) / LOG_NAME
    else:
        log_directory = Path.home() / ".local" / "state" / LOG_NAME

    log_directory.mkdir(parents=True, exist_ok=True)

    return log_directory


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(LOG_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    log_file = get_log_directory() / "postbop.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger