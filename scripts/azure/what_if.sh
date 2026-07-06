#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --resource-group NAME --parameters FILE"
}

RESOURCE_GROUP=""
PARAMETERS_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group)
      RESOURCE_GROUP="${2:-}"
      shift 2
      ;;
    --parameters)
      PARAMETERS_FILE="${2:-}"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${RESOURCE_GROUP}" || -z "${PARAMETERS_FILE}" ]]; then
  usage
  exit 2
fi

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI is required for what-if."
  exit 3
fi

az deployment group what-if \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/bicep/main.bicep \
  --parameters "${PARAMETERS_FILE}"
