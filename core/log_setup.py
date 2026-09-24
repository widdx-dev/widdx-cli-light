"""Centralized logging setup — consistent format, level and log rotation across all entry points.

Usage in entry points::

    from core.log_setup import setup_logging
    setup_logging("widdx.cli")
"""

import logging
import sys

_FORMAT = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_ROTATING_FILE_HANDLER = None


def setup_logging(name: str = "widdx", level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger(name)


def add_file_handler(
    filename: str = "widdx.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Handler:
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
    logging.getLogger().addHandler(handler)
    return handler
