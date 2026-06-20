"""Tests for the diversity / bestseller re-ranker (pure logic)."""

from __future__ import annotations

import pandas as pd

from guardrails.reranker import rerank, rerank_one

_NO_CAP = 10**9


def test_rerank_one_caps_per_category_and_keeps_order() -> None:
    ids = ["i1", "i2", "i3", "i4", "i5"]
    category = {"i1": "A", "i2": "A", "i3": "A", "i4": "B", "i5": "C"}
    is_bestseller = dict.fromkeys(ids, False)
    out = rerank_one(ids, category, is_bestseller, k=3, max_per_category=2, max_bestsellers=_NO_CAP)
    # i3 is the 3rd "A" -> skipped; i4 fills the slot
    assert out == ["i1", "i2", "i4"]


def test_rerank_one_caps_bestsellers() -> None:
    ids = ["b1", "b2", "b3", "n1"]
    category = {"b1": "A", "b2": "B", "b3": "C", "n1": "D"}  # category not binding
    is_bestseller = {"b1": True, "b2": True, "b3": True, "n1": False}
    out = rerank_one(ids, category, is_bestseller, k=3, max_per_category=_NO_CAP, max_bestsellers=2)
    # only 2 bestsellers allowed -> b3 skipped, the non-bestseller n1 fills in
    assert out == ["b1", "b2", "n1"]


def test_rerank_one_relaxes_to_fill_k() -> None:
    ids = ["i1", "i2", "i3"]
    category = dict.fromkeys(ids, "A")  # all one category
    is_bestseller = dict.fromkeys(ids, False)
    out = rerank_one(ids, category, is_bestseller, k=3, max_per_category=1, max_bestsellers=_NO_CAP)
    # cap=1 would yield only [i1]; relaxation refills deferred items in order
    assert out == ["i1", "i2", "i3"]


def test_rerank_one_identity_when_no_constraint_binds() -> None:
    ids = ["i1", "i2", "i3", "i4"]
    category = {"i1": "A", "i2": "B", "i3": "C", "i4": "D"}
    is_bestseller = dict.fromkeys(ids, False)
    out = rerank_one(
        ids, category, is_bestseller, k=2, max_per_category=_NO_CAP, max_bestsellers=_NO_CAP
    )
    assert out == ["i1", "i2"]


def test_rerank_one_pool_smaller_than_k() -> None:
    ids = ["i1", "i2"]
    category = {"i1": "A", "i2": "A"}
    is_bestseller = dict.fromkeys(ids, False)
    out = rerank_one(ids, category, is_bestseller, k=5, max_per_category=1, max_bestsellers=_NO_CAP)
    assert out == ["i1", "i2"]


def test_rerank_frame_per_customer() -> None:
    item_features = pd.DataFrame(
        {
            "product_group_name": ["A", "A", "A", "B"],
            "is_bestseller": [False, False, False, False],
        },
        index=pd.Index(["a1", "a2", "a3", "a4"], name="article_id"),
    )
    ranked = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c1", "c1", "c2", "c2"],
            "article_id": ["a1", "a2", "a3", "a4", "a4", "a1"],
            "rank": [1, 2, 3, 4, 1, 2],
        }
    )
    out = rerank(ranked, item_features, k=3, max_per_category=2, popularity_cap=1.0)

    c1 = out[out["customer_id"] == "c1"].sort_values("rank")
    assert c1["article_id"].tolist() == ["a1", "a2", "a4"]
    assert c1["rank"].tolist() == [1, 2, 3]

    c2 = out[out["customer_id"] == "c2"].sort_values("rank")
    assert c2["article_id"].tolist() == ["a4", "a1"]
    assert c2["rank"].tolist() == [1, 2]
