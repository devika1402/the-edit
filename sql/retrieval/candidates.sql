-- candidates: a few hundred candidate articles per customer, unioned and
-- de-duplicated from four cheap signals, each tagged with the source(s) that
-- produced it.
--
-- Scope: materialised for the holdout-buyer evaluation set (the customers recall
-- is measured on). Candidate CONTENT uses only `t_dat <= @cutoff`, so recall is
-- unbiased and identical to generating for everyone; this same SQL generalises to
-- any customer set for training (Phase 4) and serving (Phase 7) by changing only
-- the `target` CTE. Global + segment signals are given to every target so the
-- cold-start buyers (no pre-cutoff history) still get a popularity fallback.
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE candidates AS
WITH target AS (
  SELECT DISTINCT
    h.customer_id,
    COALESCE(c.age_band, 'unknown') AS age_band
  FROM (SELECT DISTINCT customer_id FROM stg_transactions WHERE t_dat > @cutoff) AS h
  LEFT JOIN stg_customers AS c USING (customer_id)
),
repurchase AS (
  SELECT DISTINCT t.customer_id, t.article_id, 'repurchase' AS source
  FROM stg_transactions AS t
  JOIN target USING (customer_id)
  WHERE t.t_dat <= @cutoff
),
global_top AS (
  SELECT article_id
  FROM feat_item
  ORDER BY popularity_recent DESC, article_id
  LIMIT @top_n
),
global_cand AS (
  SELECT tg.customer_id, g.article_id, 'top_global' AS source
  FROM target AS tg
  CROSS JOIN global_top AS g
),
seg_counts AS (
  SELECT
    COALESCE(cu.age_band, 'unknown') AS age_band,
    t.article_id,
    COUNT(*) AS n
  FROM stg_transactions AS t
  JOIN stg_customers AS cu USING (customer_id)
  WHERE t.t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY)
    AND t.t_dat <= @cutoff
  GROUP BY age_band, t.article_id
),
seg_ranked AS (
  SELECT
    age_band,
    article_id,
    ROW_NUMBER() OVER (PARTITION BY age_band ORDER BY n DESC, article_id) AS rn
  FROM seg_counts
),
segment_cand AS (
  SELECT tg.customer_id, sr.article_id, 'top_segment' AS source
  FROM target AS tg
  JOIN seg_ranked AS sr ON tg.age_band = sr.age_band AND sr.rn <= @top_n
),
recent_items AS (
  SELECT DISTINCT t.customer_id, t.article_id
  FROM stg_transactions AS t
  JOIN target USING (customer_id)
  WHERE t.t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY)
    AND t.t_dat <= @cutoff
),
copurchase_scored AS (
  SELECT
    ri.customer_id,
    cp.article_b AS article_id,
    SUM(cp.copurchase_count) AS score
  FROM recent_items AS ri
  JOIN item_copurchase AS cp ON ri.article_id = cp.article_a
  GROUP BY ri.customer_id, cp.article_b
),
copurchase_ranked AS (
  SELECT
    customer_id,
    article_id,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY score DESC, article_id) AS rn
  FROM copurchase_scored
),
copurchase_cand AS (
  SELECT customer_id, article_id, 'copurchase' AS source
  FROM copurchase_ranked
  WHERE rn <= @top_n
),
-- 5. product variants: other articles sharing a product_code with the customer's
-- recent items (the same product in another colour/size). A strong fashion signal.
variant_cand AS (
  SELECT DISTINCT ri.customer_id, a2.article_id, 'variant' AS source
  FROM recent_items AS ri
  JOIN stg_articles AS a1 ON ri.article_id = a1.article_id
  JOIN stg_articles AS a2
    ON a1.product_code = a2.product_code
   AND a2.article_id != a1.article_id
),
-- 6. in-category discovery: recent top sellers within the customer's dominant
-- product group (from feat_customer, so warm customers only).
cat_counts AS (
  SELECT a.product_group_name, t.article_id, COUNT(*) AS n
  FROM stg_transactions AS t
  JOIN stg_articles AS a USING (article_id)
  WHERE t.t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY)
    AND t.t_dat <= @cutoff
  GROUP BY a.product_group_name, t.article_id
),
cat_ranked AS (
  SELECT
    product_group_name,
    article_id,
    ROW_NUMBER() OVER (PARTITION BY product_group_name ORDER BY n DESC, article_id) AS rn
  FROM cat_counts
),
category_cand AS (
  SELECT tg.customer_id, cr.article_id, 'category' AS source
  FROM target AS tg
  JOIN feat_customer AS fc ON tg.customer_id = fc.customer_id
  JOIN cat_ranked AS cr
    ON fc.dominant_category = cr.product_group_name
   AND cr.rn <= @top_n
),
unioned AS (
  SELECT * FROM repurchase
  UNION ALL SELECT * FROM global_cand
  UNION ALL SELECT * FROM segment_cand
  UNION ALL SELECT * FROM copurchase_cand
  UNION ALL SELECT * FROM variant_cand
  UNION ALL SELECT * FROM category_cand
)
SELECT
  customer_id,
  article_id,
  ARRAY_AGG(DISTINCT source ORDER BY source) AS sources
FROM unioned
GROUP BY customer_id, article_id;
