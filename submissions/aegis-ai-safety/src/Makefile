SHELL := /bin/bash

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: help venv install backend-install frontend-install db-up db-down db-init db-seed \
	demo-papers scifact-data scifact-eval dev-backend dev-frontend test test-integration build lint typecheck clean

help:
	@echo "AEGIS targets:"
	@echo "  make install          Create .venv and install backend + frontend dependencies"
	@echo "  make db-up            Start IBM Db2 12.1.5 in podman (reads .env)"
	@echo "  make db-down          Stop the AEGIS Db2 container"
	@echo "  make db-init          Create schema AEGIS and all tables/indexes"
	@echo "  make db-seed          Insert the synthetic demo evidence document"
	@echo "  make demo-papers      Download the two arXiv PDFs and ingest them as evidence"
	@echo "  make scifact-data     Download the SciFact dataset (CC BY-NC 2.0)"
	@echo "  make scifact-eval     Import SciFact and run a 100-claim held-out evaluation"
	@echo "  make dev-backend      Run FastAPI on http://localhost:8000"
	@echo "  make dev-frontend     Run Next.js on http://localhost:3000"
	@echo "  make test             Unit + API tests (Db2 integration skips)"
	@echo "  make test-integration Full pipeline against real Db2"
	@echo "  make build            Production frontend build"
	@echo "  make lint typecheck   Frontend lint / TypeScript checks"

venv:
	@test -d .venv || python3 -m venv .venv

install: venv backend-install frontend-install

backend-install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements-dev.txt

frontend-install:
	cd frontend && npm install

db-up:
	@test -f .env || (echo "Create .env from .env.example first."; exit 1)
	set -a; . ./.env; set +a; \
	podman run -d --name aegis-db2 --platform linux/amd64 --privileged=true \
		-p "$${DB2_PORT}:50000" \
		-e LICENSE=accept \
		-e DB2INST1_PASSWORD="$${DB2_PASSWORD}" \
		-e DBNAME="$${DB2_DATABASE}" \
		-e ARCHIVE_LOGS=false \
		icr.io/db2_community/db2:12.1.5.0

db-down:
	podman stop aegis-db2 || true

db-init:
	$(PYTHON) database/init_db.py --stats

db-seed:
	$(PYTHON) database/seed.py

demo-papers:
	bash scripts/fetch_demo_papers.sh

scifact-data:
	bash scripts/download_scifact.sh

scifact-eval:
	$(PYTHON) experiments/run_scifact_eval.py --import --limit 100

dev-backend:
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && ../$(PYTHON) -m pytest
	$(PYTHON) -m pytest experiments/tests

test-integration:
	cd backend && AEGIS_TEST_DB2=1 ../$(PYTHON) -m pytest tests/test_integration_db2.py -v

build:
	cd frontend && npm run build

lint:
	cd frontend && npm run lint

typecheck:
	cd frontend && npm run typecheck

clean:
	rm -rf .venv frontend/node_modules frontend/.next
