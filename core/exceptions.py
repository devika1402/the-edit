"""Custom exception hierarchy for the pipeline.

Why a small, explicit hierarchy: the engineering standards forbid bare
``except`` and require external calls (BigQuery jobs, file IO, model load) to be
wrapped with context and an actionable message. Catching a project-specific
exception lets callers handle *our* failures without swallowing unrelated ones.
Every custom exception inherits from :class:`FashionRecommenderError`, so a
caller can catch the whole family with a single ``except``.
"""

from __future__ import annotations


class FashionRecommenderError(Exception):
    """Base class for every error raised by this project's own code."""


class ConfigError(FashionRecommenderError):
    """Configuration is missing or invalid (e.g. an unset required setting)."""


class SqlFileError(FashionRecommenderError):
    """A ``.sql`` file could not be read, was empty, or failed to render."""


class BigQueryJobError(FashionRecommenderError):
    """A BigQuery job failed, was rejected, or exceeded its byte ceiling."""


class DataValidationError(FashionRecommenderError):
    """A boundary check failed: empty result, unexpected schema, or bad range."""


class ModelTrainingError(FashionRecommenderError):
    """Model training or artifact (de)serialisation failed."""
