.PHONY: build test test-all format-check format lint typecheck docs-check examples-check release

build:
	.venv/bin/python -m build --wheel --no-isolation

test:
	.venv/bin/python -m pytest -q -m "not slow"

test-all:
	.venv/bin/python -m pytest -q

format-check:
	.venv/bin/ruff format --check src tests examples scripts
	.venv/bin/ruff check src tests examples scripts

format:
	.venv/bin/ruff check --fix src tests examples scripts
	.venv/bin/ruff format src tests examples scripts

lint:
	.venv/bin/ruff check src tests examples scripts

typecheck:
	.venv/bin/mypy src

docs-check:
	.venv/bin/python scripts/check_docs.py

examples-check:
	.venv/bin/python -m pytest -q tests/test_examples.py

release: test-all format-check lint typecheck build
