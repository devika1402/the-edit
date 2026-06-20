"""Tests for the pure logic in the cold-start fallback."""

from __future__ import annotations

import pandas as pd

from models.fallback import popularity_recommend


def test_popularity_recommend_ranks_by_recent_popularity() -> None:
    frame = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c1"],
            "article_id": ["a", "b", "c"],
            "popularity_recent": [5, 9, 1],
        }
    )
    out = popularity_recommend(frame, k=2)
    c1 = out[out["customer_id"] == "c1"].sort_values("rank")
    assert c1["article_id"].tolist() == ["b", "a"]  # 9 then 5
    assert c1["rank"].tolist() == [1, 2]


def test_popularity_recommend_is_per_customer() -> None:
    frame = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2"],
            "article_id": ["a", "b", "c"],
            "popularity_recent": [1, 2, 9],
        }
    )
    out = popularity_recommend(frame, k=1)
    assert out[out["customer_id"] == "c1"]["article_id"].tolist() == ["b"]
    assert out[out["customer_id"] == "c2"]["article_id"].tolist() == ["c"]
