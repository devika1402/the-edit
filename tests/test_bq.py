"""The pure BigQuery helpers are testable without touching BigQuery.

``read_sql_file`` is plain file IO; ``build_job_config`` constructs a local
``QueryJobConfig`` object (no network, no client). The cost guardrail —
``maximum_bytes_billed`` coming from config — is asserted here. BigQuery itself
is not mocked; the client paths are exercised against the warehouse at runtime.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.bq import build_job_config, read_sql_file
from core.config import Settings
from core.exceptions import SqlFileError


def _settings(max_bytes: int = 123_456) -> Settings:
    return Settings(gcp_project="unit-test-project", bq_max_bytes_billed=max_bytes)


def test_read_sql_file_returns_contents(tmp_path: Path) -> None:
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("SELECT 1\n", encoding="utf-8")
    assert read_sql_file(sql_path) == "SELECT 1\n"


def test_read_sql_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(SqlFileError):
        read_sql_file(tmp_path / "does_not_exist.sql")


def test_read_sql_file_empty_raises(tmp_path: Path) -> None:
    sql_path = tmp_path / "blank.sql"
    sql_path.write_text("   \n\t", encoding="utf-8")
    with pytest.raises(SqlFileError):
        read_sql_file(sql_path)


def test_build_job_config_applies_byte_ceiling_from_config() -> None:
    config = build_job_config(_settings(max_bytes=777))
    assert config.maximum_bytes_billed == 777
    assert config.dry_run is False


def test_build_job_config_supports_dry_run() -> None:
    config = build_job_config(_settings(), dry_run=True)
    assert config.dry_run is True


def test_build_job_config_default_dataset_is_none_by_default() -> None:
    assert build_job_config(_settings()).default_dataset is None


def test_build_job_config_sets_default_dataset() -> None:
    config = build_job_config(_settings(), default_dataset="proj.ds")
    assert config.default_dataset is not None
    assert config.default_dataset.project == "proj"
    assert config.default_dataset.dataset_id == "ds"
