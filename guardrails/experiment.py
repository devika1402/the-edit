"""Guardrails harness: beyond-accuracy, segment parity, and the trade-off curve (Phase 6).

This reuses the exact Phase-5 plumbing so the guardrail numbers are measured on the
same footing as the headline MAP@12: the 13,797 reserved test customers, the full
candidate matrix (``max_negatives = 10**9``), and their holdout-week purchases as
ground truth. From that one matrix it derives everything Phase 6 needs — the
recommendable item universe and its attributes, an all-time popularity map for
novelty, the bestseller (popularity head) set, and each customer's age band — so no
new BigQuery query is run beyond the eval pull.

Three deliverables come out:

1. **Beyond-accuracy per model** — coverage, intra-list diversity, novelty, Gini,
   and long-tail share alongside MAP@12, for popularity / item-item CF / ranker.
2. **Segment parity** — MAP@12 broken out per customer age band (OD-2) per model.
3. **The trade-off curve** — the ranker's top-100 pool re-ranked down to 12 as the
   category-diversity cap tightens (12 -> 1), so the cost of diversity is a measured
   MAP@12 number, not an assertion. (Decision: the curve sweeps the *category* cap;
   the bestseller cap stays in the reranker and is reported via Gini / long-tail
   share, per the agreed Phase-6 scope.)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

from core.bq import BigQueryClient
from core.config import Settings
from eval.experiment import _build_models, _ground_truth, _test_customers
from eval.metrics import mean_average_precision_at_k
from guardrails.beyond_accuracy import (
    coverage,
    gini,
    long_tail_share,
    mean_intra_list_diversity,
    mean_novelty,
    segment_parity,
)
from guardrails.reranker import rerank
from models.fallback import popularity_fallback_recs
from models.matrix import build_matrix

logger = logging.getLogger(__name__)

_NO_CAP = 10**9

# Item attributes used for intra-list diversity (normalised Hamming over these).
ATTR_COLS = [
    "product_group_name",
    "department_name",
    "colour_group_name",
    "garment_group_name",
    "price_tier",
]
# Category-diversity caps swept for the trade-off curve, weakest (12) to strongest (1).
CATEGORY_CAPS = (12, 8, 6, 4, 3, 2, 1)


@dataclass
class GuardrailsResult:
    """The Phase 6 deliverables."""

    beyond_accuracy: pd.DataFrame  # one row per model
    parity: dict[str, pd.DataFrame]  # model -> per-age-band MAP@k table (OD-2)
    parity_cohort: dict[str, pd.DataFrame]  # model -> warm/cold MAP@k table
    tradeoff: pd.DataFrame  # one row per category cap (the curve)
    k: int
    n_customers: int
    catalogue_size: int


def _frame_to_dict(frame: pd.DataFrame) -> dict[str, list[str]]:
    """Top-K article ids per customer, in rank order, from a recommendation frame."""
    ordered = frame.sort_values(["customer_id", "rank"])
    return {
        str(customer): group["article_id"].tolist()
        for customer, group in ordered.groupby("customer_id", sort=False)
    }


def _item_features(matrix: pd.DataFrame, bestseller_quantile: float) -> pd.DataFrame:
    """Per-item attributes for the recommendable universe, indexed by article_id.

    Carries the diversity attributes, an all-time popularity (``n_purchases``) for
    novelty, and an ``is_bestseller`` flag: items whose recent popularity sits in the
    top ``1 - bestseller_quantile`` of the universe (the popularity head).
    """
    items = matrix.drop_duplicates("article_id").set_index("article_id")
    feats = items[[*ATTR_COLS, "popularity_recent", "n_purchases"]].copy()
    threshold = float(feats["popularity_recent"].quantile(bestseller_quantile))
    feats["is_bestseller"] = (feats["popularity_recent"] >= threshold) & (
        feats["popularity_recent"] > 0
    )
    return feats


def _age_band_of(
    runner: BigQueryClient, default_dataset: str, customers: list[str]
) -> dict[str, str]:
    """True age band per customer from stg_customers (covers cold customers too).

    The matrix only holds warm customers, so segmenting on it dumped every cold
    customer into 'unknown' — the bug that made the 'unknown' age band look broken.
    Reading the band straight from stg_customers gives each customer their real band.
    """
    params: list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter] = [
        bigquery.ArrayQueryParameter("customers", "STRING", customers),
    ]
    rows = runner.query(
        "SELECT customer_id, COALESCE(age_band, 'unknown') AS age_band "
        "FROM stg_customers WHERE customer_id IN UNNEST(@customers)",
        query_parameters=params,
        default_dataset=default_dataset,
    )
    return {row["customer_id"]: row["age_band"] for row in rows}


def run_guardrails(
    settings: Settings,
    client: bigquery.Client | None = None,
    *,
    pool_size: int = 100,
    bestseller_quantile: float = 0.9,
    category_caps: tuple[int, ...] = CATEGORY_CAPS,
) -> GuardrailsResult:
    """Compute beyond-accuracy metrics, segment parity, and the trade-off curve."""
    runner = BigQueryClient(settings, client=client)
    default_dataset = f"{settings.gcp_project}.{settings.bq_dataset}"
    k = settings.top_k

    test = _test_customers(runner, settings, default_dataset)
    logger.info("scoring %s held-out test customers", len(test))
    matrix = build_matrix(settings, test, max_negatives=_NO_CAP, client=runner.client)
    truth = _ground_truth(runner, settings, default_dataset, test)
    customers = sorted(truth)

    item_features = _item_features(matrix, bestseller_quantile)
    attr_features = item_features[ATTR_COLS]
    popularity: dict[str, float] = item_features["n_purchases"].astype(float).to_dict()
    head_items = set(item_features.index[item_features["is_bestseller"]])
    catalogue_size = len(item_features)

    # Segment by TRUE age band (from stg_customers, covering cold customers) and add a
    # warm/cold cut. Cold customers (absent from the matrix) get the popularity fallback
    # rather than nothing, so every model's recs cover them.
    age_band_of = _age_band_of(runner, default_dataset, customers)
    warm_ids = set(matrix["customer_id"].unique())
    cohort_of = {c: ("warm" if c in warm_ids else "cold") for c in customers}
    cold = sorted(c for c in customers if c not in warm_ids)
    cold_recs = popularity_fallback_recs(settings, cold, k, client=runner.client)
    logger.info(
        "recommendable universe: %s items, %s bestsellers (top %.0f%%); "
        "cold-start fallback for %s of %s customers",
        catalogue_size,
        len(head_items),
        (1 - bestseller_quantile) * 100,
        len(cold),
        len(customers),
    )

    models = _build_models(settings)
    # Score the ranker once into a top-`pool_size` pool; reuse it for both its top-K
    # metrics and the trade-off sweep (avoids a second CatBoost predict over the matrix).
    ranker_pool = models["ranker"].recommend(matrix, pool_size)

    beyond_rows: list[dict[str, object]] = []
    parity: dict[str, pd.DataFrame] = {}
    parity_cohort: dict[str, pd.DataFrame] = {}
    for name, model in models.items():
        if name == "ranker":
            recs = _frame_to_dict(ranker_pool[ranker_pool["rank"] <= k])
        else:
            recs = _frame_to_dict(model.recommend(matrix, k))
        recs.update(cold_recs)  # cold customers get the fallback regardless of model
        beyond_rows.append(
            {
                "model": name,
                f"MAP@{k}": mean_average_precision_at_k(recs, truth, k),
                "coverage": coverage(recs, catalogue_size),
                "intra_list_diversity": mean_intra_list_diversity(recs, attr_features),
                "novelty": mean_novelty(recs, popularity),
                "gini": gini(recs),
                "long_tail_share": long_tail_share(recs, head_items),
            }
        )
        parity[name] = segment_parity(recs, truth, age_band_of, k=k)
        parity_cohort[name] = segment_parity(recs, truth, cohort_of, k=k)
        logger.info("scored %s", name)

    tradeoff_rows: list[dict[str, object]] = []
    for cap in category_caps:
        reranked = rerank(ranker_pool, item_features, k=k, max_per_category=cap, popularity_cap=1.0)
        recs = _frame_to_dict(reranked)
        recs.update(cold_recs)  # keep MAP comparable to the per-model table
        tradeoff_rows.append(
            {
                "max_per_category": cap,
                f"MAP@{k}": mean_average_precision_at_k(recs, truth, k),
                "intra_list_diversity": mean_intra_list_diversity(recs, attr_features),
                "coverage": coverage(recs, catalogue_size),
                "gini": gini(recs),
                "long_tail_share": long_tail_share(recs, head_items),
            }
        )
        logger.info("swept category cap = %s", cap)

    return GuardrailsResult(
        beyond_accuracy=pd.DataFrame(beyond_rows),
        parity=parity,
        parity_cohort=parity_cohort,
        tradeoff=pd.DataFrame(tradeoff_rows),
        k=k,
        n_customers=len(truth),
        catalogue_size=catalogue_size,
    )


def tradeoff_chart(result: GuardrailsResult, path: Path) -> None:
    """Plot MAP@k against intra-list diversity as the category cap tightens."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curve = result.tradeoff
    x = curve["intra_list_diversity"].tolist()
    y = curve[f"MAP@{result.k}"].tolist()
    caps = curve["max_per_category"].tolist()

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(x, y, marker="o", color="#1a73e8")
    for xi, yi, cap in zip(x, y, caps, strict=True):
        ax.annotate(f"cap={cap}", (xi, yi), textcoords="offset points", xytext=(6, 6), fontsize=8)
    ax.set_xlabel("Intra-list diversity (higher = more varied lists)")
    ax.set_ylabel(f"MAP@{result.k} (accuracy)")
    ax.set_title(f"Accuracy vs diversity as the category cap tightens (ranker, top-{result.k})")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)
    logger.info("wrote chart to %s", path)
