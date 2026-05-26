"""Structured logging utilities for Invariant."""

from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger for an Invariant module.

    Uses the standard library logging module. Log level is controlled by
    the ``INVARIANT_LOG_LEVEL`` environment variable (default: WARNING).

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        Configured Logger instance.
    """
    import os

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    level_name = os.environ.get("INVARIANT_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logger.setLevel(level)

    return logger
