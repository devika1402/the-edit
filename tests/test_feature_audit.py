"""The D-11 leakage-gate date check is pure logic, tested without BigQuery."""

from __future__ import annotations

from datetime import date

import pytest

from core.exceptions import DataValidationError
from features.audit import assert_date_within_cutoff

CUTOFF = date(2020, 9, 15)


def test_passes_when_max_date_on_or_before_cutoff() -> None:
    assert_date_within_cutoff("x", date(2020, 9, 15), CUTOFF)  # equal is allowed
    assert_date_within_cutoff("x", date(2020, 9, 1), CUTOFF)  # earlier is allowed


def test_passes_when_no_rows() -> None:
    assert_date_within_cutoff("x", None, CUTOFF)  # nothing built means nothing to leak


def test_raises_when_max_date_after_cutoff() -> None:
    with pytest.raises(DataValidationError):
        assert_date_within_cutoff("feat_item.last_sale_date", date(2020, 9, 16), CUTOFF)
