"""Build the candidate-feature matrix that all three approaches consume (Phase 4).

One row per (customer, candidate): customer features, item features, the retrieval
signals, and the holdout label. Leakage-safe — every feature is as of the cutoff
(the D-11-gated feat_* tables); only the label looks at the holdout window. The
D-11 leakage gate runs as a precondition before the matrix is built.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from core.bq import BigQueryClient, read_sql_file
from core.config import Settings
from core.exceptions import DataValidationError

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "features" / "training_matrix.sql"

NUMERIC_FEATURES = [
    "recency_days",
    "tenure_days",
    "n_transactions",
    "n_active_days",
    "monetary_index",
    "price_affinity_index",
    "n_distinct_categories",
    "share_online",
    "n_purchases",
    "popularity_recent",
    "recency_last_sale_days",
    "recency_first_sale_days",
    "avg_price",
    "copurchase_score",
    "is_repurchase",
    "is_copurchase",
    "is_top_global",
    "is_top_segment",
    "is_variant",
    "is_category",
    "n_sources",
    "category_match",
    "colour_match",
    "price_ratio",
]
CATEGORICAL_FEATURES = [
    "age_band",
    "dominant_category",
    "dominant_colour",
    "price_tier",
    "product_group_name",
    "department_name",
    "colour_group_name",
    "garment_group_name",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_matrix(
    settings: Settings,
    customers: Sequence[str],
    *,
    max_negatives: int,
    client: bigquery.Client | None = None,
) -> pd.DataFrame:
    """Build the (customer, candidate, features, label) matrix for ``customers``.

    Only the listed customers are pulled, and negatives are capped at
    ``max_negatives`` per customer in SQL, so the matrix stays laptop-sized.
    Positives are always kept. The D-11 leakage gate is the caller's precondition.

    Raises:
        DataValidationError: if the matrix is empty or has no positive labels.
        BigQueryJobError: if the query fails.
    """
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"

    sql = read_sql_file(SQL_PATH)
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date),
        bigquery.ScalarQueryParameter("window", "INT64", settings.copurchase_window_days),
        bigquery.ScalarQueryParameter("max_negatives", "INT64", max_negatives),
        bigquery.ArrayQueryParameter("customers", "STRING", list(customers)),
    ]
    rows = runner.query(sql, query_parameters=params, default_dataset=default_dataset)
    frame: pd.DataFrame = rows.to_dataframe()  # uses the BQ Storage API when installed

    if frame.empty or int(frame["label"].sum()) == 0:
        raise DataValidationError("training matrix is empty or has no positive labels")

    # CatBoost wants plain-str categorical columns (not pandas nullable "string").
    for col in CATEGORICAL_FEATURES:
        frame[col] = frame[col].fillna("unknown").astype(str)

    logger.info(
        "matrix: %s rows, %s positives (%s customers)",
        len(frame),
        int(frame["label"].sum()),
        len(customers),
    )
    return frame
