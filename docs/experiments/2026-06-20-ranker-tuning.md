# Ranker tuning: trial-and-error log (Phase 4)

**Date:** 2026-06-20
**Question:** can the CatBoost ranker do better than its first honest result?
**Short answer:** no meaningful gain from model-side tuning, it is feature/candidate-limited, not capacity-limited. Documented here so the dead ends are not silently repeated.

## Metric note (read first)

Two different denominators appear below; both are reported to avoid confusion.

- **Glance hit-rate@12 (over *answerable* customers):** of the customers who have at least one true holdout purchase somewhere in their candidates, the fraction who get one into the top 12. This is what `make train` prints.
- **Hit-rate@K (over *all* validation customers):** the fraction of all valid customers with a true purchase in the top K. Used for the ceiling/curve diagnostic.

They reconcile: glance 0.305 ≈ all-customer 0.149 ÷ ceiling 0.49.

## Starting point

After fixing two build-time bugs (a score↔row alignment bug in `recommend`, and a capped-negative validation that flattered popularity, both in DECISIONS.md), the first honest glance was:

| model | hit-rate@12 (answerable) |
| --- | --- |
| popularity | 0.110 |
| item-item CF | 0.117 |
| **CatBoost ranker** | **0.3055** |

The ranker already beats both baselines ~2.6×. The question was whether that 0.305 could go higher.

## Diagnostic: where is the ceiling?

Measured on the 5,082 validation customers (full candidate sets, no negative capping):

- **Candidate ceiling = 0.4896**, that fraction of customers have ≥1 true holdout purchase *somewhere* in their candidates. No ranker can exceed this; it is set by retrieval (Phase 3).
- **Ranker hit-rate@K over all valid customers:**

  | K | 12 | 24 | 50 | 100 | 200 |
  | --- | --- | --- | --- | --- | --- |
  | hit-rate | 0.149 | 0.205 | 0.274 | 0.348 | 0.424 |

**Reading:** the true purchase is usually *in* the candidate set but ranked past position 12 (the curve keeps climbing toward the 0.49 ceiling). So there is genuine *ranking* headroom, the question was whether a better model could pull those buried positives into the top 12.

## Experiments

| # | Lever | Hypothesis | Change | hit-rate@12 | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | Customer×item interaction features | The model sees customer and item features separately but no explicit "does this item fit this customer" signal | Added `category_match`, `colour_match`, `price_ratio` to the matrix (29→32 features) | 0.3051 | No change, CatBoost already learned these interactions from the raw categorical features via tree splits, so they were redundant |
| 2 | Early stopping + more trees | A fixed 300 iterations may be under- or over-fit | Held out a 10% NDCG@12 slice, early stopping, iterations 300→1000 | 0.3051 | No change, the model was already near-converged; early stopping picked a similar tree count |
| 3 | More / harder negatives | Train/serve mismatch: trains vs 50 random candidate-negatives but ranks ~579 at inference | Negatives per customer 50→150 | 0.3047 | No change, the random cap already samples *real* candidates, so the negative distribution was already candidate-like |

All three are within noise of the 0.3055 baseline.

## Why nothing moved it

The blocker is fundamental, not tuning. The traits that make an item a **candidate**, popular, co-purchased, a colour/size variant, in the customer's favourite category, are exactly the traits the *true* next purchase shares with the *plausible non-purchases* around it. With SQL/tabular features alone, the ranker cannot cleanly separate "bought next week" from "looks just as likely but was not." Adding more tabular features or trees does not add separating information that is not already there.

## What would actually help (and why we are not doing it now)

- **Richer item signals, text/image embeddings of the product.** This is the real lever, and it is exactly what **D-12 deliberately scoped out** (SQL co-purchase over ANN/embedding retrieval) for cost and scope. Out of scope by design.
- **Higher retrieval ceiling.** Phase 3 already pushed candidate recall to ~0.49 per customer; further retrieval gains have diminishing returns (logged in the Phase 3 entry).

Both are diminishing-returns relative to the project's scope.

## Decisions taken

- **Kept** the interaction features and early stopping, they are sound practice and harmless, even though they did not help this dataset.
- **Reverted** negatives to 50/customer, 150 gave identical results and trains slower.
- **Banked the result.** Ranker ~2.6× popularity is strong for H&M next-week prediction (the competition's MAP@12 winners scored ~0.035). Knowing the model is feature-limited rather than tuning-limited is the useful finding.

See the Phase 4 entry in `docs/DECISIONS.md` for the decision record.
