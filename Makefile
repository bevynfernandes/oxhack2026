.DEFAULT_GOAL := help
.PHONY: install notebooks check format test build docs docs-test frontend-install frontend-check help

install: ## Install locked Python development dependencies.
	uv sync --frozen --group docs

notebooks: ## Install notebook helpers only into the local environment.
	uv pip install --python .venv/bin/python ipykernel ipywidgets

check: ## Check formatting, lint, and types without modifying source.
	uv run --frozen --no-sync ruff check --no-fix .
	uv run --frozen --no-sync ruff format --check .
	uv run --frozen --no-sync mypy

format: ## Format Python source and organize imports.
	uv run --frozen --no-sync ruff check --fix .
	uv run --frozen --no-sync ruff format .

test: ## Run the scaffold packaging checks.
	uv run --frozen --no-sync pytest

build: ## Build the Python package.
	uv build --no-sources

docs: ## Serve the project documentation locally.
	uv run --frozen --no-sync mkdocs serve

docs-test: ## Build documentation with warnings treated as errors.
	uv run --frozen --no-sync mkdocs build --strict

frontend-install: ## Install locked frontend dependencies.
	npm --prefix frontend ci

frontend-check: ## Type-check and build the frontend template.
	npm --prefix frontend run build

help: ## List development targets.
	@sed -n 's/^\([a-z-]*\):.*## /\1: /p' Makefile
