# Architecture

This project is a two-stage recommender. A first stage narrows the whole catalogue down to a few hundred plausible items for a shopper, and a second stage orders that short list carefully. The reason for the split is cost. Scoring all 105,000 articles for every customer with a learned model is wasteful, so the cheap narrowing happens in the warehouse and the careful ordering happens in Python over a small set.

For what the system produces, see [RESULTS.md](RESULTS.md).

## Data flow

![H&M recommender data flow: raw CSVs load into BigQuery, are cleaned into staging, and feed both feature tables and item co-purchase counts; retrieval builds candidates, the CatBoost ranker trains on candidates joined to features, and evaluation, guardrails, and serving all read its output.](images/architecture-data-flow.png)

The shape is one direction, left to right and top to bottom. Raw files load into BigQuery, get cleaned into staging, and feed two things: the feature tables that describe each customer and each item, and the co-purchase counts. Retrieval combines those into a candidate table. The ranker trains on the candidates joined to features, evaluation and the guardrails read its output, and serving walks the same path online for one customer at a time.

## Module map

| Path | What it does | Entry point |
|---|---|---|
| `core/` | typed config from `.env`, logging, custom exceptions, and a BigQuery client that sets `maximum_bytes_billed` on every query | `core/bq.py` |
| `ingestion/` | load the three raw CSVs from Cloud Storage with explicit schemas, then build the staging tables | `python -m ingestion` |
| `features/` | build `feat_customer` and `feat_item`, and run the leakage gate that checks every feature is as of the cutoff | `python -m features` |
| `sql/` | the SQL the pipeline runs, split into `staging/`, `features/`, `retrieval/`, and `serving/` | read by the runners above |
| `models/` | the popularity and item-to-item baselines, the CatBoost ranker, the shared cold-start fallback, and the training orchestration | `python -m models` |
| `eval/` | ranking metrics on hand-checked fixtures, and the experiment harness with bootstrap confidence intervals | `python -m eval` |
| `guardrails/` | coverage, intra-list diversity, novelty, Gini, segment parity, and the greedy diversity re-ranker | `python -m guardrails` |
| `serving/` | the FastAPI app, the `/recommendations` endpoint, and the static `/demo` page | `make serve` |
| `tests/` | unit tests for the metrics, the re-ranker, and the response shapers, none of which touch BigQuery | `make test` |

## Why this shape

A few choices drive the structure, each one a trade-off, kept short here.

The warehouse does the set work and Python does the model. BigQuery is quick and cheap at grouping and joining tens of millions of rows, which is what candidate generation and feature aggregation are. The matrix-factorisation tools inside BigQuery need a paid slot reservation, so the model is in Python where it stays on the free tier and trains in minutes.

Retrieval uses SQL co-purchase counts rather than a learned nearest-neighbour search. At this scale, co-purchase counts find plausible items cheaply and need no extra serving infrastructure. The learned alternative, a two-tower embedding retrieval, would likely raise the recall ceiling and is the main piece of future work.

Features are materialised once into tables, not recomputed per request. The ranker and the serving path read the same precomputed `feat_customer` and `feat_item`, which is the lightweight version of a feature store.

A customer with no purchase history before the cutoff has no row in `feat_customer`, so the ranker cannot score them. They still have candidates, the global and per-segment top sellers, so the cold-start path ranks those by recent popularity rather than returning nothing. This lives in one place, `models/fallback.py`, and evaluation, guardrails, and serving all use it.

## Time and space complexity

Let `N` = transactions (about 31.8 million), `U` = customers, `I` = articles (about 105,000), `C` = candidates per customer (about 580 after retrieval), `K` = final list length (12), `F` = ranker features (29), and `W` = the co-purchase window (90 days).

| Component | Time | Space | What drives it |
|---|---|---|---|
| Load and staging | `O(N)` | `O(N)` | one linear pass over the transactions, plus a partition-and-cluster write |
| Feature build | `O(N)` | `O(U + I)` | grouped aggregation over transactions down to one row per customer and per item |
| Co-purchase self-join | `O(sum of basket_size^2)` over `W` | `O(pairs kept)` | pairs of items bought by the same customer in the window, bounded because basket sizes are small (p99 of 36 distinct items) |
| Candidate generation | `O(U * C)` | `O(U * C)` | a few hundred candidates unioned and de-duplicated per customer |
| Ranking inference | `O(U * C * F)` | `O(C * F)` per customer | scoring `C` candidates over `F` features |
| Greedy re-rank | `O(C * K)` per customer | `O(C)` | each of the `K` picks scans the remaining candidates under the category and bestseller caps |

A note on the co-purchase join, the heaviest query in the project. The window, the de-duplication of (customer, article) before the join, and clustering by `article_id` keep it small. The dry-run estimate and the actual cost were both about 0.35 GB, well inside the free tier and the `maximum_bytes_billed` cap.

### Measured costs and runtimes

These are measured on a laptop.

| Stage | Measured | Notes |
|---|---|---|
| Co-purchase self-join | about 0.35 GB scanned | the dry-run and the billed bytes agreed |
| Candidate table | about 40 million rows | roughly 580 candidates per customer over the evaluated set |
| Ranker training | minutes | CatBoost on a 30,000-customer sample |
| Serving, one request | about 2 to 4 seconds | dominated by a BigQuery feature fetch at request time, not the model |

The serving latency is the weak spot. Almost all of it is the feature fetch at request time, because the endpoint queries BigQuery per request. A production deployment would read precomputed features from a fast store and would precompute the co-purchase score this query derives at request time. The endpoint shows the two-stage online path with a measured number, and a production system would carry the traffic. See [MODEL_CARD.md](MODEL_CARD.md) for the model side of this and [RESULTS.md](RESULTS.md) for the numbers.
