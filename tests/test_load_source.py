"""source_location routing is pure logic, tested without BigQuery or GCS."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings
from ingestion.load import source_location
from ingestion.schemas import RAW_TRANSACTIONS


def test_uses_gcs_uri_when_bucket_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(gcp_project="p", gcs_bucket="my-bucket", gcs_raw_prefix="raw")
    assert source_location(settings, RAW_TRANSACTIONS) == (
        "gs://my-bucket/raw/transactions_train.csv"
    )


def test_handles_empty_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(gcp_project="p", gcs_bucket="my-bucket", gcs_raw_prefix="")
    assert source_location(settings, RAW_TRANSACTIONS) == "gs://my-bucket/transactions_train.csv"


def test_falls_back_to_local_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(gcp_project="p", gcs_bucket=None, data_dir=Path("data"))
    assert source_location(settings, RAW_TRANSACTIONS) == str(
        Path("data") / "transactions_train.csv"
    )
