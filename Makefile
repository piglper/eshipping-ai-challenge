.DEFAULT_GOAL := help
PYTHON ?= python3.14
VENV   := .venv
BIN    := $(VENV)/bin

.PHONY: help setup lint format typecheck test check sample migrate

help: ## Muestra esta ayuda
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Crea el entorno, instala dependencias y activa los hooks
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e . --group dev
	git config core.hooksPath .githooks

lint: ## Lint y comprobación de formato
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/lint-imports

format: ## Aplica el formato y las correcciones automáticas
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck: ## Comprobación de tipos (mypy estricto)
	$(BIN)/mypy

test: ## Tests con cobertura
	$(BIN)/pytest --cov --cov-report=term-missing

check: lint typecheck test ## Todo lo que comprueba el CI

migrate: ## Crea o actualiza la base de datos (ESHIPPING_DATABASE_URL; por defecto SQLite en data/output/)
	$(BIN)/alembic upgrade head

sample: ## Genera los datos sintéticos en data_sample/build/
	$(BIN)/python -m eshipping_ai.synthetic
