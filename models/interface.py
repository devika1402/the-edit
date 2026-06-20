"""The shared recommender interface and the top-K selector (Phase 4).

All three approaches (popularity, item-item CF, CatBoost) return recommendations
in the same tidy shape, so Phase 5 scores them identically.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

RECOMMENDATION_COLUMNS = ["customer_id", "article_id", "rank"]


def top_k_from_scores(scored: pd.DataFrame, k: int, *, score_col: str = "score") -> pd.DataFrame:
    """Return the top-``k`` articles per customer as ``(customer_id, article_id, rank)``.

    Ties are broken by ``article_id`` ascending so the output is deterministic.
    """
    ordered = scored.sort_values(
        ["customer_id", score_col, "article_id"], ascending=[True, False, True]
    )
    ordered = ordered.groupby("customer_id", sort=False).head(k).copy()
    ordered["rank"] = ordered.groupby("customer_id", sort=False).cumcount() + 1
    return ordered[RECOMMENDATION_COLUMNS].reset_index(drop=True)


class Recommender(Protocol):
    """Anything that turns the candidate-feature matrix into top-K per customer."""

    def recommend(self, matrix: pd.DataFrame, k: int) -> pd.DataFrame: ...
