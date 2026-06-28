.PHONY: install format lint type-check test test-cov quality generate-data generate-data-ci ingest-data ingest-data-ci validate-data demo-ingestion-ci clean-data clean-interim clean-quarantine clean-ingestion-reports clean

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

generate-data:
	python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data.yaml

generate-data-ci:
	python3 -m grid_reliability.data_generation.pipeline --config configs/synthetic_data_ci.yaml

ingest-data:
	python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion.yaml

ingest-data-ci:
	python3 -m grid_reliability.ingestion.pipeline --config configs/ingestion_ci.yaml

validate-data: ingest-data

demo-ingestion-ci: generate-data-ci ingest-data-ci
	@echo "Ingestion reports written under reports/ingestion/local-ci"

clean-data:
	rm -f data/raw/smart_meter_events.jsonl data/raw/substation_events.jsonl data/raw/weather_data.csv data/raw/asset_inventory.csv data/raw/maintenance_logs.csv data/raw/outage_history.csv data/raw/_manifest.json

clean-interim:
	rm -f data/interim/*.jsonl

clean-quarantine:
	rm -rf data/quarantine

clean-ingestion-reports:
	rm -rf reports/ingestion

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml build dist *.egg-info
