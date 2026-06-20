from __future__ import annotations

import pandas as pd

from models.baselines import ItemItemCFRecommender, PopularityRecommender


def _matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["a", "a", "a"],
            "article_id": ["x", "y", "z"],
            "popularity_recent": [5, 50, 1],
            "copurchase_score": [9, 0, 3],
        }
    )


def test_popularity_ranks_by_recent_popularity() -> None:
    out = PopularityRecommender().recommend(_matrix(), k=2)
    assert list(out[out.customer_id == "a"].article_id) == ["y", "x"]


def test_item_item_cf_ranks_by_copurchase_score() -> None:
    out = ItemItemCFRecommender().recommend(_matrix(), k=2)
    assert list(out[out.customer_id == "a"].article_id) == ["x", "z"]
