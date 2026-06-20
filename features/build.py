"""Build the materialised feature tables (Phase 2).

Concept — a feature store, in miniature. Precomputing features once and reading
them many times, instead of recomputing aggregates per request, is the core idea
behind a feature store. ``feat_customer`` and ``feat_item`` are the lightweight
BigQuery version: the ranker (Phase 4) and the serving endpoint (Phase 7) read
these small tables repeatedly instead of re-scanning 31M transactions each time.

Every feature is computed strictly as of ``settings.feature_cutoff_date`` (D-11),
passed as the ``@cutoff`` query parameter so it is never hard-coded in SQL. After
the tables build, ranges and nulls are validated and the leakage gate
(:func:`features.audit.leakage_audit`) must pass before the phase is considered done.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import bigquery

from core.bq import BigQueryClient
from core.config import Settings
from core.exceptions import DataValidationError
from features.audit import leakage_audit, scalar

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "features"


def build_features(settings: Settings, client: bigquery.Client | None = None) -> dict[str, int]:
    """Build feat_customer and feat_item as of the cutoff, validate, gate, count.

    Raises:
        BigQueryJobError: if a feature query fails.
        DataValidationError: if a range/null check or the D-11 leakage gate fails.
    """
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    cutoff = bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date)
    window = bigquery.ScalarQueryParameter(
        "pop_window", "INT64", settings.item_popularity_window_days
    )

    logger.info("building feat_customer as of %s", settings.feature_cutoff_date)
    runner.run_sql_file(
        SQL_DIR / "feat_customer.sql", query_parameters=[cutoff], default_dataset=default_dataset
    )
    logger.info(
        "building feat_item as of %s (popularity window %sd)",
        settings.feature_cutoff_date,
        settings.item_popularity_window_days,
    )
    runner.run_sql_file(
        SQL_DIR / "feat_item.sql",
        query_parameters=[cutoff, window],
        default_dataset=default_dataset,
    )

    counts = _validate_features(runner, default_dataset)
    leakage_audit(runner, settings, default_dataset)
    logger.info("features complete: %s", counts)
    return counts


def _check_zero(runner: BigQueryClient, label: str, sql: str, default_dataset: str) -> None:
    """Run a ``SELECT COUNTIF(...)`` check and raise if it is not zero."""
    violations = int(scalar(runner, sql, default_dataset))
    if violations != 0:
        raise DataValidationError(f"{label}: {violations} rows violate the check")


def _validate_features(runner: BigQueryClient, default_dataset: str) -> dict[str, int]:
    """Null and range checks on both feature tables; returns row counts."""
    customer_rows = int(scalar(runner, "SELECT COUNT(*) FROM feat_customer", default_dataset))
    item_rows = int(scalar(runner, "SELECT COUNT(*) FROM feat_item", default_dataset))
    if customer_rows == 0 or item_rows == 0:
        raise DataValidationError(
            f"empty feature table (feat_customer={customer_rows}, feat_item={item_rows})"
        )

    _check_zero(
        runner,
        "feat_customer null/range",
        "SELECT COUNTIF("
        "customer_id IS NULL OR n_transactions < 1 OR monetary_index <= 0 "
        "OR share_online < 0 OR share_online > 1 OR age_band IS NULL"
        ") FROM feat_customer",
        default_dataset,
    )
    _check_zero(
        runner,
        "feat_item null/range",
        "SELECT COUNTIF("
        "article_id IS NULL OR n_purchases < 1 OR price_tier NOT BETWEEN 1 AND 5"
        ") FROM feat_item",
        default_dataset,
    )
    return {"feat_customer": customer_rows, "feat_item": item_rows}
