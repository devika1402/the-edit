"""Structural D-11 guard: feature SQL must be parameterised by the cutoff."""

from __future__ import annotations

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "features"


def test_feature_sql_files_exist() -> None:
    assert (SQL_DIR / "feat_customer.sql").is_file()
    assert (SQL_DIR / "feat_item.sql").is_file()


def test_every_feature_sql_filters_by_cutoff() -> None:
    # D-11: each transform must filter on the @cutoff parameter, never a hard date.
    for name in ("feat_customer.sql", "feat_item.sql"):
        sql = (SQL_DIR / name).read_text(encoding="utf-8")
        assert "@cutoff" in sql, f"{name} does not reference @cutoff"
        assert "t_dat <= @cutoff" in sql, f"{name} does not filter t_dat <= @cutoff"


def test_feat_item_uses_popularity_window() -> None:
    sql = (SQL_DIR / "feat_item.sql").read_text(encoding="utf-8")
    assert "@pop_window" in sql
