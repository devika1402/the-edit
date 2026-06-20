"""Build the typed staging tables from the raw tables (Phase 1).

Runs the ``sql/staging/*.sql`` transforms in order via the guarded query runner
(so ``maximum_bytes_billed`` always applies and SQL stays project-agnostic), then
validates the result: raw/staging row-count parity, the partitioning and
clustering on ``stg_transactions`` (see the teaching block in
``sql/staging/stg_transactions.sql``), and a complete ``age_band``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import bigquery

from core.bq import BigQueryClient
from core.config import Settings
from core.exceptions import DataValidationError

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "staging"

#: Staging transforms, in dependency order (all read from raw_* only).
STAGING_SQL_FILES = ["stg_transactions.sql", "stg_articles.sql", "stg_customers.sql"]

#: (staging table, raw table) pairs that must have identical row counts.
_ROW_PARITY = [
    ("stg_transactions", "raw_transactions"),
    ("stg_articles", "raw_articles"),
    ("stg_customers", "raw_customers"),
]


def build_staging(settings: Settings, client: bigquery.Client | None = None) -> dict[str, int]:
    """Build and validate the staging tables; return their row counts.

    Raises:
        BigQueryJobError: if a staging query fails.
        DataValidationError: if row parity, partition/cluster layout, or the
            derived ``age_band`` does not hold.
    """
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"

    for sql_file in STAGING_SQL_FILES:
        path = SQL_DIR / sql_file
        logger.info("building staging: %s", sql_file)
        runner.run_sql_file(path, default_dataset=default_dataset)

    counts = _validate_staging(runner, settings, default_dataset)
    logger.info("staging complete: %s", counts)
    return counts


def _scalar(runner: BigQueryClient, sql: str, default_dataset: str) -> int:
    """Run a single-row ``SELECT ... AS n`` and return ``n`` as an int."""
    rows = list(runner.query(sql, default_dataset=default_dataset))
    return int(rows[0]["n"])


def _validate_staging(
    runner: BigQueryClient, settings: Settings, default_dataset: str
) -> dict[str, int]:
    """Row-count parity, partition/cluster layout, and age_band completeness."""
    counts: dict[str, int] = {}
    for stg, raw in _ROW_PARITY:
        stg_rows = _scalar(runner, f"SELECT COUNT(*) AS n FROM {stg}", default_dataset)
        raw_rows = _scalar(runner, f"SELECT COUNT(*) AS n FROM {raw}", default_dataset)
        if stg_rows == 0:
            raise DataValidationError(f"{stg} is empty")
        if stg_rows != raw_rows:
            raise DataValidationError(
                f"row parity failed: {stg} has {stg_rows} rows, {raw} has {raw_rows}"
            )
        counts[stg] = stg_rows

    table = runner.client.get_table(
        f"{settings.gcp_project}.{settings.bq_dataset}.stg_transactions"
    )
    partitioning = table.time_partitioning
    if partitioning is None or partitioning.field != "t_dat":
        raise DataValidationError("stg_transactions is not partitioned by t_dat")
    if table.clustering_fields != ["article_id"]:
        raise DataValidationError(
            f"stg_transactions clustering is {table.clustering_fields}, expected ['article_id']"
        )

    null_bands = _scalar(
        runner, "SELECT COUNTIF(age_band IS NULL) AS n FROM stg_customers", default_dataset
    )
    if null_bands != 0:
        raise DataValidationError(f"stg_customers has {null_bands} null age_band values")

    logger.info("staging validated: row parity, partition/cluster, age_band all OK")
    return counts
