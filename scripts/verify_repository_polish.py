from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "README.md",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/portfolio/project-overview.md",
    "docs/portfolio/interview-talking-points.md",
    "docs/portfolio/skills-mapping.md",
    "docs/portfolio/architecture-walkthrough.md",
    "docs/portfolio/reviewer-guide.md",
    "docs/portfolio/demo-script.md",
    "docs/portfolio/final-deliverables.md",
    "docs/portfolio/limitations-and-assumptions.md",
    "docs/portfolio/README.md",
    "docs/milestones/roadmap.md",
    "docs/milestones/milestone-12.md",
    "docs/architecture/README.md",
    "docs/data/README.md",
    "docs/forecasting/README.md",
    "docs/asset-health/README.md",
    "docs/outage-prediction/README.md",
    "docs/reliability/README.md",
    "docs/monitoring/README.md",
    "docs/genai/README.md",
    "docs/reporting/README.md",
    "docs/azure/README.md",
    "docs/security/README.md",
    "diagrams/README.md",
    "dashboard/README.md",
    "infra/README.md",
]

REQUIRED_DIAGRAMS = [
    "diagrams/high-level-platform-architecture.mmd",
    "diagrams/end-to-end-data-flow.mmd",
    "diagrams/governed-ingestion-data-flow.mmd",
    "diagrams/forecasting-workflow.mmd",
    "diagrams/asset-health-workflow.mmd",
    "diagrams/outage-prediction-workflow.mmd",
    "diagrams/reliability-analytics-workflow.mmd",
    "diagrams/monitoring-observability-workflow.mmd",
    "diagrams/genai-assistant-workflow.mmd",
    "diagrams/reporting-semantic-model-flow.mmd",
    "diagrams/azure/azure-reference-architecture.mmd",
    "diagrams/azure/azure-network-topology.mmd",
    "diagrams/azure/azure-data-flow.mmd",
]

REQUIRED_CONFIGS = [
    "configs/synthetic_data_ci.yaml",
    "configs/ingestion_ci.yaml",
    "configs/forecasting_ci.yaml",
    "configs/asset_health_ci.yaml",
    "configs/outage_prediction_ci.yaml",
    "configs/reliability_ci.yaml",
    "configs/monitoring_ci.yaml",
    "configs/genai_assistant_ci.yaml",
    "configs/reporting_ci.yaml",
    ".github/workflows/ci.yml",
    ".github/workflows/iac.yml",
    "infra/bicep/main.bicep",
]

REQUIRED_MAKE_TARGETS = [
    "quality",
    "generate-data-ci",
    "ingest-data-ci",
    "forecast-data-ci",
    "assess-asset-health-ci",
    "predict-outages-ci",
    "calculate-reliability-ci",
    "monitor-platform-ci",
    "run-assistant-ci",
    "build-reporting-model-ci",
    "verify-azure-blueprint",
    "validate-iac",
    "portfolio-check",
]

README_REQUIRED_SECTIONS = [
    "Business Problem",
    "Architecture Summary",
    "Completed Milestones",
    "Repository Structure",
    "Quickstart",
    "Full Local Demo",
    "Quality Gates",
    "Security And Governance",
    "Limitations",
    "Interview Talking Points",
    "What This Demonstrates",
]

FORBIDDEN_PHRASES = [
    "production " + "deployed",
    "live " + "azure",
    "real-time " + "grid control",
    "guaranteed " + "outage prediction",
    "certified " + "reliability reporting",
    "power bi dashboard " + "deployed",
]

SECRET_PATTERNS = [
    re.compile(
        r"(?i)(client_secret|secret_value|access_key|api_key|password)\s*[:=]\s*['\"][^'\"\n]{8,}"
    ),
    re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
MERMAID_STARTS = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
    "journey",
    "gantt",
)


def main() -> int:
    failures: list[str] = []
    failures.extend(_missing_paths(REQUIRED_DOCS + REQUIRED_DIAGRAMS + REQUIRED_CONFIGS))
    failures.extend(_missing_milestone_docs())
    failures.extend(_missing_make_targets())
    failures.extend(_readme_section_failures())
    failures.extend(_portfolio_content_failures())
    failures.extend(_azure_blueprint_language_failures())
    failures.extend(_forbidden_phrase_failures())
    failures.extend(_runtime_artifact_failures())
    failures.extend(_secret_failures())
    failures.extend(_mermaid_failures())
    failures.extend(_markdown_link_failures())

    if failures:
        print("Repository polish verification failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Repository polish verification passed.")
    return 0


def _missing_paths(paths: list[str]) -> list[str]:
    return [f"Missing required path: {path}" for path in paths if not (ROOT / path).exists()]


