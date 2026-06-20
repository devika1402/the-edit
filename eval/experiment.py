"""Offline experiment harness: score every model on the same holdout (Phase 5).

Concept — temporal holdout and leakage. A recommender is judged by hiding a future
window and predicting it: features as of the cutoff (2020-09-15), evaluated against
the holdout week (2020-09-16..22). The cardinal sin is leakage — letting any signal
from the prediction window into the features. This project avoids it two ways: the
features are the D-11-gated as-of-cutoff tables, and the customers scored here are
the 20% held out and never seen during Phase 4 training. So the numbers below are an
honest estimate of how the models would do on customers and a week they never saw.

Concept — bootstrap confidence intervals. A single average can mislead: is the
ranker really better, or did it get lucky on this set of customers? To find out we
resample the customers with replacement many times, recompute each model's MAP@12
on every resample, and read the 2.5/97.5 percentiles as a 95% interval. The lift of
the ranker over popularity gets the same treatment, plus a one-sided significance
check (the fraction of resamples where the lift is not positive). This is the honest
offline mirror of the confidence interval an online A/B test would report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery
from numpy.typing import NDArray

from core.bq import BigQueryClient
from core.config import Settings
from eval.metrics import (
    average_precision_at_k,
    mean_average_precision_at_k,
    mean_ndcg_at_k,
    mean_recall_at_k,
)
from models.baselines import ItemItemCFRecommender, PopularityRecommender
from models.fallback import popularity_fallback_recs
from models.interface import Recommender
from models.matrix import build_matrix
from models.ranker import CatBoostRecommender, load_ranker
from models.sampling import split_customers

logger = logging.getLogger(__name__)

_NO_CAP = 10**9


@dataclass
class ExperimentResult:
    """The Phase 5 deliverable: a results table plus bootstrap intervals."""

    table: pd.DataFrame  # one row per model: MAP@k, Recall@k, NDCG@k
    map_ci: dict[str, tuple[float, float, float]]  # model -> (mean, lo, hi) for MAP@k
    lift: tuple[float, float, float, float]  # ranker vs popularity: (lift, lo, hi, p_value)
    k: int
    n_customers: int


def bootstrap_metric_ci(
    values: NDArray[np.float64], *, n_bootstrap: int, seed: int
) -> tuple[float, float, float]:
    """Return (mean, 2.5th, 97.5th) of the mean under customer resampling."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_bootstrap, len(values)))
    samples = values[idx].mean(axis=1)
    return (
        float(values.mean()),
        float(np.percentile(samples, 2.5)),
        float(np.percentile(samples, 97.5)),
    )


def bootstrap_lift_ci(
    treatment: NDArray[np.float64],
    baseline: NDArray[np.float64],
    *,
    n_bootstrap: int,
    seed: int,
) -> tuple[float, float, float, float]:
    """Bootstrap the mean lift (treatment - baseline) by resampling customers.

    Returns ``(lift, ci_low, ci_high, p_value)`` where ``p_value`` is the one-sided
    fraction of resamples in which the lift is not positive (treatment not better).
    """
    rng = np.random.default_rng(seed)
    n = len(treatment)
    idx = rng.integers(0, n, size=(n_bootstrap, n))
    lift_samples = treatment[idx].mean(axis=1) - baseline[idx].mean(axis=1)
    lift = float(treatment.mean() - baseline.mean())
    return (
        lift,
        float(np.percentile(lift_samples, 2.5)),
        float(np.percentile(lift_samples, 97.5)),
        float((lift_samples <= 0).mean()),
    )


def _test_customers(runner: BigQueryClient, settings: Settings, default_dataset: str) -> list[str]:
    customers = [
        str(row[0])
        for row in runner.query(
            "SELECT DISTINCT customer_id FROM candidates", default_dataset=default_dataset
        )
    ]
    _train, test = split_customers(customers, settings.test_fraction, settings.random_seed)
    return test


def _ground_truth(
    runner: BigQueryClient, settings: Settings, default_dataset: str, customers: list[str]
) -> dict[str, list[str]]:
    """The holdout purchases per customer (relevant set)."""
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ScalarQueryParameter("cutoff", "DATE", settings.feature_cutoff_date),
        bigquery.ArrayQueryParameter("test", "STRING", customers),
    ]
    rows = runner.query(
        "SELECT customer_id, article_id FROM stg_transactions "
        "WHERE t_dat > @cutoff AND customer_id IN UNNEST(@test)",
        query_parameters=params,
        default_dataset=default_dataset,
    )
    truth: dict[str, list[str]] = {}
    for row in rows:
        truth.setdefault(row["customer_id"], []).append(row["article_id"])
    return truth


