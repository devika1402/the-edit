"""Candidate recall against the holdout week (Phase 3).

Concept — why retrieval recall is the ceiling on final performance. The ranker
can only re-order what retrieval hands it. If a customer's true next purchase is
never in their candidate set, no ranking model can recover it. So candidate
recall — of the articles a customer actually bought in the holdout, the fraction
that appear in their candidates — is the hard upper bound on the final hit rate.
Phase 4's ranker is judged against this ceiling, not against perfection; if recall
is weak, retrieval is revised before any modelling (PRD §9).

Recall is reported per cohort (warm customers have pre-cutoff history and richer
signals; cold customers fall back to popularity) and overall, as both the
per-customer mean and the micro-average over all holdout purchases.
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import bigquery

from core.bq import BigQueryClient
from core.config import Settings

logger = logging.getLogger(__name__)

_RECALL_SQL = """
WITH holdout AS (
  SELECT DISTINCT customer_id, article_id
  FROM stg_transactions
  WHERE t_dat > @cutoff
),
per_customer AS (
  SELECT
    h.customer_id,
    COUNT(*) AS n_holdout,
    COUNTIF(c.customer_id IS NOT NULL) AS n_hit
  FROM holdout AS h
  LEFT JOIN candidates AS c USING (customer_id, article_id)
  GROUP BY h.customer_id
),
labelled AS (
  SELECT
    pc.n_holdout,
    pc.n_hit,
    IF(fc.customer_id IS NOT NULL, 'warm', 'cold') AS cohort
  FROM per_customer AS pc
  LEFT JOIN feat_customer AS fc USING (customer_id)
)
SELECT
  cohort,
  COUNT(*) AS n_customers,
  SUM(n_holdout) AS holdout_articles,
  SUM(n_hit) AS hits,
  ROUND(AVG(n_hit / n_holdout), 4) AS mean_recall,
  ROUND(SAFE_DIVIDE(SUM(n_hit), SUM(n_holdout)), 4) AS micro_recall
FROM labelled
GROUP BY ROLLUP(cohort)
ORDER BY cohort NULLS LAST
"""
# The ROLLUP grand-total row has cohort = NULL; callers relabel it 'ALL'.


def measure_recall(
    settings: Settings, client: bigquery.Client | None = None
) -> list[dict[str, Any]]:
    """Measure candidate recall against the holdout; return one row per cohort + ALL."""
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    cutoff = bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date)

    rows = [
        dict(row)
        for row in runner.query(
            _RECALL_SQL, query_parameters=[cutoff], default_dataset=default_dataset
        )
    ]
    for row in rows:
        logger.info(
            "recall[%s]: customers=%s mean=%s micro=%s",
            row["cohort"] or "ALL",
            row["n_customers"],
            row["mean_recall"],
            row["micro_recall"],
        )
    return rows
