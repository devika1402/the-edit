"""Typed BigQuery client wrapper with a SQL-file runner.

Every query path applies ``maximum_bytes_billed`` from config, so a query that
would scan more than the configured ceiling fails *before* it bills. This is the
project's cost guardrail. Heavy queries (notably the co-purchase
self-join) can be previewed with :meth:`BigQueryClient.estimate_bytes`, which
dry-runs the query and reports estimated bytes without scanning any data.

The ``google.cloud.bigquery`` import is deferred to call sites so that importing
``core.bq`` (for the pure, unit-testable helpers below) does not require the
BigQuery SDK or any credentials.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.config import Settings
from core.exceptions import BigQueryJobError, SqlFileError

if TYPE_CHECKING:
    from google.cloud import bigquery
    from google.cloud.bigquery.table import RowIterator

    QueryParam = bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter

logger = logging.getLogger(__name__)


def read_sql_file(path: Path) -> str:
    """Read and return the text of a ``.sql`` file.

    Raises:
        SqlFileError: if the file cannot be read or contains only whitespace.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SqlFileError(f"Could not read SQL file '{path}': {exc}") from exc
    if not text.strip():
        raise SqlFileError(f"SQL file '{path}' is empty")
    return text


def build_job_config(
    settings: Settings,
    *,
    dry_run: bool = False,
    query_parameters: Sequence[QueryParam] | None = None,
    default_dataset: str | None = None,
) -> bigquery.QueryJobConfig:
    """Build a ``QueryJobConfig`` with the cost guardrail applied.

    This is the single place ``maximum_bytes_billed`` is set, so no query can be
    issued without it. ``default_dataset`` (a ``"project.dataset"`` string) lets
    ``.sql`` files reference tables unqualified, keeping hard-coded project ids out
    of the SQL. The function is pure and side-effect free, which is why it is
    unit-tested directly without touching BigQuery.
    """
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=settings.bq_max_bytes_billed,
        dry_run=dry_run,
        use_query_cache=True,
        query_parameters=list(query_parameters) if query_parameters else [],
    )
    if default_dataset is not None:
        job_config.default_dataset = bigquery.DatasetReference.from_string(default_dataset)
    return job_config


class BigQueryClient:
    """A thin, typed wrapper over ``google.cloud.bigquery.Client``.

    The underlying client is constructed lazily on first use so that creating a
    ``BigQueryClient`` never requires credentials until a query is actually run.
    A pre-built client may be injected (useful for integration tests).
    """

    def __init__(self, settings: Settings, client: bigquery.Client | None = None) -> None:
        self._settings = settings
        self._client = client

    @property
    def client(self) -> bigquery.Client:
        """The underlying BigQuery client, created on first access."""
        client = self._client
        if client is None:
            from google.cloud import bigquery

            try:
                client = bigquery.Client(
                    project=self._settings.gcp_project,
                    location=self._settings.bq_location,
                )
            except Exception as exc:
                raise BigQueryJobError(
                    "Could not create a BigQuery client. Run `make auth` to set up "
                    f"Application Default Credentials. Original error: {exc}"
                ) from exc
            self._client = client
        return client

    def query(
        self,
        sql: str,
        *,
        query_parameters: Sequence[QueryParam] | None = None,
        default_dataset: str | None = None,
    ) -> RowIterator:
        """Run ``sql`` and return its rows, with the byte ceiling enforced."""
        job_config = build_job_config(
            self._settings,
            query_parameters=query_parameters,
            default_dataset=default_dataset,
        )
        try:
            job = self.client.query(sql, job_config=job_config)
            rows = job.result()
        except Exception as exc:
            raise BigQueryJobError(f"BigQuery query failed: {exc}") from exc
        logger.info(
            "query complete: %s rows, %s bytes billed",
            rows.total_rows,
            job.total_bytes_billed,
        )
        return rows

    def query_scalar(
        self,
        sql: str,
        *,
        query_parameters: Sequence[QueryParam] | None = None,
        default_dataset: str | None = None,
    ) -> Any:
        """Run an aggregate query and return its single value (first column, first row)."""
        rows = list(
            self.query(sql, query_parameters=query_parameters, default_dataset=default_dataset)
        )
        return rows[0][0]

    def estimate_bytes(
        self,
        sql: str,
        *,
        query_parameters: Sequence[QueryParam] | None = None,
        default_dataset: str | None = None,
    ) -> int:
        """Dry-run ``sql`` and return estimated bytes processed (no data scanned).

        Use this on the heavy queries to preview cost before running, per the
        project's cost guardrail.
        """
        job_config = build_job_config(
            self._settings,
            dry_run=True,
            query_parameters=query_parameters,
            default_dataset=default_dataset,
        )
        try:
            job = self.client.query(sql, job_config=job_config)
        except Exception as exc:
            raise BigQueryJobError(f"BigQuery dry-run failed: {exc}") from exc
        estimated = int(job.total_bytes_processed or 0)
        logger.info("dry-run estimate: %s bytes", estimated)
        return estimated

    def run_sql_file(
        self,
        path: Path | str,
        *,
        query_parameters: Sequence[QueryParam] | None = None,
        default_dataset: str | None = None,
    ) -> RowIterator:
        """Read a ``.sql`` file from disk and run it through :meth:`query`."""
        sql = read_sql_file(Path(path))
        return self.query(sql, query_parameters=query_parameters, default_dataset=default_dataset)
