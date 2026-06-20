# Dataset

The project runs on the H&M Personalized Fashion Recommendations dataset, a record of European fast-fashion shopping. It has three parts.

| File | Rows | What it holds |
|---|---|---|
| `transactions_train.csv` | 31,788,324 | one row per purchase: date, customer, article, price, sales channel |
| `articles.csv` | 105,542 | one row per article: names, product type, colour, department, garment group |
| `customers.csv` | 1,371,980 | one row per customer: age, club status, postal code |

The image files that come with the competition are skipped on purpose. They add many gigabytes and nothing in this project uses them.

## Where the data is

The three CSVs are staged in a Cloud Storage bucket and loaded into BigQuery from there, rather than kept on a laptop. The transactions file alone is about 3.5 GB, and the full set with images would be about 35 GB, so staging in the cloud keeps local disk out of it. BigQuery batch loads from Cloud Storage.

## Cleaning and staging

Loading uses explicit schemas, never autodetect, so the load is reproducible and fails loudly if the source drifts. A few type choices matter. `article_id` is a string, so leading zeros survive. `t_dat` is a date. Only the key columns are required, so a stray null in a descriptive field does not abort a multi-gigabyte load, and boundary checks run afterwards.

Staging narrows and normalises. `stg_transactions` keeps the transaction columns, adds a season and a labelled sales channel, and is partitioned by date and clustered by article so a date-filtered query reads a slice rather than the whole table. `stg_articles` trims the 25 raw article columns to the descriptive and categorical fields the ranker and the guardrails read. `stg_customers` adds an age band. Row counts match the source exactly after staging.

## The cutoff and the holdout

Everything hinges on one date. The cutoff is **2020-09-15**. The model sees only data on or before it, and the week after, **2020-09-16 to 2020-09-22**, is the hidden holdout the model is judged on.

Features are computed strictly as of the cutoff. A leakage gate checks this before any training run: the latest sale date in the item features reads exactly 2020-09-15, all recency values are non-negative, and a holdout exists. The reasoning is in [RESULTS.md](RESULTS.md).

## Feature coverage

Two feature tables come out of staging.

| Table | Rows | Of the total | Why fewer |
|---|---|---|---|
| `feat_customer` | 1,356,709 | 1,371,980 customers | 15,271 customers made no purchase on or before the cutoff, so they have no as-of features |
| `feat_item` | 103,880 | 105,542 articles | 1,662 articles had no sale by the cutoff |

A customer in the test set who has no `feat_customer` row is a cold customer. In the latest run, of 13,797 test customers, 1,131 were cold and 12,666 were warm. Cold customers still get candidates, so they are served by the popularity fallback.

## One caveat on price

The price column in the transactions is a scaled relative index. It compares items to each other in place of an amount in pounds or euros. Any price feature here, including the price tier shown on the demo cards, is relative. This caveat is repeated in the README and the model card so a reader treats the tier as relative.
