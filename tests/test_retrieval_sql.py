"""Structural checks on the retrieval SQL (no BigQuery)."""

from __future__ import annotations

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "retrieval"


def _read(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def test_retrieval_sql_files_exist() -> None:
    assert (SQL_DIR / "item_copurchase.sql").is_file()
    assert (SQL_DIR / "candidates.sql").is_file()


def test_copurchase_is_a_windowed_self_join() -> None:
    sql = _read("item_copurchase.sql")
    # parameterised window (D-6), never a hard date
    assert "@cutoff" in sql and "@window" in sql and "@neighbors" in sql
    assert "DATE_SUB(@cutoff, INTERVAL @window DAY)" in sql
    # a self-join on customer pairing two different articles
    assert "a.customer_id = b.customer_id" in sql
    assert "a.article_id != b.article_id" in sql


def test_candidates_union_all_signals() -> None:
    sql = _read("candidates.sql")
    assert "@cutoff" in sql and "@window" in sql and "@top_n" in sql
    for source in (
        "'repurchase'",
        "'top_global'",
        "'top_segment'",
        "'copurchase'",
        "'variant'",
        "'category'",
    ):
        assert source in sql, f"candidates.sql is missing the {source} signal"
