from __future__ import annotations

import pandas as pd

from core.config import Settings
from models.matrix import CATEGORICAL_FEATURES, FEATURES
from models.ranker import CatBoostRecommender, train_ranker


def _fixture() -> pd.DataFrame:
    """Six customers, three candidates each; the high-popularity one is the positive."""
    rows: list[dict[str, object]] = []
    for c in [f"cust{j}" for j in range(6)]:
        for i, pop in enumerate([1, 10, 200]):
            row: dict[str, object] = dict.fromkeys(FEATURES, 0)
            for cat in CATEGORICAL_FEATURES:
                row[cat] = "x"
            row["popularity_recent"] = pop
            row["customer_id"] = c
            row["article_id"] = f"{c}_{i}"
            row["label"] = 1 if pop == 200 else 0
            rows.append(row)
    frame = pd.DataFrame(rows)
    for cat in CATEGORICAL_FEATURES:
        frame[cat] = frame[cat].astype(str)
    return frame


def test_ranker_predictions_align_to_rows() -> None:
    settings = Settings(gcp_project="t", ranker_iterations=100, ranker_depth=4)
    matrix = _fixture()
    model, features = train_ranker(matrix, settings)
    recs = CatBoostRecommender(model, features).recommend(matrix, k=1)
    # the positive (popularity_recent=200, article index 2) must be top-1 for every
    # customer; if predicted scores were assigned to the wrong rows, this fails.
    top1 = recs[recs["rank"] == 1].set_index("customer_id")["article_id"]
    for customer in matrix["customer_id"].unique():
        assert top1[customer] == f"{customer}_2"
