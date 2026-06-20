-- feat_item: one row per article sold as of @cutoff (D-11).
--
-- Leakage discipline: the `tx` CTE filters `t_dat <= @cutoff`, so popularity,
-- recency, and price are all as-of the cutoff. `popularity_recent` counts only
-- the @pop_window days ending at the cutoff (a fresher demand signal than the
-- all-time count). Items with no sale on/before the cutoff are absent by design
-- (they have no popularity or recency to compute).
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE feat_item AS
WITH tx AS (
  SELECT
    article_id,
    t_dat,
    price
  FROM stg_transactions
  WHERE t_dat <= @cutoff
),
per_item AS (
  SELECT
    article_id,
    COUNT(*) AS n_purchases,
    COUNTIF(t_dat > DATE_SUB(@cutoff, INTERVAL @pop_window DAY)) AS popularity_recent,
    MIN(t_dat) AS first_sale_date,
    MAX(t_dat) AS last_sale_date,
    DATE_DIFF(@cutoff, MIN(t_dat), DAY) AS recency_first_sale_days,
    DATE_DIFF(@cutoff, MAX(t_dat), DAY) AS recency_last_sale_days,
    AVG(price) AS avg_price
  FROM tx
  GROUP BY article_id
),
tiered AS (
  SELECT
    *,
    NTILE(5) OVER (ORDER BY avg_price) AS price_tier
  FROM per_item
)
SELECT
  ti.article_id,
  ti.n_purchases,
  ti.popularity_recent,
  ti.first_sale_date,
  ti.last_sale_date,
  ti.recency_first_sale_days,
  ti.recency_last_sale_days,
  ti.avg_price,
  ti.price_tier,
  a.product_group_name,
  a.department_name,
  a.colour_group_name,
  a.garment_group_name
FROM tiered AS ti
LEFT JOIN stg_articles AS a USING (article_id);
