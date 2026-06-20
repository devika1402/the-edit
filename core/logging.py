"""Logging setup. The pipeline logs; it does not print.

A single configured stream handler on the root logger gives every module a
consistent, timestamped format. ``configure_logging`` is idempotent, so calling
it from more than one entry point will not duplicate log lines.
"""

from __future__ import annotations

import logging
import sys

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_HANDLER_NAME = "fashion_console"


def configure_logging(level: str | int = "INFO", *, fmt: str = DEFAULT_FORMAT) -> logging.Logger:
    """Attach a formatted stream handler to the root logger and set its level.

    Args:
        level: a level name ("INFO", "DEBUG", ...) or a numeric ``logging`` level.
        fmt: the log line format string.

    Returns:
        The configured root logger.
    """
    if isinstance(level, str):
        numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    else:
        numeric_level = level

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if not any(handler.name == _HANDLER_NAME for handler in root.handlers):
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a named module logger (a thin wrapper over ``logging.getLogger``)."""
    return logging.getLogger(name)
