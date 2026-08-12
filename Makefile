.PHONY: help up down logs migrate lint typecheck test \
        setup-storage shell-db shell-redis create-migration install

# ============================================================
# AI Contract Risk Analyzer — Developer Makefile
# ============================================================

PYTHON   := python
ALEMBIC  := alembic
PYTEST   := pytest
UVICORN  := uvicorn

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------

up: ## Start backing services (Postgres, Redis, MinIO) in the background
	docker compose up -d
	@echo ""
	@echo "  Services started. Run 'make logs' to tail output."
	@echo "  MinIO console: http://localhost:9001 (minioadmin / minioadmin)"

down: ## Stop and remove containers (data volumes are preserved)
	docker compose down

down-volumes: ## Stop containers AND delete all data volumes (destructive!)
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

migrate: ## Apply all pending Alembic migrations
	$(ALEMBIC) upgrade head

migrate-down: ## Roll back the last migration
	$(ALEMBIC) downgrade -1

create-migration: ## Create a new Alembic migration (requires MSG= argument)
	@if [ -z "$(MSG)" ]; then \
		echo "Usage: make create-migration MSG=\"your migration description\""; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

shell-db: ## Open a psql shell in the Postgres container
	docker compose exec postgres psql -U contract_user -d contract_risk_db

shell-redis: ## Open a redis-cli shell in the Redis container
	docker compose exec redis redis-cli

# ---------------------------------------------------------------------------
# App / Storage Setup
# ---------------------------------------------------------------------------

setup-storage: ## Create MinIO buckets (run once after 'make up')
	$(PYTHON) scripts/create_buckets.py

run: ## Start the FastAPI dev server with hot reload
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Start a Celery worker (development mode)
	celery -A app.workers.celery_app worker -l info --concurrency 2

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

install: ## Install all dependencies including dev extras
	pip install -e ".[dev]"

lint: ## Run ruff linter and formatter check
	ruff check app tests scripts
	ruff format --check app tests scripts

lint-fix: ## Run ruff with auto-fix
	ruff check --fix app tests scripts
	ruff format app tests scripts

typecheck: ## Run mypy strict type checking
	mypy --strict app/

test: ## Run the full test suite with coverage
	$(PYTEST) tests/ -v

test-fast: ## Run tests, skip slow integration tests
	$(PYTEST) tests/ -v -m "not slow"

ci: lint typecheck test ## Run all CI checks locally (lint + typecheck + test)
