"""Entry point for ``make ingest`` / ``python -m ingestion``.

Loads the raw tables, builds and validates the staging tables, and prints a
row-count summary. Idempotent: safe to re-run.
"""

from __future__ import annotations

import logging

from core.config import get_settings
from core.logging import configure_logging
from ingestion.load import load_raw_tables
from ingestion.staging import build_staging

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full ingestion phase: raw load then staging build."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("=== ingestion: raw load ===")
    raw_counts = load_raw_tables(settings)

    logger.info("=== ingestion: staging build ===")
    staging_counts = build_staging(settings)

    print("\nRow counts")
    print("  raw:")
    for table, count in raw_counts.items():
        print(f"    {table:<18} {count:>12,}")
    print("  staging:")
    for table, count in staging_counts.items():
        print(f"    {table:<18} {count:>12,}")


if __name__ == "__main__":
    main()
