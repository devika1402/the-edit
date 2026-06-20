-- candidate_features: one row per (customer, candidate) with the ranker's features,
-- for serving and the cold-start fallback. Unlike training_matrix.sql there is NO
-- holdout/label (serving predicts the future, which has no label), negatives are not
-- capped (serve all candidates), and feat_customer is a LEFT JOIN so cold customers
-- (no pre-cutoff history, absent from feat_customer) still appear -- flagged by
-- `is_warm = FALSE` -- with their item features and a popularity signal, so the
-- fallback can rank them by popularity instead of returning nothing.
-- Leakage-safe: every feature is as of @cutoff. Tables unqualified (default dataset).

WITH copurchase_score AS (
  SELECT
    ri.customer_id,
    cp.article_b AS article_id,
    SUM(cp.copurchase_count) AS copurchase_score
  FROM (
    SELECT DISTINCT t.customer_id, t.article_id
    FROM stg_transactions AS t
    WHERE t.t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY) AND t.t_dat <= @cutoff
      AND t.customer_id IN UNNEST(@customers)  -- per-customer, so cheap for serving
  ) AS ri
  JOIN item_copurchase AS cp ON ri.article_id = cp.article_a
  GROUP BY ri.customer_id, cp.article_b
)
SELECT
  c.customer_id,
  c.article_id,
  COALESCE(sa.prod_name, 'Item') AS prod_name,
  COALESCE(sa.product_type_name, 'Unknown') AS product_type_name,
  fc.customer_id IS NOT NULL AS is_warm,
  fc.recency_days,
  fc.tenure_days,
  fc.n_transactions,
  fc.n_active_days,
  fc.monetary_index,
  fc.price_affinity_index,
  fc.n_distinct_categories,
  fc.share_online,
  fc.age_band,
  fc.dominant_category,
  fc.dominant_colour,
  fi.n_purchases,
  fi.popularity_recent,
  fi.recency_last_sale_days,
  fi.recency_first_sale_days,
  fi.avg_price,
  fi.price_tier,
  COALESCE(fi.product_group_name, 'unknown') AS product_group_name,
  COALESCE(fi.department_name, 'unknown') AS department_name,
  COALESCE(fi.colour_group_name, 'unknown') AS colour_group_name,
  COALESCE(fi.garment_group_name, 'unknown') AS garment_group_name,
  COALESCE(cs.copurchase_score, 0) AS copurchase_score,
  CAST('repurchase' IN UNNEST(c.sources) AS INT64) AS is_repurchase,
  CAST('copurchase' IN UNNEST(c.sources) AS INT64) AS is_copurchase,
  CAST('top_global' IN UNNEST(c.sources) AS INT64) AS is_top_global,
  CAST('top_segment' IN UNNEST(c.sources) AS INT64) AS is_top_segment,
  CAST('variant' IN UNNEST(c.sources) AS INT64) AS is_variant,
  CAST('category' IN UNNEST(c.sources) AS INT64) AS is_category,
  ARRAY_LENGTH(c.sources) AS n_sources,
  IF(fc.dominant_category = fi.product_group_name, 1, 0) AS category_match,
  IF(fc.dominant_colour = fi.colour_group_name, 1, 0) AS colour_match,
  COALESCE(SAFE_DIVIDE(fi.avg_price, NULLIF(fc.avg_price, 0)), 1.0) AS price_ratio
FROM candidates AS c
LEFT JOIN feat_customer AS fc USING (customer_id)
JOIN feat_item AS fi USING (article_id)
JOIN stg_articles AS sa USING (article_id)
LEFT JOIN copurchase_score AS cs
  ON cs.customer_id = c.customer_id AND cs.article_id = c.article_id
WHERE c.customer_id IN UNNEST(@customers);
