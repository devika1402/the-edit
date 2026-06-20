"""Config loads from the environment, applies defaults, and fails loudly."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import Settings, get_settings
from core.exceptions import ConfigError


def test_settings_reads_env_and_applies_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo
    monkeypatch.setenv("GCP_PROJECT", "unit-test-project")
    monkeypatch.setenv("BQ_LOCATION", "US")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.gcp_project == "unit-test-project"
    assert settings.bq_location == "US"  # from env
    assert settings.bq_dataset == "hm_recommender"  # default
    assert settings.bq_max_bytes_billed == 10_000_000_000  # default guardrail
    assert settings.top_k == 12  # default (MAP@12)


def test_missing_required_project_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ConfigError):
        get_settings()


def test_byte_ceiling_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Settings(gcp_project="p", bq_max_bytes_billed=0)
