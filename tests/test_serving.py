"""Tests for the pure response-shaping helpers in the serving app (no BigQuery)."""

from __future__ import annotations

import pandas as pd

from serving.app import RecommendationItem, rerank_item_features, to_items


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["c", "c", "c"],
            "article_id": ["a1", "a2", "a3"],
            "prod_name": ["Strap top", "Jersey dress", "Sneakers"],
            "product_type_name": ["Vest top", "Dress", "Sneakers"],
            "product_group_name": ["Garment Upper", "Garment Upper", "Shoes"],
            "colour_group_name": ["Black", "Blue", "White"],
            "price_tier": [1, 3, 5],
            "popularity_recent": [100, 50, 5],
            "is_top_global": [1, 0, 0],
        }
    )


def test_to_items_builds_ranked_pydantic_items() -> None:
    ranked = pd.DataFrame({"customer_id": ["c", "c"], "article_id": ["a2", "a1"], "rank": [1, 2]})
    items = to_items(ranked, _frame())
    assert all(isinstance(i, RecommendationItem) for i in items)
    assert [i.rank for i in items] == [1, 2]
    assert [i.article_id for i in items] == ["a2", "a1"]
    assert items[0].prod_name == "Jersey dress"
    assert items[0].product_type_name == "Dress"
    assert items[0].product_group_name == "Garment Upper"
    assert items[0].colour_group_name == "Blue"
    assert items[0].price_tier == 3
    assert items[0].popularity_recent == 50


def test_rerank_item_features_flags_global_bestsellers() -> None:
    feats = rerank_item_features(_frame())
    assert bool(feats.loc["a1", "is_bestseller"]) is True
    assert bool(feats.loc["a2", "is_bestseller"]) is False
    assert feats.loc["a1", "product_group_name"] == "Garment Upper"
