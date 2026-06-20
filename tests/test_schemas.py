"""The raw schemas are pure data, so they are checked without BigQuery."""

from __future__ import annotations

from ingestion.schemas import (
    RAW_ARTICLES,
    RAW_CUSTOMERS,
    RAW_TABLES,
    RAW_TRANSACTIONS,
    Column,
    RawTable,
)


def test_three_raw_tables_with_expected_sources() -> None:
    assert [t.table for t in RAW_TABLES] == [
        "raw_transactions",
        "raw_articles",
        "raw_customers",
    ]
    assert RAW_TRANSACTIONS.source_file == "transactions_train.csv"
    assert RAW_ARTICLES.source_file == "articles.csv"
    assert RAW_CUSTOMERS.source_file == "customers.csv"


def test_column_counts_match_the_hm_dataset() -> None:
    assert len(RAW_TRANSACTIONS.columns) == 5
    assert len(RAW_ARTICLES.columns) == 25
    assert len(RAW_CUSTOMERS.columns) == 7


def test_ids_are_strings_to_preserve_leading_zeros() -> None:
    article_id = _column(RAW_TRANSACTIONS, "article_id")
    customer_id = _column(RAW_TRANSACTIONS, "customer_id")
    assert article_id.field_type == "STRING"
    assert customer_id.field_type == "STRING"
    assert _column(RAW_ARTICLES, "article_id").field_type == "STRING"


def test_key_columns_are_required_and_typed() -> None:
    assert _column(RAW_TRANSACTIONS, "t_dat").field_type == "DATE"
    assert _column(RAW_TRANSACTIONS, "t_dat").mode == "REQUIRED"
    assert _column(RAW_TRANSACTIONS, "customer_id").mode == "REQUIRED"
    assert _column(RAW_CUSTOMERS, "customer_id").mode == "REQUIRED"
    assert _column(RAW_CUSTOMERS, "age").field_type == "INT64"


def test_no_duplicate_columns_within_a_table() -> None:
    for table in RAW_TABLES:
        names = [c.name for c in table.columns]
        assert len(names) == len(set(names)), f"duplicate column in {table.table}"


def test_expected_rows_are_the_known_hm_sizes() -> None:
    assert RAW_TRANSACTIONS.expected_rows == 31_788_324
    assert RAW_ARTICLES.expected_rows == 105_542
    assert RAW_CUSTOMERS.expected_rows == 1_371_980


def _column(table: RawTable, name: str) -> Column:
    for column in table.columns:
        if column.name == name:
            return column
    raise AssertionError(f"{name} not found in {table.table}")
