"""Beyond-accuracy metrics (Phase 6).

Concept — beyond-accuracy metrics. A recommender can be accurate and still bad:
repetitive, biased toward bestsellers, or worse for some customer groups. Hit-rate
metrics (MAP@12) reward predicting what a customer buys; they say nothing about
whether the *list* is a good experience. These metrics measure that other half:

- **coverage** — the share of the catalogue that is ever recommended at all. A
  system that only ever shows the same 200 hits has tiny coverage and buries the
  long tail.
- **intra-list diversity** — how different the items *within one list* are. Ten
  near-identical black dresses score badly here even if they convert.
- **novelty** — rewards surfacing less popular items. A list of obvious bestsellers
  is low-novelty; one that introduces the customer to something new is high.
- **popularity bias** — how concentrated recommendations are on a few hits. We
  report it two ways the PRD asks for: the **long-tail share** (fraction of the
  recommendation slots spent on non-bestseller items) and the **Gini coefficient**.

Concept — the Gini coefficient. Borrowed from economics, where it measures income
inequality, here it measures how unequally recommendation *exposure* is spread
across the items that get recommended. Near zero means every recommended item is
shown about equally often; near one means a handful of items soak up almost all the
exposure. It is the standard one-number summary of popularity bias.

Concept — segment parity. A strong global MAP@12 can hide a customer group the
system serves poorly. Segment parity breaks the primary metric out per customer
age band (OD-2), so an aggregate win cannot mask an unequal one.

All functions are pure and unit-tested on small fixtures with hand-computed answers.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence

import pandas as pd

from eval.metrics import mean_average_precision_at_k


def coverage(recommended_per_customer: Mapping[str, Sequence[str]], catalogue_size: int) -> float:
    """Share of the catalogue that appears in at least one recommendation list.

    ``catalogue_size`` is the count of recommendable items (the universe an item
    could have been drawn from). Returns a value in [0, 1].
    """
    if catalogue_size <= 0:
        return 0.0
    seen: set[str] = set()
    for items in recommended_per_customer.values():
        seen.update(items)
    return len(seen) / catalogue_size


def intra_list_diversity(recommended: Sequence[str], item_features: pd.DataFrame) -> float:
    """Mean pairwise dissimilarity of the items within a single list.

    ``item_features`` is indexed by ``article_id``; every column is treated as a
    categorical attribute. The dissimilarity of two items is the fraction of those
    attribute columns on which they differ (a normalised Hamming distance), and the
    list's diversity is the mean dissimilarity over all unordered item pairs. Lists
    with fewer than two items have no pairs and score 0.0.
    """
    items = [a for a in recommended if a in item_features.index]
    if len(items) < 2:
        return 0.0
    attrs = item_features.loc[items].to_numpy()
    n_attrs = attrs.shape[1]
    if n_attrs == 0:
        return 0.0
    total = 0.0
    pairs = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            differing = int((attrs[i] != attrs[j]).sum())
            total += differing / n_attrs
            pairs += 1
    return total / pairs


def mean_intra_list_diversity(
    recommended_per_customer: Mapping[str, Sequence[str]], item_features: pd.DataFrame
) -> float:
    """Mean intra-list diversity over all customers (empty lists are skipped)."""
    lists = [items for items in recommended_per_customer.values() if items]
    if not lists:
        return 0.0
    return sum(intra_list_diversity(items, item_features) for items in lists) / len(lists)


def novelty(recommended: Sequence[str], popularity: Mapping[str, float]) -> float:
    """Mean self-information novelty of a list (higher = less popular items).

    Each item's novelty is ``-log2(p)`` where ``p`` is its share of total
    popularity, so a rare item carries more bits (more "surprise") than a
    bestseller. ``popularity`` should be strictly-positive counts (e.g. all-time
    purchases); items missing or with non-positive popularity are skipped, and an
    empty result is 0.0.
    """
    total = float(sum(v for v in popularity.values() if v > 0))
    if total <= 0:
        return 0.0
    bits = []
    for item in recommended:
        count = popularity.get(item, 0.0)
        if count > 0:
            bits.append(-math.log2(count / total))
    return sum(bits) / len(bits) if bits else 0.0


def mean_novelty(
    recommended_per_customer: Mapping[str, Sequence[str]], popularity: Mapping[str, float]
) -> float:
    """Mean novelty over all customers (empty lists are skipped)."""
    lists = [items for items in recommended_per_customer.values() if items]
    if not lists:
        return 0.0
    return sum(novelty(items, popularity) for items in lists) / len(lists)


def gini(recommended_per_customer: Mapping[str, Sequence[str]]) -> float:
    """Gini coefficient of recommendation exposure across the recommended items.

    Exposure is how many lists each item appears in. With counts sorted ascending
    ``x_1..x_n``, the Gini is ``sum((2i - n - 1) * x_i) / (n * sum(x_i))``: 0 when
    every recommended item gets equal exposure, approaching 1 when a few items take
    almost all of it.
    """
    exposure: dict[str, int] = {}
    for items in recommended_per_customer.values():
        for item in items:
            exposure[item] = exposure.get(item, 0) + 1
    counts = sorted(exposure.values())
    n = len(counts)
    total = sum(counts)
    if n == 0 or total == 0:
        return 0.0
    weighted = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(counts))
    return weighted / (n * total)


def long_tail_share(
    recommended_per_customer: Mapping[str, Sequence[str]], head_items: Collection[str]
) -> float:
    """Fraction of recommendation slots spent on long-tail (non-head) items.

    ``head_items`` is the set of bestsellers (the popularity "head"). Every slot in
    every list is one impression; this returns the share of impressions that landed
    on items *outside* that head set, so a higher value means less popularity bias.
    """
    head = set(head_items)
    impressions = 0
    tail = 0
    for items in recommended_per_customer.values():
        for item in items:
            impressions += 1
            if item not in head:
                tail += 1
    return tail / impressions if impressions else 0.0


def segment_parity(
    recommended_per_customer: Mapping[str, Sequence[str]],
    relevant_per_customer: Mapping[str, Sequence[str]],
    segment_of_customer: Mapping[str, str],
    *,
    k: int = 12,
) -> pd.DataFrame:
    """Report MAP@K per customer segment (the OD-2 age band).

    Returns one row per segment with ``n_customers`` (answerable customers in the
    segment, i.e. those with at least one relevant item — the MAP denominator) and
    ``MAP@{k}``, sorted by segment so a global average cannot hide an unequal one.
    """
    by_segment: dict[str, list[str]] = {}
    for customer, relevant in relevant_per_customer.items():
        if not relevant:
            continue
        segment = segment_of_customer.get(customer, "unknown")
        by_segment.setdefault(segment, []).append(customer)

    rows: list[dict[str, object]] = []
    for segment in sorted(by_segment):
        customers = by_segment[segment]
        recs = {c: recommended_per_customer.get(c, []) for c in customers}
        rel = {c: relevant_per_customer[c] for c in customers}
        rows.append(
            {
                "segment": segment,
                "n_customers": len(customers),
                f"MAP@{k}": mean_average_precision_at_k(recs, rel, k),
            }
        )
    return pd.DataFrame(rows, columns=["segment", "n_customers", f"MAP@{k}"])
