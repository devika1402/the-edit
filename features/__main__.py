"""Entry point for ``make features`` / ``python -m features``.

Builds the feature tables as of the configured cutoff, validates them, runs the
D-11 leakage gate, and prints a row-count summary. Idempotent: safe to re-run.
"""

from __future__ import annotations

import logging

from core.config import get_settings
from core.logging import configure_logging
from features.build import build_features

logger = logging.getLogger(__name__)


def main() -> None:
    """Build and validate the feature tables."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("=== features: building as of %s ===", settings.feature_cutoff_date)
    counts = build_features(settings)

    print(f"\nFeature tables (as of {settings.feature_cutoff_date})")
    for table, count in counts.items():
        print(f"  {table:<16} {count:>12,}")


if __name__ == "__main__":
    main()
