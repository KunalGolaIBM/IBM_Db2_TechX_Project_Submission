# MetricGuard developer commands.
# Some shells export PYTHONHOME globally, which breaks virtualenv interpreters; clear it.
unexport PYTHONHOME
SHELL := /bin/bash

PY      := .venv/bin/python
MG      := .venv/bin/metricguard
# Prefer the standalone binary (Homebrew); fall back to the docker CLI plugin.
COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo docker-compose || echo "docker compose") -f docker/compose.yaml --env-file .env

.PHONY: help setup colima-up db-up db-wait db-down db-logs db-reader db-audit-user db-init db-migrate db-verify db-reset health test test-db2 test-live-llm eval eval-llm openapi api

help:
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-12s %s\n",$$1,$$2}'

setup: ## Create .venv and install the backend (Python 3.12)
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e "backend[dev]"
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example - edit the passwords.")

colima-up: ## Start a Colima VM that runs linux/amd64 via QEMU binfmt (Apple Silicon)
	# Rosetta is deliberately OFF: its binfmt handler drops argv[0], so the Db2 image's
	# `su - db2inst1` login shells never load db2profile and db2start/CREATE DATABASE silently fail.
	colima start --profile metricguard --vm-type vz --vz-rosetta=false --arch aarch64 --cpu 6 --memory 12 --disk 60

db-up: ## Start IBM Db2 Community Edition, wait for setup, apply emulation fix-ups
	$(COMPOSE) up -d db2
	@$(MAKE) --no-print-directory db-wait
	bash scripts/db2_post_setup.sh

db-wait:
	@echo "Waiting for Db2 setup to complete (first start takes several minutes under emulation)..."
	@for i in $$(seq 1 180); do \
	  if docker logs metricguard-db2 2>&1 | grep -q "Setup has completed"; then echo "Db2 is ready."; exit 0; fi; \
	  sleep 5; done; echo "Timed out waiting for Db2" >&2; exit 1

db-down: ## Stop Db2 (data volume is kept)
	$(COMPOSE) down

db-logs:
	docker logs --tail 100 -f metricguard-db2

db-reader: ## Create the SELECT-only OS user used for analytical queries (local container only)
	bash scripts/create_reader_user.sh

db-audit-user: ## Create the append-only audit OS user (INSERT+SELECT on QUERY_AUDIT_LOG; local container only)
	bash scripts/create_reader_user.sh audit

db-migrate: ## Non-destructive Stage 2 migration on an existing database (audit columns + audit grants)
	$(MG) db migrate

db-init: ## Create schema, seed deterministic data, register metrics, RUNSTATS, grants
	$(MG) db init --reset
	bash scripts/db2_runstats.sh

db-verify: ## Run analytical verification queries against Db2 and write evidence/
	$(MG) db verify

db-reset: db-init ## Alias: drop and rebuild the METRICGUARD schema

health: ## Check Db2 connectivity
	$(MG) health

test: ## Unit tests (no database required)
	$(PY) -m pytest -q

test-db2: ## Unit + live Db2 integration tests
	MG_RUN_DB2_TESTS=1 $(PY) -m pytest -q

test-live-llm: ## Real LangChain + Meta Model API (AI_PROVIDER=meta, MODEL_API_KEY) + Db2 tests; costs API credits
	MG_RUN_DB2_TESTS=1 MG_RUN_LIVE_LLM_TESTS=1 $(PY) -m pytest -q backend/tests/test_live_llm.py

eval: ## Benchmark (DEMO_RULE_BASED planner) through FastAPI + live Db2 -> evaluation/benchmark-demo.json
	$(MG) eval --planner demo --out evaluation/benchmark-demo.json

eval-llm: ## Benchmark with the real LLM provider (Meta by default), core + unseen suites -> evaluation/benchmark-meta.json (costs API credits)
	$(MG) eval --planner llm --suite all --out evaluation/benchmark-meta.json

openapi: ## Export docs/openapi.json from the FastAPI app
	$(MG) openapi --out docs/openapi.json

api: ## Run the API on :8000
	$(PY) -m uvicorn metricguard.api.app:app --reload --port 8000
