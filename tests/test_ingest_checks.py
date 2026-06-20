"""Pure ingestion helpers, tested on tiny fixtures (no BigQuery)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.checks import count_csv_data_rows, within_tolerance


def test_within_tolerance_exact_and_close() -> None:
    assert within_tolerance(100, 100)
    assert within_tolerance(1000, 1005)  # 0.5% < default 1%
    assert not within_tolerance(1000, 1100)  # 10% off


def test_within_tolerance_zero_expected() -> None:
    assert within_tolerance(0, 0)
    assert not within_tolerance(5, 0)


def test_within_tolerance_rejects_negative() -> None:
    with pytest.raises(ValueError):
        within_tolerance(-1, 10)


def test_count_csv_data_rows_excludes_header(tmp_path: Path) -> None:
    csv = tmp_path / "data.csv"
    csv.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    assert count_csv_data_rows(csv) == 2


def test_count_csv_data_rows_header_only(tmp_path: Path) -> None:
    csv = tmp_path / "header.csv"
    csv.write_text("a,b,c\n", encoding="utf-8")
    assert count_csv_data_rows(csv) == 0


def test_count_csv_data_rows_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        count_csv_data_rows(tmp_path / "nope.csv")
