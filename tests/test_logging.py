"""Logging setup is idempotent and respects the requested level."""

from __future__ import annotations

import logging

from core.logging import _HANDLER_NAME, configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    root = logging.getLogger()
    named = [handler for handler in root.handlers if handler.name == _HANDLER_NAME]
    assert len(named) == 1


def test_configure_logging_sets_level() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_get_logger_returns_named_logger() -> None:
    assert get_logger("core.test").name == "core.test"
