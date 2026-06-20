"""Entry point for ``make guardrails`` / ``python -m guardrails``.

Reports beyond-accuracy metrics for every model, breaks MAP@12 out per customer age
band (segment parity), and sweeps the diversity guardrail to quantify what it costs
in MAP@12. Writes the tables + the trade-off chart under ``reports/``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from core.config import get_settings
from core.logging import configure_logging
from guardrails.experiment import GuardrailsResult, run_guardrails, tradeoff_chart

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


def _takeaway(result: GuardrailsResult) -> str:
    """One honest sentence on what the diversity guardrail costs."""
    curve = result.tradeoff.sort_values("max_per_category")
    strong = curve.iloc[0]  # tightest cap (most diversity)
    weak = curve.iloc[-1]  # loosest cap (~unconstrained top-K)
    k = result.k
    map_off, map_on = float(weak[f"MAP@{k}"]), float(strong[f"MAP@{k}"])
    div_off, div_on = float(weak["intra_list_diversity"]), float(strong["intra_list_diversity"])
    drop = map_off - map_on
    rel = f", {-drop / map_off:+.0%}" if map_off > 0 else ""
    return (
        f"Tightening the category cap from {int(weak['max_per_category'])} to "
        f"{int(strong['max_per_category'])} raises intra-list diversity "
        f"{div_off:.3f} -> {div_on:.3f} (+{div_on - div_off:.3f}) and costs MAP@{k} "
        f"{map_off:.4f} -> {map_on:.4f} ({-drop:+.4f}{rel}). That is the measured "
        f"price of the diversity guardrail."
    )


def main() -> None:
    """Run the guardrails harness and report the three deliverables."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("=== guardrails: beyond-accuracy, parity, and the trade-off curve ===")
    result = run_guardrails(settings)
    k = result.k

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    beyond_path = REPORTS_DIR / "beyond_accuracy.csv"
    parity_path = REPORTS_DIR / "segment_parity.csv"
    tradeoff_csv = REPORTS_DIR / "tradeoff_curve.csv"
    tradeoff_png = REPORTS_DIR / "tradeoff_curve.png"

    def _long(parity: dict[str, pd.DataFrame], dimension: str) -> pd.DataFrame:
        return pd.concat(
            [table.assign(model=name, dimension=dimension) for name, table in parity.items()],
            ignore_index=True,
        )[["model", "dimension", "segment", "n_customers", f"MAP@{k}"]]

    result.beyond_accuracy.to_csv(beyond_path, index=False)
    parity_age = _long(result.parity, "age_band")
    parity_cohort = _long(result.parity_cohort, "cohort")
    pd.concat([parity_age, parity_cohort], ignore_index=True).to_csv(parity_path, index=False)
    result.tradeoff.to_csv(tradeoff_csv, index=False)
    tradeoff_chart(result, tradeoff_png)

    fmt = lambda value: f"{value:.4f}"  # noqa: E731

    print(f"\nBeyond-accuracy metrics on {result.n_customers:,} held-out test customers")
    print(f"(recommendable universe = {result.catalogue_size:,} articles):\n")
    print(result.beyond_accuracy.to_string(index=False, float_format=fmt))

    print(f"\nSegment parity — MAP@{k} per customer age band (OD-2):\n")
    print(parity_age.drop(columns="dimension").to_string(index=False, float_format=fmt))

    print(f"\nSegment parity — MAP@{k} by cold-start cohort (warm = in matrix):\n")
    print(parity_cohort.drop(columns="dimension").to_string(index=False, float_format=fmt))

    print(f"\nTrade-off curve — ranker top-{k} re-ranked as the category cap tightens:\n")
    print(result.tradeoff.to_string(index=False, float_format=fmt))

    print(f"\n{_takeaway(result)}")
    print(f"\nWrote {beyond_path}, {parity_path}, {tradeoff_csv}, and {tradeoff_png}")


if __name__ == "__main__":
    main()
