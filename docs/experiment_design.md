# Experiment design: the online A/B test we would run

This document specifies the **online** test that would confirm it on live
traffic. We have no live users, so this is the design, not a run; the offline
bootstrap is its mirror.

## Randomisation unit: the customer

Assign by `customer_id`, 50/50, sticky for the whole test. Not by session or
impression: recommendations are personalised and a customer generates many
impressions, so impression-level assignment would let one customer see both variants
(contamination) and violate independence. Customer-level assignment matches how the
system is deployed and how we measured offline (per-customer metrics).

## Variants

- **Control:** the incumbent (popularity baseline today).
- **Treatment:** the CatBoost ranker, optionally with the Phase 6 diversity re-ranker.

Single factor, one change at a time, so the measured lift is attributable.

## Primary metric

**Purchases per customer attributable to recommended slots**, over a fixed 2-week
window. MAP@12 was the *offline proxy*; online we measure the business outcome it
stands in for. One primary metric, fixed in advance, to avoid multiple-comparison
inflation.

## Guardrail metrics (must not regress)

- **Catalogue coverage / intra-list diversity** (Phase 6), a ranker can lift
  conversion by collapsing onto bestsellers; we will not ship that.
- **Popularity bias / Gini** of recommended items.
- **Per-segment quality**, no customer age band materially worse off (fairness).
- **Serving latency** (p95) and **return rate**.

Decision rule: ship only if the primary lift is positive with a 95% CI excluding 0
**and** no guardrail regresses beyond its pre-set threshold.

## Sample size and power

Two-sample test, α = 0.05 (two-sided), power = 0.80, so `z_{α/2} + z_β = 1.96 + 0.84 = 2.80`.
For a primary purchase rate, per arm:

```
n ≈ (z_{α/2} + z_β)^2 · [p1(1-p1) + p2(1-p2)] / (p1 - p2)^2
```

**Worked example.** Baseline purchase rate `p1 = 5%`; smallest worthwhile lift = 5%
relative, i.e. `p2 = 5.25%` (absolute Δ = 0.0025):

```
n ≈ 2.80^2 · (0.05·0.95 + 0.0525·0.9475) / 0.0025^2
  ≈ 7.84 · 0.0972 / 6.25e-6
  ≈ 122,000 customers per arm  (~244,000 total)
```

At, say, 50k eligible customers/day that is ~5 days to enrol, run 2 weeks for the
outcome window. If the true effect is smaller, n grows with 1/Δ², which is exactly
what CUPED helps with.

## CUPED (variance reduction)

> **Concept, CUPED (Controlled-experiment Using Pre-Experiment Data).** Sensitivity
> is capped by how noisy the primary metric is across customers. CUPED shrinks that
> noise using a pre-experiment covariate `X` that is correlated with the outcome `Y`
> but, because it is measured *before* assignment, cannot be affected by the
> treatment. We replace `Y` with `Y_adj = Y - θ·(X - mean(X))`, where
> `θ = Cov(Y, X) / Var(X)`. The treatment effect is unbiased (X is pre-treatment),
> but the customer-to-customer baseline variation is subtracted out, so the variance
> of the estimated lift drops by roughly `(1 - ρ²)`, with `ρ` the Y-X correlation.

Here `X` = each customer's purchases in the 4 weeks **before** the test. With a
plausible `ρ ≈ 0.5`, variance falls ~25% (so ~92k/arm instead of 122k); with
`ρ ≈ 0.7`, it roughly halves (~62k/arm). CUPED is named to show command of online
experimentation; it is not implemented here (no live data).

## Analysis

1. Compute the CUPED-adjusted primary per customer.
2. Two-sample test → lift, 95% CI, p-value (the online analogue of the harness's
   bootstrap CI).
3. Check every guardrail against its threshold.
4. Apply the decision rule above.
