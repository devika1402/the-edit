from __future__ import annotations

from models.sampling import split_customers, subsample


def test_split_is_disjoint_and_proportional() -> None:
    customers = [f"c{i}" for i in range(100)]
    train, test = split_customers(customers, test_fraction=0.2, seed=42)
    assert set(train).isdisjoint(test)
    assert sorted(train + test) == sorted(customers)
    assert 15 <= len(test) <= 25


def test_split_is_deterministic() -> None:
    customers = [f"c{i}" for i in range(50)]
    assert split_customers(customers, 0.2, 7) == split_customers(customers, 0.2, 7)


def test_subsample_caps_and_is_stable() -> None:
    customers = [f"c{i}" for i in range(10)]
    assert len(subsample(customers, 3, seed=1)) == 3
    assert subsample(customers, 99, seed=1) == customers  # n >= len returns all
