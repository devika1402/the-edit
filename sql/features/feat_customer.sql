-- feat_customer: one row per customer, computed STRICTLY as of @cutoff (D-11).
--
-- Leakage discipline: the only transaction source is filtered `t_dat <= @cutoff`
-- in the `tx` CTE, so nothing from the holdout window (t_dat > @cutoff) can enter
-- any aggregate below. The cutoff arrives as a query parameter, never hard-coded.
--
-- Relative indices: H&M `price` is an already-scaled relative value, so absolute
-- spend is not meaningful on its own. `monetary_index` and `price_affinity_index`
-- divide each customer by the population mean (1.0 = average customer).
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE feat_customer AS
WITH tx AS (
  SELECT
    t.customer_id,
    t.t_dat,
    t.price,
    t.sales_channel,
    a.product_group_name,
    a.colour_group_name
  FROM stg_transactions AS t
  JOIN stg_articles AS a USING (article_id)
  WHERE t.t_dat <= @cutoff
),
per_customer AS (
  SELECT
    customer_id,
    COUNT(*) AS n_transactions,
    COUNT(DISTINCT t_dat) AS n_active_days,
    MAX(t_dat) AS last_purchase_date,
    DATE_DIFF(@cutoff, MAX(t_dat), DAY) AS recency_days,
    DATE_DIFF(@cutoff, MIN(t_dat), DAY) AS tenure_days,
    SUM(price) AS total_spend,
    AVG(price) AS avg_price,
    COUNT(DISTINCT product_group_name) AS n_distinct_categories,
    APPROX_TOP_COUNT(product_group_name, 1)[OFFSET(0)].value AS dominant_category,
    APPROX_TOP_COUNT(colour_group_name, 1)[OFFSET(0)].value AS dominant_colour,
    AVG(IF(sales_channel = 'online', 1.0, 0.0)) AS share_online
  FROM tx
  GROUP BY customer_id
),
population AS (
  SELECT
    AVG(total_spend) AS avg_total_spend,
    AVG(avg_price) AS avg_avg_price
  FROM per_customer
)
SELECT
  pc.customer_id,
  pc.n_transactions,
  pc.n_active_days,
  pc.last_purchase_date,
  pc.recency_days,
  pc.tenure_days,
  pc.total_spend,
  SAFE_DIVIDE(pc.total_spend, pop.avg_total_spend) AS monetary_index,
  pc.avg_price,
  SAFE_DIVIDE(pc.avg_price, pop.avg_avg_price) AS price_affinity_index,
  pc.n_distinct_categories,
  pc.dominant_category,
  pc.dominant_colour,
  pc.share_online,
  c.age,
  COALESCE(c.age_band, 'unknown') AS age_band
FROM per_customer AS pc
CROSS JOIN population AS pop
LEFT JOIN stg_customers AS c USING (customer_id);
