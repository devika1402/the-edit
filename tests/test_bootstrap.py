"""The bootstrap helpers are pure and deterministic under a seed."""

from __future__ import annotations

import numpy as np

from eval.experiment import bootstrap_lift_ci, bootstrap_metric_ci


def test_metric_ci_of_a_constant_is_that_constant() -> None:
    mean, lo, hi = bootstrap_metric_ci(np.ones(20), n_bootstrap=200, seed=0)
    assert (mean, lo, hi) == (1.0, 1.0, 1.0)


def test_lift_ci_clear_winner() -> None:
    lift, lo, hi, p = bootstrap_lift_ci(np.ones(50), np.zeros(50), n_bootstrap=500, seed=0)
    assert lift == 1.0
    assert lo == 1.0 and hi == 1.0
    assert p == 0.0  # treatment is never not-better


def test_lift_ci_no_difference_is_not_significant() -> None:
    same = np.full(30, 0.5)
    lift, lo, hi, p = bootstrap_lift_ci(same, same, n_bootstrap=300, seed=0)
    assert lift == 0.0
    assert p == 1.0  # paired bootstrap: every resample has zero lift
