from __future__ import annotations

import pandas as pd

from models.interface import RECOMMENDATION_COLUMNS, top_k_from_scores


def test_top_k_from_scores_orders_and_ranks_per_customer() -> None:
    scored = pd.DataFrame(
        {
            "customer_id": ["a", "a", "a", "b", "b"],
            "article_id": ["x", "y", "z", "p", "q"],
            "score": [0.1, 0.9, 0.5, 0.2, 0.8],
        }
    )
    out = top_k_from_scores(scored, k=2)
    assert list(out.columns) == RECOMMENDATION_COLUMNS
    a = out[out.customer_id == "a"]
    assert list(a.article_id) == ["y", "z"]
    assert list(a["rank"]) == [1, 2]
    assert set(out[out.customer_id == "b"].article_id) == {"q", "p"}
    assert len(out) == 4  # 2 per customer


def test_top_k_from_scores_breaks_ties_deterministically() -> None:
    scored = pd.DataFrame(
        {"customer_id": ["a", "a"], "article_id": ["x", "y"], "score": [0.5, 0.5]}
    )
    out = top_k_from_scores(scored, k=2)
    assert list(out.article_id) == ["x", "y"]  # stable: article_id ascending on ties
