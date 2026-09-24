.PHONY: install install-dev install-api test lint typecheck coverage build clean run-cli run-tui run-web run-api help

PACKAGE = widdx-nexus

help:
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  WIDDX Nexus — Makefile                     ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║ install       Install base dependencies      ║"
	@echo "║ install-dev   Install + dev + api deps       ║"
	@echo "║ install-api   Install + api deps             ║"
	@echo "║ test          Run tests (quick)              ║"
	@echo "║ test-v        Run tests (verbose)            ║"
	@echo "║ test-cov      Run tests with coverage        ║"
	@echo "║ lint          Ruff check core/               ║"
	@echo "║ lint-fix      Ruff check + auto-fix          ║"
	@echo "║ typecheck     Mypy type checking (core/)     ║"
	@echo "║ build         Build pip package              ║"
	@echo "║ clean         Remove __pycache__, .pytest_cache, dist║"
	@echo "║ run-cli       Launch CLI (widdx)             ║"
	@echo "║ run-tui       Launch TUI (widdx-tui)         ║"
	@echo "║ run-web       Launch Web UI (widdx-web)      ║"
	@echo "║ run-api       Launch API server (widdx-api)  ║"
	@echo "╚══════════════════════════════════════════════╝"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev,api]"

install-api:
	pip install -e ".[api]"

test:
	python -m pytest tests/ -q --tb=short -x --ignore=tests/test_api_server.py -k "not test_next_run_daily"

test-v:
	python -m pytest tests/ -v --tb=long --ignore=tests/test_api_server.py -k "not test_next_run_daily"

test-cov:
	python -m pytest tests/ --cov=core --cov-report=term --cov-report=html --ignore=tests/test_api_server.py -k "not test_next_run_daily"

lint:
	ruff check core/ cli/ tui/ scripts/

lint-fix:
	ruff check core/ cli/ tui/ scripts/ --fix

typecheck:
	mypy core/ --ignore-missing-imports

build:
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache htmlcov coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

run-cli:
	widdx

run-tui:
	widdx-tui

run-web:
	widdx-web

run-api:
	widdx-api
