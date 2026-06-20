"""Core infrastructure shared by every pipeline stage.

Centralised configuration, logging, custom exceptions, and the typed BigQuery
client wrapper live here. Pipeline stages (ingestion, models, eval, guardrails,
serving) import from ``core`` rather than re-implementing any of it.
"""
