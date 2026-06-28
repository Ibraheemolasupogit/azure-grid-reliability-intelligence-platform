.PHONY: install format lint type-check test test-cov quality clean

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

format:
	python -m ruff format .
	python -m ruff check . --fix

lint:
	python -m ruff check .
	python -m ruff format --check .

type-check:
	python -m mypy src

test:
	python -m pytest

test-cov:
	python -m pytest --cov --cov-report=term-missing

quality: lint type-check test-cov

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml build dist *.egg-info

