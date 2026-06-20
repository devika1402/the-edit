"""Explicit schemas for the three raw H&M tables (Phase 1).

Schemas are declared as plain data (no BigQuery import) so they can be
unit-tested without the warehouse; ``ingestion.load`` turns them into
``bigquery.SchemaField`` objects at load time. Explicit schemas (never
autodetect) make the load reproducible and let it fail loudly if the source
drifts.

Type choices worth noting:
- ``article_id`` is **STRING**, not INT, to preserve leading zeros (e.g.
  ``0108775015``). The same applies to other id/code columns we never do
  arithmetic on.
- ``t_dat`` is a real **DATE**; the source format is ``YYYY-MM-DD``.
- Only the key columns are ``REQUIRED`` so a stray null in a descriptive field
  does not abort a multi-gigabyte load; boundary checks run afterwards.
"""

from __future__ import annotations

from typing import NamedTuple


class Column(NamedTuple):
    """One BigQuery column: name, standard-SQL type, and mode."""

    name: str
    field_type: str
    mode: str = "NULLABLE"


class RawTable(NamedTuple):
    """A raw table: its BigQuery name, source CSV, columns, and expected size.

    ``expected_rows`` is the canonical row count of that file in the H&M dataset.
    When loading from GCS (where the source cannot be line-counted locally) it is
    the source-match sanity check: a load that comes back far from this means an
    incomplete upload.
    """

    table: str
    source_file: str
    columns: list[Column]
    expected_rows: int


RAW_TRANSACTIONS = RawTable(
    table="raw_transactions",
    source_file="transactions_train.csv",
    expected_rows=31_788_324,
    columns=[
        Column("t_dat", "DATE", "REQUIRED"),
        Column("customer_id", "STRING", "REQUIRED"),
        Column("article_id", "STRING", "REQUIRED"),
        Column("price", "FLOAT64"),
        Column("sales_channel_id", "INT64"),
    ],
)

RAW_ARTICLES = RawTable(
    table="raw_articles",
    source_file="articles.csv",
    expected_rows=105_542,
    columns=[
        Column("article_id", "STRING", "REQUIRED"),
        Column("product_code", "INT64"),
        Column("prod_name", "STRING"),
        Column("product_type_no", "INT64"),
        Column("product_type_name", "STRING"),
        Column("product_group_name", "STRING"),
        Column("graphical_appearance_no", "INT64"),
        Column("graphical_appearance_name", "STRING"),
        Column("colour_group_code", "INT64"),
        Column("colour_group_name", "STRING"),
        Column("perceived_colour_value_id", "INT64"),
        Column("perceived_colour_value_name", "STRING"),
        Column("perceived_colour_master_id", "INT64"),
        Column("perceived_colour_master_name", "STRING"),
        Column("department_no", "INT64"),
        Column("department_name", "STRING"),
        Column("index_code", "STRING"),
        Column("index_name", "STRING"),
        Column("index_group_no", "INT64"),
        Column("index_group_name", "STRING"),
        Column("section_no", "INT64"),
        Column("section_name", "STRING"),
        Column("garment_group_no", "INT64"),
        Column("garment_group_name", "STRING"),
        Column("detail_desc", "STRING"),
    ],
)

RAW_CUSTOMERS = RawTable(
    table="raw_customers",
    source_file="customers.csv",
    expected_rows=1_371_980,
    columns=[
        Column("customer_id", "STRING", "REQUIRED"),
        Column("FN", "FLOAT64"),
        Column("Active", "FLOAT64"),
        Column("club_member_status", "STRING"),
        Column("fashion_news_frequency", "STRING"),
        Column("age", "INT64"),
        Column("postal_code", "STRING"),
    ],
)

#: The three raw tables, in the order Phase 1 loads them.
RAW_TABLES: list[RawTable] = [RAW_TRANSACTIONS, RAW_ARTICLES, RAW_CUSTOMERS]
