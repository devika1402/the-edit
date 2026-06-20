"""Known-answer tests for the ranking metrics (computed by hand)."""

from __future__ import annotations

import pytest

from eval.metrics import (
    average_precision_at_k,
    mean_average_precision_at_k,
    mean_ndcg_at_k,
    mean_recall_at_k,
    ndcg_at_k,
    recall_at_k,
)

# recommended a,b,c,d ; relevant b,d  -> hits at ranks 2 and 4
RECS = ["a", "b", "c", "d"]
REL = ["b", "d"]


def test_recall_at_k() -> None:
    assert recall_at_k(RECS, REL, k=4) == 1.0  # both relevant in top 4
    assert recall_at_k(RECS, REL, k=2) == 0.5  # only b in top 2
    assert recall_at_k(["x", "y"], REL, k=2) == 0.0


def test_average_precision_at_k() -> None:
    # AP@4 = (P@2 + P@4) / min(2,4) = (1/2 + 2/4) / 2 = 0.5
    assert average_precision_at_k(RECS, REL, k=4) == pytest.approx(0.5)
    # perfect ordering -> AP = 1.0
    assert average_precision_at_k(["b", "d", "a", "c"], REL, k=4) == pytest.approx(1.0)
    assert average_precision_at_k(["x", "y"], REL, k=2) == 0.0


def test_ndcg_at_k() -> None:
    # DCG = 1/log2(3) + 1/log2(5) ; IDCG = 1/log2(2) + 1/log2(3)
    assert ndcg_at_k(RECS, REL, k=4) == pytest.approx(0.65091, abs=1e-4)
    assert ndcg_at_k(["b", "d", "a", "c"], REL, k=4) == pytest.approx(1.0)
    assert ndcg_at_k(["x", "y"], REL, k=2) == 0.0


def test_empty_relevant_is_zero() -> None:
    assert recall_at_k(["a"], [], k=12) == 0.0
    assert average_precision_at_k(["a"], [], k=12) == 0.0
    assert ndcg_at_k(["a"], [], k=12) == 0.0


def test_means_over_customers() -> None:
    recs = {"c1": ["a", "b", "c", "d"], "c2": ["b", "d", "a", "c"]}
    rel = {"c1": ["b", "d"], "c2": ["b", "d"]}
    assert mean_average_precision_at_k(recs, rel, k=4) == pytest.approx(0.75)  # (0.5 + 1.0)/2
    assert mean_recall_at_k(recs, rel, k=4) == pytest.approx(1.0)
    assert mean_ndcg_at_k(recs, rel, k=4) == pytest.approx((0.65091 + 1.0) / 2, abs=1e-4)


def test_mean_skips_customers_with_no_relevant() -> None:
    recs = {"c1": ["b"], "c2": ["a"]}
    rel = {"c1": ["b"], "c2": []}  # c2 has nothing bought -> excluded
    assert mean_recall_at_k(recs, rel, k=12) == pytest.approx(1.0)  # only c1 counts
