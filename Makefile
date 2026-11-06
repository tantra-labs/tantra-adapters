.PHONY: default build dev test lint fmt check clean

default: check

build: dev

dev:
	python -m pip install -e . --quiet

test:
	python -m pytest -q

lint:
	ruff check .

fmt:
	ruff format .

check: lint
	ruff format --check .
	python -m pytest -q

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
