"""Known-answer tests for the beyond-accuracy metrics (computed by hand)."""

from __future__ import annotations

import pandas as pd
import pytest

from guardrails.beyond_accuracy import (
    coverage,
    gini,
    intra_list_diversity,
    long_tail_share,
    mean_intra_list_diversity,
    mean_novelty,
    novelty,
    segment_parity,
)

# Two attribute columns; dissimilarity is the fraction of columns that differ.
ITEM_FEATURES = pd.DataFrame(
    {"category": ["X", "X", "Y"], "colour": ["R", "B", "B"]},
    index=pd.Index(["a", "b", "c"], name="article_id"),
)


def test_coverage() -> None:
    # distinct items {a, b, c} = 3 over a catalogue of 10
    recs = {"c1": ["a", "b"], "c2": ["b", "c"]}
    assert coverage(recs, catalogue_size=10) == pytest.approx(0.3)


def test_coverage_empty_is_zero() -> None:
    assert coverage({}, catalogue_size=10) == 0.0
    assert coverage({"c1": ["a"]}, catalogue_size=0) == 0.0


def test_intra_list_diversity() -> None:
    # pairs: (a,b)=0.5, (a,c)=1.0, (b,c)=0.5 -> mean 2/3
    assert intra_list_diversity(["a", "b", "c"], ITEM_FEATURES) == pytest.approx(2 / 3)
    # one pair only
    assert intra_list_diversity(["a", "b"], ITEM_FEATURES) == pytest.approx(0.5)


def test_intra_list_diversity_degenerate_lists_are_zero() -> None:
    assert intra_list_diversity(["a"], ITEM_FEATURES) == 0.0
    assert intra_list_diversity([], ITEM_FEATURES) == 0.0


def test_mean_intra_list_diversity() -> None:
    recs = {"c1": ["a", "b", "c"], "c2": ["a", "b"]}
    assert mean_intra_list_diversity(recs, ITEM_FEATURES) == pytest.approx((2 / 3 + 0.5) / 2)


def test_novelty() -> None:
    # p(a)=p(b)=0.25 -> 2 bits; p(c)=0.5 -> 1 bit
    popularity = {"a": 1.0, "b": 1.0, "c": 2.0}
    assert novelty(["a", "c"], popularity) == pytest.approx(1.5)
    # items missing from the popularity map are skipped
    assert novelty(["a", "z"], popularity) == pytest.approx(2.0)
    assert novelty(["z"], popularity) == 0.0


def test_mean_novelty() -> None:
    popularity = {"a": 1.0, "b": 1.0, "c": 2.0}
    recs = {"c1": ["a", "c"], "c2": ["c"]}
    assert mean_novelty(recs, popularity) == pytest.approx((1.5 + 1.0) / 2)


def test_gini() -> None:
    # exposure: a=3, b=1 -> Gini 0.25
    recs = {"c1": ["a", "b"], "c2": ["a"], "c3": ["a"]}
    assert gini(recs) == pytest.approx(0.25)


def test_gini_even_exposure_is_zero() -> None:
    assert gini({"c1": ["a"], "c2": ["b"]}) == pytest.approx(0.0)
    assert gini({}) == 0.0


def test_long_tail_share() -> None:
    # impressions [a, b, a, c]; head = {a} -> tail b, c -> 2/4
    recs = {"c1": ["a", "b"], "c2": ["a", "c"]}
    assert long_tail_share(recs, head_items={"a"}) == pytest.approx(0.5)


def test_long_tail_share_empty_is_zero() -> None:
    assert long_tail_share({}, head_items={"a"}) == 0.0


def test_segment_parity() -> None:
    recs = {"c1": ["b", "x"], "c2": ["a", "b"], "c3": ["b", "d"]}
    rel = {"c1": ["b"], "c2": ["b"], "c3": ["b", "d"]}
    seg = {"c1": "18-25", "c2": "18-25", "c3": "26-35"}
    out = segment_parity(recs, rel, seg, k=2)

    assert list(out["segment"]) == ["18-25", "26-35"]
    assert list(out["n_customers"]) == [2, 1]
    # 18-25: AP@2 = (1.0 + 0.5)/2 = 0.75 ; 26-35: AP@2 = 1.0
    assert out["MAP@2"].tolist() == pytest.approx([0.75, 1.0])
