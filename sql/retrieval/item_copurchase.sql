-- item_copurchase: for each article, its top co-occurrence neighbours, computed
-- over a recent window (D-6). This is the heaviest query in the project: a
-- self-join of the windowed transactions on customer_id pairs every two distinct
-- articles the same customer bought.
--
-- Cost control: the `win` CTE is restricted to `t_dat` within @window days of the
-- cutoff (partition pruning) and de-duplicated to DISTINCT (customer, article),
-- so a customer who bought an item many times contributes it once and the join
-- stays bounded by basket size, not purchase count. Only the top @neighbors
-- neighbours per article are kept, so the output is small.
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE item_copurchase AS
WITH win AS (
  SELECT DISTINCT customer_id, article_id
  FROM stg_transactions
  WHERE t_dat > DATE_SUB(@cutoff, INTERVAL @window DAY)
    AND t_dat <= @cutoff
),
pairs AS (
  SELECT
    a.article_id AS article_a,
    b.article_id AS article_b,
    COUNT(*) AS copurchase_count
  FROM win AS a
  JOIN win AS b
    ON a.customer_id = b.customer_id
   AND a.article_id != b.article_id
  GROUP BY article_a, article_b
),
ranked AS (
  SELECT
    article_a,
    article_b,
    copurchase_count,
    ROW_NUMBER() OVER (PARTITION BY article_a ORDER BY copurchase_count DESC, article_b) AS rn
  FROM pairs
)
SELECT article_a, article_b, copurchase_count
FROM ranked
WHERE rn <= @neighbors;