def _recommendations(model: Recommender, matrix: pd.DataFrame, k: int) -> dict[str, list[str]]:
    """Top-k article ids per customer, in rank order."""
    recs = model.recommend(matrix, k).sort_values(["customer_id", "rank"])
    return {
        str(customer): group["article_id"].tolist()
        for customer, group in recs.groupby("customer_id", sort=False)
    }


def _build_models(settings: Settings) -> dict[str, Recommender]:
    model, features = load_ranker(settings.artifacts_dir)
    return {
        "popularity": PopularityRecommender(),
        "item_item_cf": ItemItemCFRecommender(),
        "ranker": CatBoostRecommender(model, features),
    }


def run_experiment(
    settings: Settings,
    client: bigquery.Client | None = None,
    *,
    n_bootstrap: int = 1000,
) -> ExperimentResult:
    """Score all models on the reserved test holdout; return the table + intervals."""
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    k = settings.top_k

    test = _test_customers(runner, settings, default_dataset)
    logger.info("scoring %s held-out test customers", len(test))
    matrix = build_matrix(settings, test, max_negatives=_NO_CAP, client=runner.client)
    truth = _ground_truth(runner, settings, default_dataset, test)
    customers = sorted(truth)

    # Cold-start fallback: customers with holdout purchases but no pre-cutoff history
    # are absent from the (warm-only) matrix, so no model can score them. They still
    # have candidates, so they are served a popularity ranking rather than nothing.
    warm_ids = set(matrix["customer_id"].unique())
    cold = sorted(c for c in truth if c not in warm_ids)
    cold_recs = popularity_fallback_recs(settings, cold, k, client=runner.client)
    logger.info("cold-start fallback for %s customers absent from the matrix", len(cold))

    rows: list[dict[str, float | str]] = []
    ap_by_model: dict[str, NDArray[np.float64]] = {}
    for name, model in _build_models(settings).items():
        recs = _recommendations(model, matrix, k)
        recs.update(cold_recs)  # cold customers get the fallback regardless of model
        ap_by_model[name] = np.array(
            [average_precision_at_k(recs.get(c, []), truth[c], k) for c in customers],
            dtype=np.float64,
        )
        rows.append(
            {
                "model": name,
                f"MAP@{k}": mean_average_precision_at_k(recs, truth, k),
                f"Recall@{k}": mean_recall_at_k(recs, truth, k),
                f"NDCG@{k}": mean_ndcg_at_k(recs, truth, k),
            }
        )
        logger.info("scored %s", name)

    table = pd.DataFrame(rows)
    map_ci = {
        name: bootstrap_metric_ci(ap, n_bootstrap=n_bootstrap, seed=settings.random_seed)
        for name, ap in ap_by_model.items()
    }
    lift = bootstrap_lift_ci(
        ap_by_model["ranker"],
        ap_by_model["popularity"],
        n_bootstrap=n_bootstrap,
        seed=settings.random_seed,
    )
    return ExperimentResult(table, map_ci, lift, k, len(customers))


def comparison_chart(result: ExperimentResult, path: Path) -> None:
    """Write a MAP@k bar chart with 95% bootstrap CI error bars."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(result.map_ci)
    means = [result.map_ci[n][0] for n in names]
    lower = [result.map_ci[n][0] - result.map_ci[n][1] for n in names]
    upper = [result.map_ci[n][2] - result.map_ci[n][0] for n in names]

    highs = [result.map_ci[n][2] for n in names]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(names, means, yerr=[lower, upper], capsize=6, color=["#9aa0a6", "#9aa0a6", "#1a73e8"])
    ax.set_ylabel(f"MAP@{result.k}")
    ax.set_title(f"Model comparison on the holdout week (MAP@{result.k}, 95% bootstrap CI)")
    ax.set_ylim(top=max(highs) * 1.18)
    for i, high in enumerate(highs):
        ax.text(i, high, f"{means[i]:.4f}", ha="center", va="bottom")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    logger.info("wrote chart to %s", path)
