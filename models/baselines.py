"""Baseline rankers: recent popularity and item-item collaborative filtering.

These set the floor the learned ranker must beat (Phase 4). The popularity
baseline orders candidates by recent sales; the item-item CF baseline orders them
by the co-purchase co-occurrence score produced during retrieval. Both expose the
same top-K interface as the learned ranker, so Phase 5 treats all three identically.
"""

from __future__ import annotations

import pandas as pd

from models.interface import top_k_from_scores


class PopularityRecommender:
    """Rank each customer's candidates by recent item popularity."""

    def recommend(self, matrix: pd.DataFrame, k: int) -> pd.DataFrame:
        scored = matrix.rename(columns={"popularity_recent": "score"})
        return top_k_from_scores(scored, k)


class ItemItemCFRecommender:
    """Rank each customer's candidates by item-item co-occurrence score."""

    def recommend(self, matrix: pd.DataFrame, k: int) -> pd.DataFrame:
        scored = matrix.rename(columns={"copurchase_score": "score"})
        return top_k_from_scores(scored, k)
