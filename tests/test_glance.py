from __future__ import annotations

import pandas as pd

from models.train import hit_rate_at_k


def test_hit_rate_at_k_counts_customers_with_a_hit() -> None:
    recs = pd.DataFrame(
        {
            "customer_id": ["a", "a", "b", "b"],
            "article_id": ["x", "y", "p", "q"],
            "rank": [1, 2, 1, 2],
        }
    )
    truth = pd.DataFrame({"customer_id": ["a", "b"], "article_id": ["y", "z"]})
    # a: y is in recs -> hit; b: z not in recs -> miss => 0.5
    assert hit_rate_at_k(recs, truth, k=2) == 0.5


def test_hit_rate_at_k_respects_k() -> None:
    recs = pd.DataFrame({"customer_id": ["a", "a"], "article_id": ["x", "y"], "rank": [1, 2]})
    truth = pd.DataFrame({"customer_id": ["a"], "article_id": ["y"]})
    assert hit_rate_at_k(recs, truth, k=1) == 0.0  # y is at rank 2, outside top-1
    assert hit_rate_at_k(recs, truth, k=2) == 1.0
