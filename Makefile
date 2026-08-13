# ---------------------------------------------------------------------------
# White Bird Zanzibar — Site Management Module
# Developer workflow
# ---------------------------------------------------------------------------

PYTHON       ?= .venv/bin/python
PIP          ?= .venv/bin/pip
MANAGE       ?= $(PYTHON) manage.py
SETTINGS     ?= config.settings.dev
PYTEST       ?= .venv/bin/pytest
RUFF         ?= .venv/bin/ruff
MYPY         ?= .venv/bin/mypy
PRECOMMIT    ?= .venv/bin/pre-commit

.PHONY: help setup install migrate makemigrations run worker beat lint format type test \
        quality docker-build docker-up docker-down seed

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Create the virtualenv and install all dependencies
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/dev.txt -r requirements/test.txt
	$(PRECOMMIT) install

install: ## Install (or reinstall) dependencies
	$(PIP) install -r requirements/dev.txt -r requirements/test.txt

migrate: ## Apply migrations (local DB)
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(MANAGE) migrate

makemigrations: ## Create migrations from model changes
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(MANAGE) makemigrations

run: ## Run the development server
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(MANAGE) runserver

worker: ## Run a Celery worker
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(PYTHON) -m celery -A config worker --loglevel=info

beat: ## Run the Celery beat scheduler
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(PYTHON) -m celery -A config beat --loglevel=info

lint: ## Lint with Ruff
	$(RUFF) check .

format: ## Auto-format with Ruff
	$(RUFF) format .
	$(RUFF) check . --fix

type: ## Static type check with Mypy
	$(MYPY) apps config

test: ## Run the test suite with branch coverage (90% gate)
	DJANGO_SETTINGS_MODULE=config.settings.test $(PYTEST) --cov=apps --cov-branch --cov-report=term-missing --cov-fail-under=90 -q

test-fast: ## Run tests without coverage
	DJANGO_SETTINGS_MODULE=config.settings.test $(PYTEST)

quality: ## Run every quality gate
	$(MAKE) lint
	$(MAKE) type
	$(MAKE) test
	DJANGO_SETTINGS_MODULE=config.settings.test $(MANAGE) makemigrations --check --dry-run

seed: ## Seed a demo tenant (idempotent)
	DJANGO_SETTINGS_MODULE=$(SETTINGS) $(MANAGE) seed_sites

docker-build: ## Build the application image
	docker compose build

docker-up: ## Start db + redis + web
	docker compose up -d --build

docker-down: ## Stop the compose stack
	docker compose down
