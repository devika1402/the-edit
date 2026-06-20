-- stg_customers: customers with a derived age_band for segment parity (OD-2).
-- age_band buckets ages into bands and labels missing ages 'unknown', so a
-- per-segment metric never silently drops customers with no age on file.
-- Idempotent: CREATE OR REPLACE. Tables referenced unqualified (default dataset).

CREATE OR REPLACE TABLE stg_customers
AS
SELECT
  customer_id,
  age,
  CASE
    WHEN age IS NULL THEN 'unknown'
    WHEN age < 25 THEN '<25'
    WHEN age < 35 THEN '25-34'
    WHEN age < 45 THEN '35-44'
    WHEN age < 55 THEN '45-54'
    ELSE '55+'
  END AS age_band,
  club_member_status,
  fashion_news_frequency,
  postal_code
FROM raw_customers;
