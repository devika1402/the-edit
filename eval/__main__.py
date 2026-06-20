"""Entry point for ``make eval`` / ``python -m eval``.

Scores popularity, item-item CF, and the CatBoost ranker on the reserved test
holdout, prints the MAP@12 / Recall@12 / NDCG@12 table with the ranker's lift and
confidence interval, and writes the comparison chart + CSV under ``reports/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.config import get_settings
from core.logging import configure_logging
from eval.experiment import comparison_chart, run_experiment

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


def main() -> None:
    """Run the offline experiment and report the results table + chart."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("=== eval: scoring models on the holdout week ===")
    result = run_experiment(settings)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / "model_comparison.csv"
    png_path = REPORTS_DIR / "model_comparison.png"
    result.table.to_csv(csv_path, index=False)
    comparison_chart(result, png_path)

    table = result.table.to_string(index=False, float_format=lambda value: f"{value:.4f}")
    print(f"\nResults on {result.n_customers:,} held-out test customers (holdout week):\n")
    print(table)

    lift, lo, hi, p_value = result.lift
    base = result.map_ci["popularity"][0]
    relative = f" ({lift / base:+.0%} relative)" if base > 0 else ""
    print(
        f"\nRanker lift over popularity (MAP@{result.k}): {lift:+.4f}"
        f"  95% CI [{lo:+.4f}, {hi:+.4f}]  p={p_value:.4f}{relative}"
    )
    print(f"\nWrote {csv_path} and {png_path}")


if __name__ == "__main__":
    main()
