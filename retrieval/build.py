"""Build the retrieval tables: item_copurchase, then candidates (Phase 3).

The co-purchase self-join is the heaviest query in the project, so it is
dry-run first and its estimated bytes are logged before it runs (the project's
cost guardrail). Candidates are then unioned from four signals and validated.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import bigquery

from core.bq import BigQueryClient, read_sql_file
from core.config import Settings
from core.exceptions import DataValidationError

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "retrieval"


def build_candidates(settings: Settings, client: bigquery.Client | None = None) -> dict[str, int]:
    """Dry-run + build item_copurchase and candidates; return counts and the estimate.

    Raises:
        BigQueryJobError: if a retrieval query fails.
        DataValidationError: if a built table is empty or malformed.
    """
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"

    cutoff = bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date)
    window = bigquery.ScalarQueryParameter("window", "INT64", settings.copurchase_window_days)
    neighbors = bigquery.ScalarQueryParameter(
        "neighbors", "INT64", settings.retrieval_copurchase_neighbors
    )
    top_n = bigquery.ScalarQueryParameter("top_n", "INT64", settings.retrieval_top_n)

    # 1. Dry-run the co-purchase self-join and report estimated bytes BEFORE running.
    copurchase_sql = read_sql_file(SQL_DIR / "item_copurchase.sql")
    estimated_bytes = runner.estimate_bytes(
        copurchase_sql,
        query_parameters=[cutoff, window, neighbors],
        default_dataset=default_dataset,
    )
    logger.info(
        "co-purchase self-join dry-run estimate: %s bytes (~%.2f GB) over a %sd window",
        f"{estimated_bytes:,}",
        estimated_bytes / 1e9,
        settings.copurchase_window_days,
    )

    # 2. Build item_copurchase (the self-join), then candidates.
    logger.info("building item_copurchase")
    runner.query(
        copurchase_sql,
        query_parameters=[cutoff, window, neighbors],
        default_dataset=default_dataset,
    )
    logger.info("building candidates (top_n=%s per signal)", settings.retrieval_top_n)
    runner.run_sql_file(
        SQL_DIR / "candidates.sql",
        query_parameters=[cutoff, window, top_n],
        default_dataset=default_dataset,
    )

    counts = _validate(runner, default_dataset)
    counts["copurchase_estimated_bytes"] = estimated_bytes
    logger.info("retrieval build complete: %s", counts)
    return counts


def _validate(runner: BigQueryClient, default_dataset: str) -> dict[str, int]:
    """Boundary checks; returns row/customer counts."""
    copurchase_rows = int(
        runner.query_scalar("SELECT COUNT(*) FROM item_copurchase", default_dataset=default_dataset)
    )
    candidate_rows = int(
        runner.query_scalar("SELECT COUNT(*) FROM candidates", default_dataset=default_dataset)
    )
    candidate_customers = int(
        runner.query_scalar(
            "SELECT COUNT(DISTINCT customer_id) FROM candidates", default_dataset=default_dataset
        )
    )
    if copurchase_rows == 0 or candidate_rows == 0:
        raise DataValidationError(
            f"empty retrieval table: item_copurchase={copurchase_rows}, candidates={candidate_rows}"
        )

    bad = int(
        runner.query_scalar(
            "SELECT COUNTIF(customer_id IS NULL OR article_id IS NULL "
            "OR ARRAY_LENGTH(sources) = 0) FROM candidates",
            default_dataset=default_dataset,
        )
    )
    if bad != 0:
        raise DataValidationError(f"candidates has {bad} rows with null keys or no source")

    return {
        "item_copurchase_rows": copurchase_rows,
        "candidates_rows": candidate_rows,
        "candidate_customers": candidate_customers,
    }
