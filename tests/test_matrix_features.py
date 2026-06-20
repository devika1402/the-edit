from __future__ import annotations

from models.matrix import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES


def test_feature_lists_are_disjoint_and_combined() -> None:
    assert set(NUMERIC_FEATURES).isdisjoint(CATEGORICAL_FEATURES)
    assert FEATURES == NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert "customer_id" not in FEATURES and "label" not in FEATURES


def test_categoricals_are_the_known_categorical_columns() -> None:
    assert set(CATEGORICAL_FEATURES) == {
        "age_band",
        "dominant_category",
        "dominant_colour",
        "price_tier",
        "product_group_name",
        "department_name",
        "colour_group_name",
        "garment_group_name",
    }
