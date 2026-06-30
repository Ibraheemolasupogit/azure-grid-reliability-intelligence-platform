"""Deterministic Markdown reports for outage prediction."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from grid_reliability.outage_prediction.config import OutagePredictionConfig
from grid_reliability.outage_prediction.models import (
    ClassificationMetric,
    ModelSelection,
    PredictionResult,
    ReasonDescription,
)


def write_reports(
    report_root: Path,
    run_id: str,
    config: OutagePredictionConfig,
    predictions: list[PredictionResult],
    metrics: list[ClassificationMetric],
    selection: ModelSelection,
) -> dict[str, Path]:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "evaluation": run_root / "outage_prediction_evaluation.md",
        "risk_report": run_root / "outage_risk_report.md",
        "model_card": run_root / "model_card.md",
        "executive_summary": run_root / "executive_outage_risk_summary.md",
    }
    paths["evaluation"].write_text(_evaluation(config, metrics, selection), encoding="utf-8")
    paths["risk_report"].write_text(_risk_report(predictions), encoding="utf-8")
    paths["model_card"].write_text(_model_card(config, selection), encoding="utf-8")
    paths["executive_summary"].write_text(_summary(predictions, selection), encoding="utf-8")
    return paths


def _evaluation(
    config: OutagePredictionConfig,
    metrics: list[ClassificationMetric],
    selection: ModelSelection,
) -> str:
    lines = [
        "# Outage Prediction Evaluation",
        "",
        "## Prediction Problem",
        "",
        f"- Entity grain: `{config.entity_type.value}`",
        "- Label: unplanned outage starts strictly after observation time and on or before "
        "the horizon boundary.",
        f"- Horizon intervals: `{config.prediction_horizon_intervals}`",
        f"- Lookback intervals: `{config.feature_lookback_intervals}`",
        f"- Purge intervals: `{config.prediction_horizon_intervals}`",
        "",
        "## Selected Model",
        "",
        f"- Model: `{selection.selected_model}`",
        f"- Threshold: `{selection.selected_threshold}`",
        f"- Selection metric: `{selection.selection_metric}`",
        "",
        "## Metrics",
        "",
    ]
    for metric in metrics:
        lines.append(
            f"- `{metric.model_name}` `{metric.split}` `{metric.grid_region}`: "
            f"rows `{metric.row_count}`, positives `{metric.positive_count}`, "
            f"precision `{metric.precision}`, recall `{metric.recall}`, f1 `{metric.f1}`"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Metrics are calculated on fictional synthetic data.",
            "- CI data is intentionally small; unavailable AUC values are recorded as null.",
            "- Scores are decision-support risk estimates, not certified protection logic.",
        ]
    )
    return "\n".join(lines) + "\n"


def _risk_report(predictions: list[PredictionResult]) -> str:
    selected = (
        [row for row in predictions if row.model_name == predictions[0].model_name]
        if predictions
        else []
    )
    bands = Counter(row.risk_band.value for row in selected)
    reasons = Counter(code for row in selected for code in row.reason_codes)
    highest = sorted(
        selected, key=lambda row: (-row.risk_score, row.row.labelled.panel.entity.entity_id)
    )[:10]
    lines = ["# Outage Risk Report", "", "## Risk-Band Distribution", ""]
    for band, count in sorted(bands.items()):
        lines.append(f"- `{band}`: {count}")
    lines.extend(["", "## Highest-Risk Entity-Times", ""])
    for row in highest:
        lines.append(
            f"- `{row.row.labelled.panel.entity.entity_id}` "
            f"`{row.row.labelled.panel.observation_timestamp.isoformat()}`: "
            f"{row.risk_score:.3f} `{row.risk_band.value}`"
        )
    lines.extend(["", "## Dominant Reasons", ""])
    for code, count in reasons.most_common(10):
        lines.append(f"- `{code}`: {count}")
    return "\n".join(lines) + "\n"


def _model_card(config: OutagePredictionConfig, selection: ModelSelection) -> str:
    lines = [
        "# Outage Prediction Model Card",
        "",
        "## Intended Use",
        "",
        "Synthetic local decision support for reviewing unplanned outage-risk signals.",
        "",
        "## Prohibited Use",
        "",
        "Do not use as protection logic, restoration automation, maintenance scheduling "
        "optimisation, or evidence of Azure deployment.",
        "",
        "## Algorithm",
        "",
        f"Selected model: `{selection.selected_model}`. Candidate models include transparent "
        "baselines and deterministic logistic regression.",
        "",
        "## Class Imbalance",
        "",
        f"Positive class weight: `{config.positive_class_weight}`.",
        "",
        "## Calibration",
        "",
        f"Calibration method: `{config.calibration_method}`. Raw scores are interpreted "
        "cautiously when validation data is small.",
        "",
        "## Reason Codes",
        "",
    ]
    for code, description in ReasonDescription.items():
        lines.append(f"- `{code}`: {description}")
    lines.extend(["", "All data is fictional synthetic data. No Azure resources are deployed."])
    return "\n".join(lines) + "\n"


def _summary(predictions: list[PredictionResult], selection: ModelSelection) -> str:
    selected = [row for row in predictions if row.model_name == selection.selected_model]
    high = sum(1 for row in selected if row.risk_band.value in {"HIGH", "CRITICAL"})
    return (
        "# Executive Outage Risk Summary\n\n"
        f"- Selected model: `{selection.selected_model}`\n"
        f"- Scored rows: `{len(selected)}`\n"
        f"- High or critical risk rows: `{high}`\n"
        "- Risk scores are based on synthetic data and carry material uncertainty.\n"
        "- No operational savings, certified engineering decision, dashboard, or deployment "
        "is claimed.\n"
    )
