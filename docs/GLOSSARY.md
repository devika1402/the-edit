# Glossary

Each entry gives the general meaning of a term, then what it means in this project. A reader who knows the term can skim, and a reader who does not gets both.

**Two-stage recommendation.** Splitting the job of picking items into a cheap narrowing step and a careful ordering step. Here the narrowing is SQL retrieval and the ordering is a Python ranker.

**Retrieval.** The first stage, which produces a small set of plausible items per user from cheap signals. Here it runs in BigQuery SQL and yields a few hundred candidates per customer.

**Ranking.** The second stage, which orders the retrieved candidates. Here it is a CatBoost model trained to order each customer's short list.

**Candidate.** One item that retrieval put forward for a customer. The ranker can only order candidates, so a true future purchase that never becomes a candidate can never be recommended.

**Cold start.** A user the model has no history for. Here a customer with no purchase before the cutoff has no feature row, so they are served a popularity ranking of their candidates instead of nothing.

**Co-purchase.** Two items being bought by the same customer. Counting co-purchases across customers gives an item-to-item signal: people who bought this also bought that.

**Repurchase.** A customer buying an item they bought before. It is one of the retrieval signals, because past purchases are often bought again in fashion.

**Temporal holdout.** Splitting train and test by time rather than at random. Here the model trains on everything up to a cutoff date and is tested on the following week, which is how a recommender is judged in practice.

**Leakage.** Letting information from the test period reach training. Here every feature is computed strictly as of the cutoff, and a gate checks this before any training run, because a single full-dataset aggregate would inflate the score.

**MAP@12.** Mean average precision at 12. It rewards putting the items a customer actually bought near the top of a 12-item list. It is the metric the H&M competition used, so the numbers here are comparable to that benchmark.

**Recall@K.** The share of a customer's true purchases that appear anywhere in the top K. It asks whether the right items made the list at all, ignoring their order.

**NDCG@K.** Normalised discounted cumulative gain. A ranking metric that rewards correct items more the higher they sit, with diminishing returns down the list.

**Learning to rank.** Training a model to order a list rather than to score each item on its own, because a row of recommendation slots cares about the order.

**YetiRank.** The listwise objective inside CatBoost used here. It perturbs predicted rankings and optimises a smoothed ranking metric, training grouped by customer so the model learns to order within one customer's list.

**Bootstrap confidence interval.** A range for a metric found by resampling the customers many times and recomputing. Here it puts an interval around the ranker's lift over the baseline, so the win is shown to be more than noise.

**Coverage.** The share of the catalogue that ever gets recommended. Low coverage means the system only ever shows a small slice of the items.

**Intra-list diversity.** How different the items inside one recommendation list are from each other. Higher means a more varied list.

**Novelty.** How non-obvious the recommended items are, measured from how rare they are. Surfacing less popular items scores higher.

**Gini coefficient.** Borrowed from economics, where it measures income inequality. Here it measures how unevenly recommendation exposure is spread across the catalogue. Near zero is even, near one means a few items get almost all the exposure.

**Long-tail share.** The fraction of recommended items that come from outside the bestseller head. A higher share means the system reaches past the obvious hits.

**Segment parity.** Reporting a metric per customer group rather than only overall, so a group that is served poorly does not hide inside a strong average. Here it is MAP@12 per age band and per warm or cold cohort.

**Cold-start fallback.** The rule for serving a user with no history. Here it ranks that customer's candidates by recent popularity, defined once in `models/fallback.py` and shared by evaluation, guardrails, and serving.

**Feature table.** A table of precomputed attributes read many times instead of recomputed per request. Here `feat_customer` and `feat_item` are the lightweight version of a feature store.

**Partitioning and clustering.** Two ways BigQuery lays out a table so a query reads less. Partitioning by date lets a date filter skip whole slices, and clustering by a column co-locates rows for filters and joins on it. Here `stg_transactions` is partitioned by date and clustered by article, which keeps the 31 million row table inside the free tier.

**maximum_bytes_billed.** A BigQuery setting that fails a query if it would scan more than a set number of bytes. Here every query runner sets it from config, so a cost mistake fails instead of billing.

**Application Default Credentials.** The standard way Google client libraries find your identity from the environment without a key file in the code. Here a one-time `gcloud auth application-default login` is all the local setup needs.

**CUPED.** A variance-reduction technique for online experiments that adjusts each user's metric using their pre-experiment behaviour, so an effect is easier to detect with less traffic. It is named in the experiment design as the method to use, and is left for live data.
