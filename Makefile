# H&M recommender — developer entry points.
# Tooling targets (install, auth, lint, typecheck, test) work today.
# Pipeline targets are wired in their respective phases; until then they exit 1
# with the phase that builds them.

VENV := fvenv
PY := $(VENV)/bin/python

.PHONY: install auth lint typecheck test ingest features retrieval train eval guardrails serve all help

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Create/refresh the venv and install deps (+ dev tools).
	@test -d $(VENV) || python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

auth: ## One-time: set up Application Default Credentials for local BigQuery.
	gcloud auth application-default login

lint: ## Lint and format-check with ruff.
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

typecheck: ## Type-check with mypy.
	$(PY) -m mypy

test: ## Run unit tests with pytest.
	$(PY) -m pytest

ingest: ## Load raw CSVs + build staging tables (Phase 1).
	$(PY) -m ingestion

features: ## Build customer + item feature tables (Phase 2).
	$(PY) -m features

retrieval: ## Build candidates + report candidate recall (Phase 3).
	$(PY) -m retrieval

train: ## Train baselines + CatBoost ranker (Phase 4).
	$(PY) -m models

eval: ## Run the experiment harness, write results + chart (Phase 5).
	$(PY) -m eval

guardrails: ## Beyond-accuracy metrics + trade-off report (Phase 6).
	$(PY) -m guardrails

serve: ## Start the FastAPI recommendations endpoint (Phase 7).
	$(PY) -m uvicorn serving.app:create_app --factory --host 127.0.0.1 --port 8000

all: ingest features retrieval train eval guardrails ## Full pipeline (excludes serve + two-tower).
