# Models

The project runs three approaches on the same task, because the comparison is the point. Two are simple baselines and one is a learned ranker. All three return the top twelve through one shared interface, so evaluation treats them the same way. The numbers are in [RESULTS.md](RESULTS.md).

## The two baselines

**Recent popularity.** Rank a customer's candidates by how often each item sold in the recent window. This is the floor. If a learned model cannot beat showing the current bestsellers, it is not earning its place.

**Item-to-item co-purchase.** Rank a customer's candidates by the co-occurrence score from retrieval, which counts how often other customers bought an item alongside what this customer bought. This is a collaborative-filtering method and a fairer bar than popularity.

## The ranker

The ranker is a CatBoost model using the YetiRank objective, trained to order each customer's candidate list. Learning to rank means it is trained on the order of a list, not on scoring each item alone, which is what a row of recommendation slots needs. Training is grouped by customer, so the model learns to order within one customer's candidates rather than across customers.

It reads 29 features per candidate, 8 of them categorical. The features are a blend of item signals (recent popularity, recency since first and last sale, average price, price tier, department, colour, garment group), customer signals (recency, tenure, frequency, monetary index, price affinity, dominant category and colour, channel mix, age band), the retrieval signals that produced the candidate (repurchase, co-purchase score, top-seller flags, variant and category flags), and a few customer-by-item interaction features (category match, colour match, price ratio).

### Why CatBoost over LightGBM

The plan first named LightGBM LambdaMART, the standard gradient-boosted ranker. The model was switched to CatBoost. The reason is the data. The H&M articles are full of high-cardinality categoricals: colour, department, garment group, product type, customer age band. CatBoost handles these natively with ordered target statistics under ordered boosting, so there is no manual one-hot or target encoding step that could leak the label. LightGBM would have needed that encoding by hand. CatBoost stays a credible, laptop-trainable learning-to-rank method while removing a whole class of leakage risk. The cost is a heavier library and slightly slower training, which did not matter at this scale.

## The cold-start fallback

A customer with no purchase history before the cutoff has no feature row, so neither the ranker nor the co-purchase baseline can score them. They still have candidates, the global and per-segment top sellers, so the right behaviour is to rank those by recent popularity. This lives once in `models/fallback.py` and is shared by evaluation, the guardrails harness, and serving, so the same fallback is used everywhere and the ranker-versus-popularity comparison stays fair.

## Training discipline

Training uses a sampled subset of customers, 30,000 of them, with negatives capped per customer, so it finishes in minutes on a laptop. Using all 1.3 million customers would not demonstrate anything the sample does not and would slow every iteration. The split is strict and time-based: features as of the cutoff, labels from the holdout week, and the test customers are reserved before training so they are never seen. The trained model and the exact feature list are saved as artifacts (`artifacts/ranker.cbm` and `artifacts/feature_list.json`).

For the model card, see [MODEL_CARD.md](MODEL_CARD.md).
