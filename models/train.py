"""Phase 4 orchestration: build matrix, split, train all three, glance at the ranker.

The test split is reserved for Phase 5; the weak-ranker glance here uses a small
validation slice carved from the training customers. Only a sampled set of
customers is pulled, with negatives capped per customer in SQL, so the matrix is
laptop-sized. The D-11 leakage gate runs once as a precondition.
"""

from __future__ import annotations

import logging

import pandas as pd

from core.bq import BigQueryClient
from core.config import Settings
from features.audit import leakage_audit
from models.baselines import ItemItemCFRecommender, PopularityRecommender
from models.matrix import build_matrix
from models.ranker import CatBoostRecommender, save_ranker, train_ranker
from models.sampling import split_customers, subsample

logger = logging.getLogger(__name__)

_VALID_FRACTION = 0.1  # of the training customers, held out for the glance
_NO_CAP = 10**9  # "keep all negatives" sentinel for the full validation pull


def hit_rate_at_k(recommended: pd.DataFrame, truth: pd.DataFrame, k: int) -> float:
    """Fraction of truth-customers with at least one true article in their top-k."""
    top = recommended[recommended["rank"] <= k][["customer_id", "article_id"]]
    hits = truth.merge(top, on=["customer_id", "article_id"], how="inner")
    customers = truth["customer_id"].nunique()
    return 0.0 if customers == 0 else hits["customer_id"].nunique() / customers


def run_training(settings: Settings) -> dict[str, float | int]:
    """Build the matrix, train baselines + ranker, save artifacts, return the glance."""
    runner = BigQueryClient(settings)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    leakage_audit(runner, settings, default_dataset)  # D-11 gate precondition

    customers = [
        str(row[0])
        for row in runner.query(
            "SELECT DISTINCT customer_id FROM candidates", default_dataset=default_dataset
        )
    ]
    train_customers, _test = split_customers(
        customers, settings.test_fraction, settings.random_seed
    )
    fit_pool, valid_customers = split_customers(
        train_customers, _VALID_FRACTION, settings.random_seed
    )
    fit_customers = subsample(fit_pool, settings.train_sample_customers, settings.random_seed)

    # Fit: negatives capped (laptop-sized). Validation: FULL candidates, so the
    # glance is an honest comparison (capping would bias it toward popularity).
    fit = build_matrix(
        settings,
        fit_customers,
        max_negatives=settings.max_negatives_per_customer,
        client=runner.client,
    )
    valid = build_matrix(settings, valid_customers, max_negatives=_NO_CAP, client=runner.client)

    model, features = train_ranker(fit, settings)
    model_path = save_ranker(model, features, settings.artifacts_dir)
    logger.info("saved ranker to %s (%s features)", model_path, len(features))

    truth = valid[valid["label"] == 1][["customer_id", "article_id"]]
    k = settings.top_k
    pop = PopularityRecommender().recommend(valid, k)
    cf = ItemItemCFRecommender().recommend(valid, k)
    ranked = CatBoostRecommender(model, features).recommend(valid, k)
    glance: dict[str, float | int] = {
        "fit_customers": int(fit["customer_id"].nunique()),
        "valid_customers": int(valid["customer_id"].nunique()),
        f"popularity_hit_rate@{k}": round(hit_rate_at_k(pop, truth, k), 4),
        f"item_item_cf_hit_rate@{k}": round(hit_rate_at_k(cf, truth, k), 4),
        f"ranker_hit_rate@{k}": round(hit_rate_at_k(ranked, truth, k), 4),
    }
    logger.info("training glance: %s", glance)
    return glance