def _missing_milestone_docs() -> list[str]:
    return [
        f"Missing milestone document: docs/milestones/milestone-{number}.md"
        for number in range(1, 13)
        if not (ROOT / f"docs/milestones/milestone-{number}.md").exists()
    ]


def _missing_make_targets() -> list[str]:
    makefile = _read("Makefile")
    failures = []
    for target in REQUIRED_MAKE_TARGETS:
        if not re.search(rf"^{re.escape(target)}:", makefile, flags=re.MULTILINE):
            failures.append(f"Missing Makefile target: {target}")
    return failures


def _readme_section_failures() -> list[str]:
    readme = _read("README.md")
    failures = []
    for section in README_REQUIRED_SECTIONS:
        if f"## {section}" not in readme:
            failures.append(f"README missing section: {section}")
    required_terms = [
        "synthetic",
        "local-first",
        "Azure blueprint",
        "No Azure resources are deployed",
        "No Power BI workspace is deployed",
    ]
    for term in required_terms:
        if term not in readme:
            failures.append(f"README missing required wording: {term}")
    return failures


def _portfolio_content_failures() -> list[str]:
    combined = "\n".join(_read(path) for path in REQUIRED_DOCS if path.startswith("docs/portfolio"))
    required = [
        "critical infrastructure",
        "decision support",
        "human review",
        "synthetic",
        "Azure",
        "Power BI",
    ]
    return [f"Portfolio docs missing concept: {term}" for term in required if term not in combined]


def _azure_blueprint_language_failures() -> list[str]:
    azure_text = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in ("docs/azure", "infra")
        for path in sorted((ROOT / folder).rglob("*"))
        if path.is_file()
    ).lower()
    required = ["blueprint", "not deployed", "no azure resources are deployed"]
    return [
        f"Azure/infra docs missing clear boundary phrase: {phrase}"
        for phrase in required
        if phrase not in azure_text
    ]


def _forbidden_phrase_failures() -> list[str]:
    failures = []
    for path in _text_files():
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                failures.append(
                    f"Forbidden overclaim phrase '{phrase}' found in {path.relative_to(ROOT)}"
                )
    return failures


def _runtime_artifact_failures() -> list[str]:
    failures = []
    tracked = subprocess.run(
        ["git", "ls-files", "data", "outputs", "reports"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        return ["Unable to inspect tracked runtime paths with git ls-files"]
    for relative in tracked.stdout.splitlines():
        if Path(relative).name != ".gitkeep":
            failures.append(f"Generated runtime artifact is tracked: {relative}")
    return failures


def _secret_failures() -> list[str]:
    failures = []
    for path in _text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"Obvious secret-shaped value found in {path.relative_to(ROOT)}")
    return failures


def _mermaid_failures() -> list[str]:
    failures = []
    for path in sorted((ROOT / "diagrams").rglob("*.mmd")):
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("%%")
        ]
        if not lines:
            failures.append(f"Empty Mermaid diagram: {path.relative_to(ROOT)}")
        elif not lines[0].startswith(MERMAID_STARTS):
            failures.append(
                f"Unexpected Mermaid diagram start in {path.relative_to(ROOT)}: {lines[0]}"
            )
    return failures


def _markdown_link_failures() -> list[str]:
    failures = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for raw_link in MARKDOWN_LINK.findall(text):
            link = raw_link.strip()
            if _is_external_or_anchor(link):
                continue
            target = link.split("#", 1)[0]
            if not target:
                continue
            target_path = (path.parent / target).resolve()
            if ROOT not in target_path.parents and target_path != ROOT:
                failures.append(
                    f"Markdown link escapes repository in {path.relative_to(ROOT)}: {link}"
                )
            elif not target_path.exists():
                failures.append(f"Broken Markdown link in {path.relative_to(ROOT)}: {link}")
    return failures


def _is_external_or_anchor(link: str) -> bool:
    return (
        link.startswith("#")
        or "://" in link
        or link.startswith("mailto:")
        or link.startswith("tel:")
    )


def _text_files() -> list[Path]:
    suffixes = {
        ".md",
        ".py",
        ".yaml",
        ".yml",
        ".toml",
        ".txt",
        ".sh",
        ".bicep",
        ".bicepparam",
        ".mmd",
    }
    skipped_parts = {".git", ".venv", "venv", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and not skipped_parts.intersection(path.relative_to(ROOT).parts)
    ]


def _markdown_files() -> list[Path]:
    return [path for path in ROOT.rglob("*.md") if ".git" not in path.relative_to(ROOT).parts]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
