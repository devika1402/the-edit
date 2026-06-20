"""The custom exception hierarchy is shallow but must hang together."""

from __future__ import annotations

import pytest

from core.exceptions import (
    BigQueryJobError,
    ConfigError,
    DataValidationError,
    FashionRecommenderError,
    ModelTrainingError,
    SqlFileError,
)


def test_base_inherits_from_exception() -> None:
    assert issubclass(FashionRecommenderError, Exception)


def test_all_project_errors_share_the_base() -> None:
    for exc_type in (
        ConfigError,
        SqlFileError,
        BigQueryJobError,
        DataValidationError,
        ModelTrainingError,
    ):
        assert issubclass(exc_type, FashionRecommenderError)


def test_a_caller_can_catch_the_whole_family() -> None:
    with pytest.raises(FashionRecommenderError):
        raise BigQueryJobError("boom")
