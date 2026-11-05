# =============================================================================
# Kisan Mitra (किसान मित्र) - Makefile
# IBM Db2Hack 2026
# =============================================================================

.PHONY: help install ingest test run up down clean

help:
	@echo "🌾 Kisan Mitra (किसान मित्र) - Available Commands:"
	@echo "  make install  - Setup virtualenv and install dependencies"
	@echo "  make up       - Start IBM Db2 Community Edition Docker container"
	@echo "  make down     - Stop IBM Db2 container"
	@echo "  make ingest   - Ingest Mandi prices and build Db2 Vector store"
	@echo "  make test     - Run complete test suite (27 verification tests)"
	@echo "  make run      - Launch Streamlit AI dashboard"
	@echo "  make clean    - Remove build artifacts and temporary caches"

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --prefer-binary -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; fi

up:
	docker compose -f db/docker-compose.yml up -d

down:
	docker compose -f db/docker-compose.yml down

ingest:
	. .venv/bin/activate && python ingest/create_official_docs.py
	. .venv/bin/activate && python ingest/fetch_mandi.py --force-csv
	. .venv/bin/activate && python ingest/build_vector_store.py

test:
	. .venv/bin/activate && pytest -v tests/

run:
	./run.sh

clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
