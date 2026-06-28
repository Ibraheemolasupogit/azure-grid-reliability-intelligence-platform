# Local Development

## Prerequisites

- Python 3.11 or later.
- A local virtual environment.
- No Azure credentials are required for Milestone 1.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
make install
```

## Quality Checks

```bash
make quality
```

This runs Ruff, Ruff format check, mypy, and pytest with coverage.

## Configuration

Base settings live in `configs/base.yaml`. Local non-secret overrides may be set through environment variables shown in `.env.example`.

Do not commit `.env`, Azure credentials, generated data, trained models, report outputs, or local caches.

