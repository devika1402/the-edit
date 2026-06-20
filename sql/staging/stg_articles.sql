-- stg_articles: the article columns the recommender actually uses, normalised.
-- Free-text names are trimmed; the wide raw catalogue (25 columns) is narrowed
-- to the descriptive and categorical fields the ranker and guardrails read.
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE stg_articles
AS
SELECT
  article_id,
  product_code,
  TRIM(prod_name) AS prod_name,
  product_type_name,
  product_group_name,
  colour_group_name,
  perceived_colour_value_name,
  perceived_colour_master_name,
  department_name,
  index_name,
  index_group_name,
  section_name,
  garment_group_name,
  detail_desc
FROM raw_articles;
