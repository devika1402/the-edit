"""Deterministic customer split and subsampling for ranker training.

Negative capping is done in SQL (see ``sql/features/training_matrix.sql``), so
these helpers only need to choose *which customers* go into training.
"""

from __future__ import annotations

import random
from collections.abc import Sequence


def split_customers(
    customers: Sequence[str], test_fraction: float, seed: int
) -> tuple[list[str], list[str]]:
    """Split customers into disjoint (train, test) lists, deterministically."""
    shuffled = list(customers)
    random.Random(seed).shuffle(shuffled)
    n_test = round(len(shuffled) * test_fraction)
    test = sorted(shuffled[:n_test])
    train = sorted(shuffled[n_test:])
    return train, test


def subsample(customers: Sequence[str], n: int, seed: int) -> list[str]:
    """Return up to ``n`` customers, deterministically (all if ``n >= len``)."""
    items = list(customers)
    if n >= len(items):
        return items
    return sorted(random.Random(seed).sample(items, n))
