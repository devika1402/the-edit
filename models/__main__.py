"""Entry point for ``make train`` / ``python -m models``.

Builds the candidate-feature matrix, trains the popularity baseline, the item-item
CF baseline, and the CatBoost ranker, saves the ranker artifacts, and prints a
weak-ranker glance (validation hit-rate vs the popularity baseline). Idempotent.
"""

from __future__ import annotations

import logging

from core.config import get_settings
from core.logging import configure_logging
from models.train import run_training

logger = logging.getLogger(__name__)


def main() -> None:
    """Train all three approaches and print the weak-ranker glance."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("=== train: baselines + CatBoost ranker ===")
    glance = run_training(settings)
    print("\nPhase 4 training glance (validation slice):")
    for key, value in glance.items():
        print(f"  {key:<28} {value}")


if __name__ == "__main__":
    main()
