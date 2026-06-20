"""Cold-start popularity fallback (shared component).

Concept — a cold-start fallback. A customer with no pre-cutoff history is absent
from ``feat_customer``, so they never enter the training matrix and the learned
ranker (and item-item CF) cannot score them. But they *do* have candidates — every
customer is given the global and per-segment top sellers in retrieval — so the
right behaviour is not to return nothing, it is to fall back to ranking those
candidates by recent popularity. That is what a production recommender does for an
unknown user, and it is what serving needs so the endpoint never returns an empty
list for a known customer.

This module is the single home of that behaviour: it fetches candidate features
without a holdout label (``sql/serving/candidate_features.sql``) and ranks the
cold customers' candidates by ``popularity_recent``. Eval, the guardrails harness,
and the serving endpoint all use it, so the fallback is defined once.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from core.bq import BigQueryClient, read_sql_file
from core.config import Settings
from models.interface import top_k_from_scores
from models.matrix import CATEGORICAL_FEATURES

logger = logging.getLogger(__name__)

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "serving" / "candidate_features.sql"


def fetch_candidate_features(
    settings: Settings,
    customers: Sequence[str],
    *,
    client: bigquery.Client | None = None,
) -> pd.DataFrame:
    """Fetch label-free candidate features for ``customers`` (serving + fallback).

    Returns one row per (customer, candidate) with the ranker's feature columns,
    an ``is_warm`` flag (False for cold customers with no ``feat_customer`` row), and
    categoricals cast to plain strings as the ranker expects. May be empty if none of
    the customers have candidates.
    """
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    sql = read_sql_file(SQL_PATH)
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date),
        bigquery.ScalarQueryParameter("window", "INT64", settings.copurchase_window_days),
        bigquery.ArrayQueryParameter("customers", "STRING", list(customers)),
    ]
    rows = runner.query(sql, query_parameters=params, default_dataset=default_dataset)
    frame: pd.DataFrame = rows.to_dataframe()
    if not frame.empty:
        for col in CATEGORICAL_FEATURES:
            frame[col] = frame[col].fillna("unknown").astype(str)
    return frame


def popularity_recommend(frame: pd.DataFrame, k: int) -> pd.DataFrame:
    """Rank each customer's candidates by recent popularity; return top-K per customer."""
    scored = frame.rename(columns={"popularity_recent": "score"})
    return top_k_from_scores(scored, k)


def popularity_fallback_recs(
    settings: Settings,
    customers: Sequence[str],
    k: int,
    *,
    client: bigquery.Client | None = None,
) -> dict[str, list[str]]:
    """Top-K popularity recommendations per cold customer, as ``{customer: [ids]}``."""
    if not customers:
        return {}
    frame = fetch_candidate_features(settings, customers, client=client)
    if frame.empty:
        logger.warning("no candidates for %s fallback customers", len(customers))
        return {}
    ranked = popularity_recommend(frame, k).sort_values(["customer_id", "rank"])
    return {
        str(customer): group["article_id"].tolist()
        for customer, group in ranked.groupby("customer_id", sort=False)
    }
