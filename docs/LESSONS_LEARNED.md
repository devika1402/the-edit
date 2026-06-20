# Lessons learned

A look back at what went wrong, what caught me off guard, and what I would do differently. The blow-by-blow of each bug is in [TROUBLESHOOTING.md](TROUBLESHOOTING.md). This is the reflection on top of it.

## The scariest numbers came from the plumbing

Two of the worst-looking moments turned out to be measurement, not modelling. The ranker scored worse than popularity on the first comparison, which read like the whole approach was wrong. It was a row-alignment bug, scores written back onto an unsorted frame. Later, an age band scored near zero, which read like a fairness failure. It was cold customers being dropped by a join and mislabelled. Both times the instinct to distrust the model was the wrong instinct. The lesson I took is to check the plumbing before the method, because a broken join or a misaligned index produces numbers that look like a deep failure and are nothing of the kind.

## Retrieval is the ceiling, and I underspent on it at first

I spent a lot of effort tuning the ranker and very little moved. Adding interaction features, early stopping, and more negatives all left MAP@12 within a thousandth of where it started. The diagnostic that explained it was simple: only about a quarter of true next purchases were in the candidate set at all, so three quarters of the possible score was already gone before the ranker saw anything. The model was close to the best it could do with what retrieval handed it. The lever that mattered was the first stage, and revising it twice lifted candidate recall by more than forty percent, which mattered far more than any model change. If I started again I would measure candidate recall on day one and treat it as the number to beat.

## BigQuery has sharp edges that do not look like errors

The sandbox expiry emptying the staging table is the one that stuck. The query succeeded, the bytes were scanned, and the table was empty, because partitions dated in the past expired the moment they were written. Nothing raised an error. The same theme showed up in the run-to-run variance, where tie-breaking in a top-N selection changed the candidate set between runs with no error. Neither was a crash. Both taught me to validate row counts and to pin down anything non-deterministic, rather than trust that a green run means a correct one.

## MAP@12 is stricter than it feels

The hit-rate glance during training read about 0.30, and the proper MAP@12 came in around 0.03. That gap is not a regression, it is the metric doing its job: MAP rewards putting the few relevant items high in a short list and normalises hard, so a model that finds the right item but ranks it tenth gets little credit. Seeing the two side by side made the metric concrete in a way the definition never did.

## What I would change next

- **Make the pipeline reproducible.** Add an explicit secondary sort key to the retrieval selections so ties always break the same way, and the headline number stops drifting between runs.
- **Precompute serving features.** Almost all of the serving latency is a BigQuery fetch at request time. Reading precomputed features from a fast store would turn a couple of seconds into milliseconds, which is the step from a demonstration to a production path.
- **Build the two-tower retrieval.** The recall ceiling is the limit, and a learned embedding retrieval is the most likely way to raise it. It is a stub today.
- **Draw the second guardrail curve.** The trade-off curve sweeps the category cap. The bestseller cap is in the re-ranker and reported through Gini and long-tail share, but a second curve sweeping it would round out the safety story.
- **Give cold customers more than popularity.** Cold customers all get the same fallback. A light cold-profile signal, even from age band and channel, would let them be served as something better than the average shopper.

## What I would keep

The trade-off framing earned its place. Building the guardrails and the curve, rather than only chasing MAP@12, is what lets the project say what shipping the model would cost the catalogue, beyond the score. The strict time-based split with a leakage gate was worth the discipline, because it means the numbers are the kind you can defend.