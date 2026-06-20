"""Pure validation helpers for ingestion (no BigQuery, unit-tested).

The runtime BigQuery checks (row counts, schema, partitioning) live in
``load`` and ``staging``; these are the small pure pieces they lean on.
"""

from __future__ import annotations

from pathlib import Path


def within_tolerance(actual: int, expected: int, *, rel: float = 0.01) -> bool:
    """Return whether ``actual`` is within ``rel`` (relative) of ``expected``.

    Used to compare loaded BigQuery row counts against the source file's line
    count. A small tolerance absorbs benign differences (for example quoted
    fields containing newlines in ``articles.csv``) while still catching a gross
    mismatch that means the load went wrong.
    """
    if expected < 0 or actual < 0:
        raise ValueError("row counts cannot be negative")
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / expected <= rel


def count_csv_data_rows(path: Path) -> int:
    """Count data rows in a CSV (total lines minus the header), streamed.

    This is a line count, not a strict record count, so a file whose quoted
    fields contain embedded newlines will read slightly high; that is why the
    caller compares with :func:`within_tolerance` rather than for exact equality.
    """
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        total_lines = sum(1 for _ in handle)
    return max(total_lines - 1, 0)
