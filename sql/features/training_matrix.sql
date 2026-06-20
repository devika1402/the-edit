-- training_matrix: one row per (customer, candidate) with features + holdout label,
-- restricted to the requested customers (@customers) and with negatives capped per
-- customer (@max_negatives) so the pulled matrix stays laptop-sized. Positives are
-- always kept; negatives are ordered by a deterministic hash, so the cap is a stable
-- pseudo-random sample. Leakage-safe: every feature is as of @cutoff; only `label`
-- looks at t_dat > @cutoff (the prediction target). Tables unqualified (default dataset).

WITH holdout AS (
  SELECT DISTINCT customer_id, article_id
  FROM stg_transactions
  WHERE t_dat > @cutoff
),
copurchase_score AS (
  SELECT
    ri.customer_id,
    cp.article_b AS article_id,
    SUM(cp.copurchase_count) AS copurchase_score
  FROM (
    SELECT DISTINCT t.customer_id, t.article_id
    FROM stg_transactions AS t
    WHERE t.t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY) AND t.t_dat <= @cutoff
  ) AS ri
  JOIN item_copurchase AS cp ON ri.article_id = cp.article_a
  GROUP BY ri.customer_id, cp.article_b
),
base AS (
  SELECT
    c.customer_id,
    c.article_id,
    IF(h.customer_id IS NOT NULL, 1, 0) AS label,
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
    -- customer x item interaction features (the "does this item fit this customer" signal)
    IF(fc.dominant_category = fi.product_group_name, 1, 0) AS category_match,
    IF(fc.dominant_colour = fi.colour_group_name, 1, 0) AS colour_match,
    COALESCE(SAFE_DIVIDE(fi.avg_price, NULLIF(fc.avg_price, 0)), 1.0) AS price_ratio
  FROM candidates AS c
  JOIN feat_customer AS fc USING (customer_id)
  JOIN feat_item AS fi USING (article_id)
  LEFT JOIN holdout AS h ON c.customer_id = h.customer_id AND c.article_id = h.article_id
  LEFT JOIN copurchase_score AS cs ON cs.customer_id = c.customer_id AND cs.article_id = c.article_id
  WHERE c.customer_id IN UNNEST(@customers)
)
SELECT * EXCEPT (neg_rank)
FROM (
  SELECT
    base.*,
    IF(
      label = 1,
      0,
      ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY FARM_FINGERPRINT(CONCAT(customer_id, article_id))
      )
    ) AS neg_rank
  FROM base
)
WHERE label = 1 OR neg_rank <= @max_negatives;
