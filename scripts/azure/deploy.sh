#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --resource-group NAME --parameters FILE --confirm-deploy"
}

RESOURCE_GROUP=""
PARAMETERS_FILE=""
CONFIRM_DEPLOY="false"
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
    --confirm-deploy)
      CONFIRM_DEPLOY="true"
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ "${CONFIRM_DEPLOY}" != "true" ]]; then
  echo "Deployment blocked. Re-run with --confirm-deploy after approval."
  exit 4
fi

if [[ -z "${RESOURCE_GROUP}" || -z "${PARAMETERS_FILE}" ]]; then
  usage
  exit 2
fi

if ! command -v az >/dev/null 2>&1; then
  echo "Azure CLI is required for deployment."
  exit 3
fi

az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/bicep/main.bicep \
  --parameters "${PARAMETERS_FILE}"
