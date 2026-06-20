"""Entry point for ``make retrieval`` / ``python -m retrieval``.

Builds the candidate tables (dry-running the co-purchase self-join first), then
measures and prints candidate recall against the holdout. Idempotent.
"""

from __future__ import annotations

import logging

from core.config import get_settings
from core.logging import configure_logging
from retrieval.build import build_candidates
from retrieval.recall import measure_recall

logger = logging.getLogger(__name__)


def main() -> None:
    """Build candidates and report the co-purchase byte estimate + candidate recall."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("=== retrieval: building candidates ===")
    build = build_candidates(settings)
    logger.info("=== retrieval: measuring candidate recall ===")
    recall = measure_recall(settings)

    estimate = build["copurchase_estimated_bytes"]
    print(f"\nCo-purchase self-join dry-run: {estimate:,} bytes (~{estimate / 1e9:.2f} GB)")
    print(f"item_copurchase rows : {build['item_copurchase_rows']:,}")
    print(
        f"candidates rows      : {build['candidates_rows']:,}"
        f"  (customers: {build['candidate_customers']:,})"
    )
    print("\nCandidate recall vs holdout week (2020-09-16..09-22):")
    print(f"  {'cohort':<6} {'customers':>10} {'mean_recall':>12} {'micro_recall':>13}")
    for row in recall:
        cohort = row["cohort"] or "ALL"
        print(
            f"  {cohort:<6} {row['n_customers']:>10,} "
            f"{row['mean_recall']:>12} {row['micro_recall']:>13}"
        )


if __name__ == "__main__":
    main()
