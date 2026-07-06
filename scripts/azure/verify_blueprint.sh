#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest tests/unit/test_azure_blueprint.py
