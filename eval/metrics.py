"""Ranking metrics: MAP@K, Recall@K, NDCG@K (Phase 5).

Concept — ranking metrics, and why accuracy is the wrong lens. Accuracy asks
"did we label each item right"; a recommender instead fills a few slots and only
cares whether the right items land near the top of a short list. So we measure
that directly:

- **Recall@K** — of the items a customer actually bought, what fraction made it
  into the top K. A coverage measure; it ignores order within the top K.
- **MAP@K** (mean average precision) — rewards putting relevant items *high* in
  the top K, averaged over customers. This is the metric the H&M competition used,
  so it is the primary here. Per customer, AP@K averages the precision measured at
  each rank where a relevant item appears, normalised by ``min(#relevant, K)``.
- **NDCG@K** — discounts a relevant item by its position (``1/log2(rank+1)``) and
  normalises by the best achievable ordering, so a hit at rank 1 is worth more
  than a hit at rank 12.

All functions take a customer's ranked ``recommended`` list (distinct article ids,
best first) and the set of ``relevant`` (actually-bought) ids, and return a value
in [0, 1]. They are pure, so they are unit-tested on fixtures with known answers.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence


def recall_at_k(recommended: Sequence[str], relevant: Sequence[str], k: int = 12) -> float:
    """Fraction of relevant items that appear in the top ``k`` recommendations."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    hits = sum(1 for item in recommended[:k] if item in relevant_set)
    return hits / len(relevant_set)


def average_precision_at_k(
    recommended: Sequence[str], relevant: Sequence[str], k: int = 12
) -> float:
    """Average precision at ``k`` for one customer (the H&M MAP@K per-user term)."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    hits = 0
    score = 0.0
    for rank, item in enumerate(recommended[:k], start=1):
        if item in relevant_set:
            hits += 1
            score += hits / rank
    return score / min(len(relevant_set), k)


def ndcg_at_k(recommended: Sequence[str], relevant: Sequence[str], k: int = 12) -> float:
    """Normalised discounted cumulative gain at ``k`` (binary relevance)."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(recommended[:k], start=1)
        if item in relevant_set
    )
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def _mean(
    metric: Callable[[Sequence[str], Sequence[str], int], float],
    recommended_per_customer: Mapping[str, Sequence[str]],
    relevant_per_customer: Mapping[str, Sequence[str]],
    k: int,
) -> float:
    """Mean of a per-customer metric over the customers that have relevant items."""
    customers = [c for c in relevant_per_customer if relevant_per_customer[c]]
    if not customers:
        return 0.0
    total = sum(
        metric(recommended_per_customer.get(c, []), relevant_per_customer[c], k) for c in customers
    )
    return total / len(customers)


def mean_average_precision_at_k(
    recommended_per_customer: Mapping[str, Sequence[str]],
    relevant_per_customer: Mapping[str, Sequence[str]],
    k: int = 12,
) -> float:
    """MAP@K: mean of per-customer average precision (the primary metric)."""
    return _mean(average_precision_at_k, recommended_per_customer, relevant_per_customer, k)


def mean_recall_at_k(
    recommended_per_customer: Mapping[str, Sequence[str]],
    relevant_per_customer: Mapping[str, Sequence[str]],
    k: int = 12,
) -> float:
    """Mean Recall@K over customers."""
    return _mean(recall_at_k, recommended_per_customer, relevant_per_customer, k)


def mean_ndcg_at_k(
    recommended_per_customer: Mapping[str, Sequence[str]],
    relevant_per_customer: Mapping[str, Sequence[str]],
    k: int = 12,
) -> float:
    """Mean NDCG@K over customers."""
    return _mean(ndcg_at_k, recommended_per_customer, relevant_per_customer, k)
