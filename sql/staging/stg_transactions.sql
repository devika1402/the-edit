-- stg_transactions: typed, enriched transactions, physically laid out for cost.
--
-- TEACHING — partitioning and clustering, and why they control cost.
-- BigQuery on-demand billing charges by *bytes scanned*, not rows. Two physical
-- choices shrink what a query must read:
--   * PARTITION BY t_dat  — splits the table into one physical partition per day.
--     A query filtered to a date range (every temporal-holdout query we run)
--     reads only those partitions instead of the whole table. A full scan of
--     31M rows becomes a scan of a few weeks.
--   * CLUSTER BY article_id — sorts/co-locates rows by article within each
--     partition, so filters and joins on article_id (the co-purchase self-join,
--     item features) touch fewer blocks.
-- Together they are what keeps a 31M-row table inside the free tier. The cost
-- guardrail (maximum_bytes_billed) is the backstop; this layout is the design.
--
-- Idempotent: CREATE OR REPLACE rebuilds the table each run.
-- Tables are referenced unqualified; the runner sets a default dataset.

CREATE OR REPLACE TABLE stg_transactions
PARTITION BY t_dat
CLUSTER BY article_id
-- Explicit: never expire partitions. t_dat is historical (2018-2020), so any
-- inherited default partition expiration would drop every partition on write.
OPTIONS (partition_expiration_days = NULL)
AS
SELECT
  t_dat,
  customer_id,
  article_id,
  price,
  sales_channel_id,
  CASE
    WHEN EXTRACT(MONTH FROM t_dat) IN (12, 1, 2) THEN 'winter'
    WHEN EXTRACT(MONTH FROM t_dat) IN (3, 4, 5) THEN 'spring'
    WHEN EXTRACT(MONTH FROM t_dat) IN (6, 7, 8) THEN 'summer'
    ELSE 'autumn'
  END AS season,
  CASE sales_channel_id
    WHEN 1 THEN 'store'
    WHEN 2 THEN 'online'
    ELSE 'unknown'
  END AS sales_channel
FROM raw_transactions;
