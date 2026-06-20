"""Diversity and popularity-cap re-ranker (Phase 6).

Concept — a guardrail re-ranker. A learned ranker optimises hit rate, so its top-K
can be repetitive (many items from one category) and bestseller-heavy. This layer
re-orders a model's ranked pool to enforce two rules: cap how many items may share a
category (``max_per_category``) and cap how many bestsellers a list may contain
(``popularity_cap`` as a share of the list). It is a greedy pass that keeps the
model's order wherever the caps allow, so it sacrifices as little ranking quality as
possible to buy diversity. The cap is the guardrail's *strength*: sweeping it traces
the accuracy-versus-diversity trade-off, turning "diversity is good" into a measured
cost in MAP@12 rather than an assertion.

The greedy core is a pure function (``rerank_one``) so it is unit-tested directly.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import pandas as pd

from models.interface import RECOMMENDATION_COLUMNS


def rerank_one(
    ids: Sequence[str],
    category_of: Mapping[str, str],
    is_bestseller_of: Mapping[str, bool],
    *,
    k: int,
    max_per_category: int,
    max_bestsellers: int,
) -> list[str]:
    """Greedily re-order one customer's ranked pool under the diversity caps.

    Walks ``ids`` in model-rank order and accepts each item unless it would exceed
    ``max_per_category`` for its category or ``max_bestsellers`` bestsellers in the
    list; rejected items are deferred. If the caps are too tight to fill ``k`` slots,
    the deferred items are appended in their original order so the list is never
    shorter than an unconstrained top-K would be. Returns up to ``k`` article ids.
    """
    selected: list[str] = []
    deferred: list[str] = []
    per_category: dict[str, int] = {}
    bestsellers = 0

    for item in ids:
        if len(selected) >= k:
            break
        category = category_of.get(item, "__missing__")
        is_best = is_bestseller_of.get(item, False)
        if per_category.get(category, 0) >= max_per_category:
            deferred.append(item)
            continue
        if is_best and bestsellers >= max_bestsellers:
            deferred.append(item)
            continue
        selected.append(item)
        per_category[category] = per_category.get(category, 0) + 1
        if is_best:
            bestsellers += 1

    # Relax: if the caps left the list short, refill from the deferred items in order.
    for item in deferred:
        if len(selected) >= k:
            break
        selected.append(item)
    return selected


def rerank(
    ranked: pd.DataFrame,
    item_features: pd.DataFrame,
    *,
    k: int = 12,
    max_per_category: int = 3,
    popularity_cap: float = 0.5,
    category_col: str = "product_group_name",
    bestseller_col: str = "is_bestseller",
) -> pd.DataFrame:
    """Re-order each customer's ranked pool to enforce diversity and cap bestsellers.

    Args:
        ranked: a model's ranked candidates per customer
            (``customer_id, article_id, rank``); should hold more than ``k`` rows per
            customer so the re-ranker has room to substitute.
        item_features: per-item attributes indexed by ``article_id``, with a category
            column and a boolean bestseller column.
        k: final list length.
        max_per_category: maximum items from any one category in the final list.
        popularity_cap: maximum share of the list that may be bestsellers; the
            bestseller count cap is ``floor(popularity_cap * k)``.
        category_col: column in ``item_features`` holding each item's category.
        bestseller_col: boolean column in ``item_features`` flagging bestsellers.

    Returns:
        The re-ranked top-K per customer as ``customer_id, article_id, rank``.
    """
    category_of: dict[str, str] = item_features[category_col].astype(str).to_dict()
    is_bestseller_of: dict[str, bool] = item_features[bestseller_col].astype(bool).to_dict()
    max_bestsellers = math.floor(popularity_cap * k)

    out_rows: list[dict[str, object]] = []
    ordered = ranked.sort_values(["customer_id", "rank"])
    for customer, group in ordered.groupby("customer_id", sort=False):
        ids = group["article_id"].tolist()
        chosen = rerank_one(
            ids,
            category_of,
            is_bestseller_of,
            k=k,
            max_per_category=max_per_category,
            max_bestsellers=max_bestsellers,
        )
        for rank, article_id in enumerate(chosen, start=1):
            out_rows.append({"customer_id": customer, "article_id": article_id, "rank": rank})
    return pd.DataFrame(out_rows, columns=RECOMMENDATION_COLUMNS)
