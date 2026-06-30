.PHONY: install format lint type-check test test-cov quality generate-data generate-data-ci ingest-data ingest-data-ci validate-data demo-ingestion-ci forecast-data forecast-data-ci forecast-demo assess-asset-health assess-asset-health-ci asset-health-demo predict-outages predict-outages-ci outage-prediction-demo calculate-reliability calculate-reliability-ci reliability-demo clean-data clean-interim clean-quarantine clean-ingestion-reports clean-forecasting clean-model-artifacts clean-forecast-reports clean-asset-health clean-asset-health-reports clean-outage-prediction clean-outage-models clean-outage-reports clean-reliability clean-reliability-reports clean

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

forecast-data:
	python3 -m grid_reliability.forecasting.pipeline --config configs/forecasting.yaml

forecast-data-ci:
	python3 -m grid_reliability.forecasting.pipeline --config configs/forecasting_ci.yaml

forecast-demo: generate-data-ci ingest-data-ci forecast-data-ci
	@echo "Forecast outputs written under outputs/forecasting/forecast-ci"
	@echo "Forecast reports written under reports/forecasting/forecast-ci"

assess-asset-health:
	python3 -m grid_reliability.asset_health.pipeline --config configs/asset_health.yaml

assess-asset-health-ci:
	python3 -m grid_reliability.asset_health.pipeline --config configs/asset_health_ci.yaml

asset-health-demo: generate-data-ci ingest-data-ci assess-asset-health-ci
	@echo "Asset-health outputs written under outputs/asset_health/asset-health-ci"
	@echo "Asset-health reports written under reports/asset_health/asset-health-ci"

predict-outages:
	python3 -m grid_reliability.outage_prediction.pipeline --config configs/outage_prediction.yaml

predict-outages-ci:
	python3 -m grid_reliability.outage_prediction.pipeline --config configs/outage_prediction_ci.yaml

outage-prediction-demo: generate-data-ci ingest-data-ci predict-outages-ci
	@echo "Outage prediction outputs written under outputs/outage_prediction/outage-prediction-ci"
	@echo "Outage prediction models written under outputs/models/outage_prediction/outage-prediction-ci"
	@echo "Outage prediction reports written under reports/outage_prediction/outage-prediction-ci"

calculate-reliability:
	python3 -m grid_reliability.reliability.pipeline --config configs/reliability.yaml

calculate-reliability-ci:
	python3 -m grid_reliability.reliability.pipeline --config configs/reliability_ci.yaml

reliability-demo: generate-data-ci ingest-data-ci calculate-reliability-ci
	@echo "Reliability outputs written under outputs/reliability/reliability-ci"
	@echo "Reliability reports written under reports/reliability/reliability-ci"

clean-data:
	rm -f data/raw/smart_meter_events.jsonl data/raw/substation_events.jsonl data/raw/weather_data.csv data/raw/asset_inventory.csv data/raw/maintenance_logs.csv data/raw/outage_history.csv data/raw/_manifest.json

clean-interim:
	rm -f data/interim/*.jsonl

clean-quarantine:
	rm -rf data/quarantine

clean-ingestion-reports:
	rm -rf reports/ingestion

clean-forecasting:
	rm -rf outputs/forecasting

clean-model-artifacts:
	rm -rf outputs/models/forecasting

clean-forecast-reports:
	rm -rf reports/forecasting

clean-asset-health:
	rm -rf outputs/asset_health

clean-asset-health-reports:
	rm -rf reports/asset_health

clean-outage-prediction:
	rm -rf outputs/outage_prediction

clean-outage-models:
	rm -rf outputs/models/outage_prediction

clean-outage-reports:
	rm -rf reports/outage_prediction

clean-reliability:
	rm -rf outputs/reliability

clean-reliability-reports:
	rm -rf reports/reliability

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage coverage.xml build dist *.egg-info
