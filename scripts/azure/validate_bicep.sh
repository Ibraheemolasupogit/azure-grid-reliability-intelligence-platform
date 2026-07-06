#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MAIN_FILE="${ROOT_DIR}/infra/bicep/main.bicep"

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI is not installed; skipping az bicep build/lint."
  echo "Run tests/unit/test_azure_blueprint.py for static blueprint validation."
  exit 0
fi

az bicep build --file "${MAIN_FILE}"
az bicep lint --file "${MAIN_FILE}"
rm -f "${ROOT_DIR}/infra/bicep/main.json"
