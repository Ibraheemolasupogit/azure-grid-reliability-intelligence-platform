from __future__ import annotations

import ipaddress
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_azure_blueprint_structure() -> None:
    required = [
        "infra/bicep/main.bicep",
        "infra/bicep/parameters/dev.bicepparam",
        "infra/bicep/parameters/test.bicepparam",
        "infra/bicep/parameters/prod.bicepparam",
        "scripts/azure/validate_bicep.sh",
        "scripts/azure/what_if.sh",
        "scripts/azure/deploy.sh",
        "scripts/azure/verify_blueprint.sh",
        "docs/azure/reference-architecture.md",
        "docs/security/threat-model.md",
        "docs/security/azure-security-control-matrix.md",
        "docs/azure/operational-readiness-checklist.md",
    ]
    for relative in required:
        assert (ROOT / relative).exists(), relative

    module_paths = re.findall(r"modules/[^\']+\.bicep", _read("infra/bicep/main.bicep"))
    assert module_paths
    for module in module_paths:
        assert (ROOT / "infra/bicep" / module).exists(), module


def test_security_defaults_and_no_credentials() -> None:
    text = _all_blueprint_text()
    bicep_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "infra").rglob("*.bicep"))
    )
    assert "allowBlobPublicAccess: false" in text
    assert "supportsHttpsTrafficOnly: true" in text
    assert "minimumTlsVersion: 'TLS1_2'" in text
    assert "enableSoftDelete: true" in text
    assert "enablePurgeProtection: true" in text
    assert "type: 'SystemAssigned'" in text
    assert "Owner" not in bicep_text
    assert "roleDefinitionId: '*'" not in bicep_text
    assert not re.search(r"(?i)(client_secret|password|secret_value)\s*=", text)
    assert not re.search(
        r"/subscriptions/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text,
    )


def test_environment_parameters_are_separated_and_production_restricted() -> None:
    dev = _read("infra/bicep/parameters/dev.bicepparam")
    test = _read("infra/bicep/parameters/test.bicepparam")
    prod = _read("infra/bicep/parameters/prod.bicepparam")
    assert "environment = 'dev'" in dev
    assert "environment = 'test'" in test
    assert "environment = 'prod'" in prod
    assert "allowPublicNetworkAccess = true" in dev
    assert "allowPublicNetworkAccess = false" in test
    assert "allowPublicNetworkAccess = false" in prod
    assert "logRetentionDays = 180" in prod

    for content in (dev, test, prod):
        cidrs = re.findall(r"'(10\.\d+\.\d+\.0/\d+)'", content)
        networks = [ipaddress.ip_network(cidr) for cidr in cidrs]
        assert all(network.version == 4 for network in networks)
        for left_index, left in enumerate(networks):
            for right in networks[left_index + 1 :]:
                if left.prefixlen == right.prefixlen:
                    assert not left.overlaps(right)


def test_scripts_are_safe_and_ci_does_not_deploy() -> None:
    for script in ("validate_bicep.sh", "what_if.sh", "deploy.sh", "verify_blueprint.sh"):
        text = _read(f"scripts/azure/{script}")
        assert "set -euo pipefail" in text
        assert "client_secret" not in text
        assert "--subscription" not in text

    deploy = _read("scripts/azure/deploy.sh")
    assert "--confirm-deploy" in deploy
    assert "Deployment blocked" in deploy

    workflow = _read(".github/workflows/iac.yml")
    assert "azure/login" not in workflow
    assert "deploy.sh" not in workflow
    assert "verify-azure-blueprint" in workflow


def test_docs_and_diagrams_mark_blueprint_only() -> None:
    docs = [
        "docs/azure/reference-architecture.md",
        "docs/azure/service-mapping.md",
        "docs/security/azure-security-control-matrix.md",
        "docs/security/threat-model.md",
        "docs/milestones/milestone-11.md",
    ]
    for relative in docs:
        assert "BLUEPRINT" in _read(relative)

    adr_files = sorted((ROOT / "docs/architecture/decisions").glob("ADR-*.md"))
    assert len(adr_files) >= 10
    diagrams = sorted((ROOT / "diagrams/azure").glob("*.mmd"))
    assert len(diagrams) >= 8


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _all_blueprint_text() -> str:
    roots = [
        ROOT / "infra",
        ROOT / "docs/azure",
        ROOT / "docs/security",
        ROOT / "scripts/azure",
    ]
    return "\n".join(
        path.read_text(encoding="utf-8")
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
