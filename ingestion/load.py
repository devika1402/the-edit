"""Batch-load the source H&M CSVs into ``raw_*`` BigQuery tables (Phase 1).

Only ``transactions_train.csv``, ``articles.csv``, and ``customers.csv`` are
loaded; the image files are skipped (D-4). Loads run as batch jobs (free shared
slot pool) with explicit schemas and ``WRITE_TRUNCATE``, which is what makes the
loader idempotent: re-running replaces each table cleanly. After each load we
assert the table is non-empty, its column names match the declared schema, and
its row count matches the source (fail loudly, fail early).

Source selection (D-3 → billing enabled):
- When ``settings.gcs_bucket`` is set (the project default), each table loads
  from ``gs://<bucket>/<prefix>/<file>`` via a server-side ``load_table_from_uri``
  — no multi-gigabyte upload from the laptop. Source-match is checked against the
  canonical H&M row count, since a GCS object cannot be line-counted locally.
- Otherwise it falls back to a local file under ``settings.data_dir`` and checks
  the count against the file's own line count.
"""

from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import bigquery

from core.bq import BigQueryClient
from core.config import Settings
from core.exceptions import BigQueryJobError, DataValidationError
from ingestion.checks import count_csv_data_rows, within_tolerance
from ingestion.schemas import RAW_TABLES, RawTable

logger = logging.getLogger(__name__)


def source_location(settings: Settings, raw: RawTable) -> str:
    """Resolve where a raw table's CSV lives: a ``gs://`` URI or a local path."""
    if settings.gcs_bucket:
        prefix = settings.gcs_raw_prefix.strip("/")
        object_name = f"{prefix}/{raw.source_file}" if prefix else raw.source_file
        return f"gs://{settings.gcs_bucket}/{object_name}"
    return str(settings.data_dir / raw.source_file)


def ensure_dataset(client: bigquery.Client, settings: Settings) -> None:
    """Create the target dataset if needed and clear any default expirations.

    A dataset created while the project was in BigQuery sandbox carries a 60-day
    default table/partition expiration. Because ``t_dat`` is historical
    (2018-2020), a partitioned table inheriting that would have every partition
    expire the moment it is written, leaving it empty. Now that billing is
    enabled we clear both defaults, idempotently, so tables and partitions persist.
    """
    dataset_id = f"{settings.gcp_project}.{settings.bq_dataset}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = settings.bq_location
    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        if (
            dataset.default_partition_expiration_ms is not None
            or dataset.default_table_expiration_ms is not None
        ):
            dataset.default_partition_expiration_ms = None
            dataset.default_table_expiration_ms = None
            client.update_dataset(
                dataset,
                ["default_partition_expiration_ms", "default_table_expiration_ms"],
            )
            logger.info("cleared sandbox-era default expirations on %s", dataset_id)
    except Exception as exc:
        raise BigQueryJobError(f"Could not ensure dataset '{dataset_id}': {exc}") from exc
    logger.info("dataset ready: %s @ %s", dataset_id, settings.bq_location)


def load_raw_tables(settings: Settings, client: bigquery.Client | None = None) -> dict[str, int]:
    """Load each source CSV into its ``raw_*`` table and return row counts.

    Args:
        settings: pipeline configuration (project, dataset, GCS or data dir).
        client: an optional pre-built client (mainly for tests); otherwise one is
            created from ADC.

    Returns:
        A mapping of raw table name to loaded row count.

    Raises:
        BigQueryJobError: if a load job fails or the client cannot be built.
        DataValidationError: if a loaded table is empty, has the wrong schema, or
            its row count does not match the source.
    """
    bq_client = BigQueryClient(settings, client=client).client
    ensure_dataset(bq_client, settings)

    counts: dict[str, int] = {}
    for raw in RAW_TABLES:
        counts[raw.table] = _load_one(bq_client, settings, raw)
    logger.info("raw load complete: %s", counts)
    return counts


def _schema_fields(raw: RawTable) -> list[bigquery.SchemaField]:
    """Turn the declarative column list into BigQuery ``SchemaField`` objects."""
    return [
        bigquery.SchemaField(column.name, column.field_type, mode=column.mode)
        for column in raw.columns
    ]


def _load_one(client: bigquery.Client, settings: Settings, raw: RawTable) -> int:
    """Load a single CSV (GCS or local) into its raw table and validate it."""
    source = source_location(settings, raw)
    is_gcs = source.startswith("gs://")
    if not is_gcs and not Path(source).is_file():
        raise DataValidationError(
            f"Source CSV not found: {source}. Set GCS_BUCKET to load from GCS, or "
            f"place the H&M files under '{settings.data_dir}/'."
        )

    table_id = f"{settings.gcp_project}.{settings.bq_dataset}.{raw.table}"
    job_config = bigquery.LoadJobConfig(
        schema=_schema_fields(raw),
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        max_bad_records=0,
        allow_quoted_newlines=True,
        autodetect=False,
    )

    logger.info("loading %s -> %s", source, table_id)
    try:
        if is_gcs:
            job = client.load_table_from_uri(source, table_id, job_config=job_config)
        else:
            with Path(source).open("rb") as handle:
                job = client.load_table_from_file(handle, table_id, job_config=job_config)
        job.result()
    except Exception as exc:
        raise BigQueryJobError(f"Load of '{raw.table}' failed: {exc}") from exc

    loaded = int(job.output_rows or 0)
    table = client.get_table(table_id)
    _validate_raw(raw, table, loaded, source)
    logger.info("loaded %s: %s rows", raw.table, loaded)
    return loaded


def _validate_raw(raw: RawTable, table: bigquery.Table, loaded: int, source: str) -> None:
    """Boundary checks: non-empty, schema matches, count matches the source."""
    if loaded == 0:
        raise DataValidationError(f"{raw.table} loaded 0 rows from {source}")

    actual_names = [field.name for field in table.schema]
    expected_names = [column.name for column in raw.columns]
    if actual_names != expected_names:
        raise DataValidationError(
            f"{raw.table} schema mismatch: loaded {actual_names}, expected {expected_names}"
        )

    if source.startswith("gs://"):
        if not within_tolerance(loaded, raw.expected_rows, rel=0.001):
            raise DataValidationError(
                f"{raw.table} loaded {loaded:,} rows, expected ~{raw.expected_rows:,} "
                "(canonical H&M size); the GCS upload may be incomplete"
            )
        logger.info("validated %s: %s rows (canonical ~%s)", raw.table, loaded, raw.expected_rows)
    else:
        source_rows = count_csv_data_rows(Path(source))
        if not within_tolerance(loaded, source_rows):
            raise DataValidationError(
                f"{raw.table} row count {loaded} is not within tolerance of source {source_rows}"
            )
        logger.info("validated %s: %s rows (source ~%s)", raw.table, loaded, source_rows)
