"""Lightweight logger (replaces MiroFish's Flask-coupled logger)."""

from __future__ import annotations

import logging
import sys


_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(name: str = "miroedo.engine", level: int = logging.INFO) -> logging.Logger:
    """Get a configured logger; idempotent."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    return logger
