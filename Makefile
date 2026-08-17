# ==============================================================================
# InternIndex Makefile — Convenience Developer Commands
# ==============================================================================

.PHONY: dev start init ingest test clean help

help:
	@echo "InternIndex Developer Commands:"
	@echo "  make dev      - Start all services (Postgres, FastAPI, Dagster, Bot) in 1 command"
	@echo "  make init     - Initialize PostgreSQL database tables"
	@echo "  make ingest   - Run manual multi-source ingestion poll"
	@echo "  make clean    - Stop containers and clean temp files"

dev:
	./start.sh

start:
	./start.sh

init:
	docker compose up -d
	uv sync
	uv run python db/init_db.py

ingest:
	uv run python -m ingestion.runner

clean:
	docker compose down
	find . -type d -name "__pycache__" -exec rm -rf {} +
