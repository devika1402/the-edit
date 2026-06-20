"""Centralised, typed configuration.

A single :class:`Settings` object reads from environment variables and an
optional ``.env`` file. Nothing in the pipeline hard-codes a project id, dataset
name, or path; everything flows from here. ``.env.example`` documents every
field. ``get_settings()`` is cached so the file and environment are parsed once.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.exceptions import ConfigError


class Settings(BaseSettings):
    """Typed settings for the whole pipeline, loaded from env and ``.env``.

    Field names map to upper-case environment variables (case-insensitive), so
    ``gcp_project`` is read from ``GCP_PROJECT``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Google Cloud / BigQuery -------------------------------------------
    gcp_project: str = Field(
        ...,
        description="GCP project id that owns the BigQuery dataset. Required; no default.",
    )
    bq_dataset: str = Field(
        default="hm_recommender",
        description="BigQuery dataset holding raw, staging, feature, and candidate tables.",
    )
    bq_location: str = Field(
        default="EU",
        description="BigQuery dataset location (the H&M data is European).",
    )
    bq_max_bytes_billed: int = Field(
        default=10_000_000_000,
        gt=0,
        description=(
            "Cost guardrail: maximum_bytes_billed applied to every query. A query "
            "that would scan more than this fails instead of billing (default 10 GB)."
        ),
    )
    google_application_credentials: Path | None = Field(
        default=None,
        description=(
            "Optional path to a service-account key, used in CI. Local development "
            "uses Application Default Credentials (`make auth`) and leaves this unset."
        ),
    )
    gcs_bucket: str | None = Field(
        default=None,
        description=(
            "GCS bucket holding the raw CSVs. When set, ingestion loads from "
            "gs:// URIs instead of local files (the default for this project)."
        ),
    )
    gcs_raw_prefix: str = Field(
        default="raw",
        description="Object-name prefix under the bucket for the raw CSVs (e.g. 'raw').",
    )

    # --- Filesystem paths ---------------------------------------------------
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory holding the source H&M CSVs (kept out of version control).",
    )
    artifacts_dir: Path = Field(
        default=Path("artifacts"),
        description="Directory for trained model artifacts and the saved feature list.",
    )

    # --- Pipeline knobs (locked scoping decisions live in config, not code) -
    customer_sample_size: int = Field(
        default=100_000,
        gt=0,
        description="Number of customers sampled for ranker training (D-8).",
    )
    copurchase_window_days: int = Field(
        default=90,
        gt=0,
        description="Recent-window length for the co-purchase self-join (D-6).",
    )
    feature_cutoff_date: date = Field(
        default=date(2020, 9, 15),
        description=(
            "As-of date for feature computation (D-11). Features aggregate only "
            "transactions with t_dat <= this date; the holdout is t_dat > this date. "
            "Default leaves the final week (2020-09-16..09-22) of the H&M data as holdout."
        ),
    )
    item_popularity_window_days: int = Field(
        default=30,
        gt=0,
        description="Recent-window length (days, ending at the cutoff) for feat_item popularity.",
    )
    retrieval_top_n: int = Field(
        default=200,
        gt=0,
        description="Per-customer cap for each retrieval signal (global, segment, co-purchase).",
    )
    retrieval_copurchase_neighbors: int = Field(
        default=100,
        gt=0,
        description="Co-occurrence neighbours kept per article in item_copurchase (D-6).",
    )
    train_sample_customers: int = Field(
        default=30_000,
        gt=0,
        description="Customers sampled from the train split to train the ranker (D-8).",
    )
    max_negatives_per_customer: int = Field(
        default=50,
        gt=0,
        description="Cap on negative (unpurchased) candidates kept per customer for training.",
    )
    test_fraction: float = Field(
        default=0.2,
        gt=0.0,
        lt=1.0,
        description="Fraction of candidate-having customers held out as the Phase 5 test set.",
    )
    random_seed: int = Field(default=42, description="Seed for customer split and sampling.")
    ranker_iterations: int = Field(
        default=1000, gt=0, description="Max CatBoostRanker trees (early stopping may use fewer)."
    )
    ranker_learning_rate: float = Field(default=0.1, gt=0.0, description="CatBoostRanker LR.")
    ranker_depth: int = Field(default=6, gt=0, description="CatBoostRanker tree depth.")
    top_k: int = Field(
        default=12,
        gt=0,
        description="Recommendation list length; MAP@12 is the primary metric (D-9).",
    )

    # --- Logging ------------------------------------------------------------
    log_level: str = Field(
        default="INFO",
        description="Root log level: DEBUG, INFO, WARNING, ERROR, or CRITICAL.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, parsed once and cached.

    Raises:
        ConfigError: if a required setting is missing or a value fails validation.
    """
    try:
        return Settings()  # all values come from the environment and .env
    except ValidationError as exc:
        raise ConfigError(f"Invalid or missing configuration: {exc}") from exc
