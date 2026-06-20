"""CatBoost learning-to-rank ranker (Phase 4; replaces LightGBM, D-7 reopened).

Concept — learning to rank, and why grouped by customer. A pointwise model scores
each item independently; a learning-to-rank model optimises the *order* of a list,
which is what a recommendation slot actually cares about. CatBoost's YetiRank is a
listwise objective that perturbs predicted rankings and optimises a smoothed
ranking metric. Training data is grouped by customer (``group_id = customer_id``)
because the model learns to order articles *within* one customer's candidate list,
not across customers. CatBoost handles the high-cardinality categoricals (colour,
department, garment group, category, age band) natively via ordered target
statistics with ordered boosting, so there is no manual one-hot / target encoding
to leak the label.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
from catboost import CatBoostRanker, Pool

from core.config import Settings
from core.exceptions import ModelTrainingError
from models.interface import top_k_from_scores
from models.matrix import CATEGORICAL_FEATURES, FEATURES
from models.sampling import split_customers

logger = logging.getLogger(__name__)

_MODEL_FILE = "ranker.cbm"
_FEATURES_FILE = "feature_list.json"


def write_feature_list(features: list[str], artifacts_dir: Path) -> None:
    """Persist the exact feature order and which features are categorical."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    payload = {"features": features, "categorical": CATEGORICAL_FEATURES}
    (artifacts_dir / _FEATURES_FILE).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_feature_list(artifacts_dir: Path) -> list[str]:
    """Read back the saved feature order."""
    payload = json.loads((artifacts_dir / _FEATURES_FILE).read_text(encoding="utf-8"))
    return list(payload["features"])


def _sorted(matrix: pd.DataFrame) -> pd.DataFrame:
    """Sort rows so each customer's group is contiguous (CatBoost needs this)."""
    return matrix.sort_values("customer_id", kind="stable").reset_index(drop=True)


def _pool(ordered: pd.DataFrame) -> Pool:
    """Build a CatBoost Pool from an already-sorted frame, grouped by customer."""
    label = ordered["label"] if "label" in ordered.columns else None
    return Pool(
        data=ordered[FEATURES],
        label=label,
        group_id=ordered["customer_id"],
        cat_features=CATEGORICAL_FEATURES,
    )


def train_ranker(matrix: pd.DataFrame, settings: Settings) -> tuple[CatBoostRanker, list[str]]:
    """Train a CatBoostRanker (YetiRank) grouped by customer; return (model, features).

    With enough customers, a 10% slice is held out for early stopping on NDCG@12, so
    the model picks its own tree count up to ``ranker_iterations`` rather than using a
    fixed guess. On tiny inputs (unit tests) it falls back to a plain fit.
    """
    customers = matrix["customer_id"].unique().tolist()
    use_eval = len(customers) >= 50
    if use_eval:
        fit_ids, eval_ids = split_customers(customers, 0.1, settings.random_seed)
        train_pool = _pool(_sorted(matrix[matrix["customer_id"].isin(set(fit_ids))]))
        eval_pool = _pool(_sorted(matrix[matrix["customer_id"].isin(set(eval_ids))]))
    else:
        train_pool = _pool(_sorted(matrix))
        eval_pool = None

    params: dict[str, object] = {
        "loss_function": "YetiRank",
        "iterations": settings.ranker_iterations,
        "learning_rate": settings.ranker_learning_rate,
        "depth": settings.ranker_depth,
        "random_seed": settings.random_seed,
        "verbose": False,
    }
    if use_eval:
        params["eval_metric"] = "NDCG:top=12"
        params["early_stopping_rounds"] = 50

    try:
        model = CatBoostRanker(**params)
        model.fit(train_pool, eval_set=eval_pool)
    except Exception as exc:
        raise ModelTrainingError(f"CatBoost training failed: {exc}") from exc
    return model, FEATURES


def save_ranker(model: CatBoostRanker, features: list[str], artifacts_dir: Path) -> Path:
    """Save the model and feature list; return the model path."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / _MODEL_FILE
    model.save_model(str(model_path))
    write_feature_list(features, artifacts_dir)
    return model_path


def load_ranker(artifacts_dir: Path) -> tuple[CatBoostRanker, list[str]]:
    """Load the saved model and feature list."""
    model = CatBoostRanker()
    model.load_model(str(artifacts_dir / _MODEL_FILE))
    return model, read_feature_list(artifacts_dir)


class CatBoostRecommender:
    """Score candidates with the trained ranker and return top-K per customer."""

    def __init__(self, model: CatBoostRanker, features: list[str]) -> None:
        self._model = model
        self._features = features

    def recommend(self, matrix: pd.DataFrame, k: int) -> pd.DataFrame:
        ordered = _sorted(matrix)  # predict + assign on the SAME ordered frame (aligned)
        ordered["score"] = self._model.predict(_pool(ordered))
        return top_k_from_scores(ordered, k)
