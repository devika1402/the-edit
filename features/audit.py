"""D-11 temporal-leakage gate for the feature tables.

The gate is pass/fail. A single feature that encodes information from after the
cutoff (a later sale date, a negative "days since" value, or a holdout that does
not exist) would inflate MAP@12 and void the evaluation, so the build is rejected
here before anything can reach Phase 4 training. The checks read the built tables
and compare against the configured cutoff; the date comparison itself is a pure
function, unit-tested without BigQuery.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from core.bq import BigQueryClient
from core.config import Settings
from core.exceptions import DataValidationError

logger = logging.getLogger(__name__)


def scalar(runner: BigQueryClient, sql: str, default_dataset: str) -> Any:
    """Run an aggregate query and return its single scalar value."""
    rows = list(runner.query(sql, default_dataset=default_dataset))
    return rows[0][0]


def assert_date_within_cutoff(label: str, max_date: date | None, cutoff: date) -> None:
    """Raise if ``max_date`` is after the cutoff (pure; unit-tested)."""
    if max_date is not None and max_date > cutoff:
        raise DataValidationError(
            f"leakage: {label} has max date {max_date}, after cutoff {cutoff}"
        )


def leakage_audit(runner: BigQueryClient, settings: Settings, default_dataset: str) -> None:
    """Fail the build if any feature leaks data from after the cutoff (D-11)."""
    cutoff = settings.feature_cutoff_date

    assert_date_within_cutoff(
        "feat_item.last_sale_date",
        scalar(runner, "SELECT MAX(last_sale_date) FROM feat_item", default_dataset),
        cutoff,
    )
    assert_date_within_cutoff(
        "feat_customer.last_purchase_date",
        scalar(runner, "SELECT MAX(last_purchase_date) FROM feat_customer", default_dataset),
        cutoff,
    )

    bad_customer = int(
        scalar(runner, "SELECT COUNTIF(recency_days < 0) FROM feat_customer", default_dataset)
    )
    bad_item = int(
        scalar(
            runner,
            "SELECT COUNTIF(recency_last_sale_days < 0) FROM feat_item",
            default_dataset,
        )
    )
    if bad_customer or bad_item:
        raise DataValidationError(
            f"leakage: negative recency (customer={bad_customer}, item={bad_item})"
        )

    data_max = scalar(runner, "SELECT MAX(t_dat) FROM stg_transactions", default_dataset)
    if data_max is not None and data_max <= cutoff:
        raise DataValidationError(
            f"no holdout: data max {data_max} is not after cutoff {cutoff}; "
            "features would leave nothing to evaluate"
        )

    logger.info("leakage gate PASSED: all features are as of %s, holdout exists", cutoff)
