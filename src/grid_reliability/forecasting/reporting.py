"""Deterministic Markdown reports for forecasting runs."""

from __future__ import annotations

from pathlib import Path

from grid_reliability.forecasting.models import MetricResult, ModelSelection, SplitBoundaries


def write_reports(
    *,
    report_root: Path,
    run_id: str,
    target_name: str,
    target_unit: str,
    aggregation_level: str,
    boundaries: SplitBoundaries,
    metrics: list[MetricResult],
    selection: ModelSelection,
    feature_names: list[str],
    weather_enabled: bool,
) -> dict[str, Path]:
    run_root = report_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "forecast_evaluation": run_root / "forecast_evaluation.md",
        "model_card": run_root / "model_card.md",
        "executive_summary": run_root / "executive_load_forecast_summary.md",
    }
    paths["forecast_evaluation"].write_text(
        _evaluation_report(
            target_name,
            target_unit,
            aggregation_level,
            boundaries,
            metrics,
            selection,
            weather_enabled,
        ),
        encoding="utf-8",
    )
    paths["model_card"].write_text(
        _model_card(
            target_name,
            target_unit,
            aggregation_level,
            selection,
            feature_names,
            weather_enabled,
        ),
        encoding="utf-8",
    )
    paths["executive_summary"].write_text(
        _executive_summary(target_name, target_unit, selection, metrics),
        encoding="utf-8",
    )
    return paths


def _evaluation_report(
    target_name: str,
    target_unit: str,
    aggregation_level: str,
    boundaries: SplitBoundaries,
    metrics: list[MetricResult],
    selection: ModelSelection,
    weather_enabled: bool,
) -> str:
    lines = [
        "# Forecast Evaluation",
        "",
        "## Problem Definition",
        "",
        f"- Target: `{target_name}` in `{target_unit}`",
        f"- Aggregation grain: `{aggregation_level}`",
        "- Horizons: configured short-term interval horizons",
        "- Weather assumption: "
        + (
            "observed weather at forecast origin is available for evaluation"
            if weather_enabled
            else "weather features disabled"
        ),
        "",
        "## Split Design",
        "",
        f"- Training: {boundaries.training_start} to {boundaries.training_end}",
        f"- Validation: {boundaries.validation_start} to {boundaries.validation_end}",
        f"- Test: {boundaries.test_start} to {boundaries.test_end}",
        "",
        "## Model Selection",
        "",
        f"- Selected model: `{selection.selected_model}`",
        f"- Selection metric: `{selection.selected_metric}`",
        f"- Beats persistence baseline: `{selection.beats_baseline}`",
        "",
        "## Metrics",
        "",
        "| Model | Split | Entity | Horizon | MAE | RMSE | WAPE | Bias | Rows |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for metric in metrics:
        lines.append(
            f"| {metric.model_name} | {metric.split} | {metric.entity_id} | "
            f"{metric.horizon} | {metric.mae:.6f} | {metric.rmse:.6f} | "
            f"{_fmt(metric.wape)} | {metric.bias:.6f} | {metric.row_count} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Forecasting uses fictional synthetic validated interim data only.",
            "- Day-ahead forecasts are not promised for short CI-profile history.",
            "- Prediction intervals are empirical residual intervals, not calibrated guarantees.",
            "- No Azure Machine Learning resources or endpoints are deployed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _model_card(
    target_name: str,
    target_unit: str,
    aggregation_level: str,
    selection: ModelSelection,
    feature_names: list[str],
    weather_enabled: bool,
) -> str:
    return (
        "# Forecasting Model Card\n\n"
        "## Intended Use\n\n"
        "Short-term local forecasting experiments on fictional synthetic grid telemetry.\n\n"
        "## Out Of Scope\n\n"
        "Real-grid operational decisions, outage prediction, asset-health scoring, KPI reporting, "
        "and deployed online inference.\n\n"
        "## Target And Units\n\n"
        f"- Target: `{target_name}`\n"
        f"- Unit: `{target_unit}`\n"
        f"- Entity grain: `{aggregation_level}`\n\n"
        "## Algorithm\n\n"
        f"Selected model: `{selection.selected_model}`. Baselines are always evaluated.\n\n"
        "## Features\n\n" + "\n".join(f"- `{name}`" for name in feature_names) + "\n\n"
        "## Assumptions\n\n"
        f"- Weather features enabled: `{weather_enabled}`.\n"
        "- Weather values are observed at forecast origin for local evaluation; production use "
        "would require weather forecasts.\n"
        "- Inputs are synthetic and validated by the local ingestion layer.\n\n"
        "## Monitoring And Retraining\n\n"
        "Track forecast error, interval coverage, missing intervals, and entity-level drift before "
        "any future production design.\n\n"
        "## Responsible Use\n\n"
        "This model is a local demonstration artifact and is not suitable for real critical "
        "infrastructure operations.\n"
    )


def _executive_summary(
    target_name: str,
    target_unit: str,
    selection: ModelSelection,
    metrics: list[MetricResult],
) -> str:
    test_metrics = [
        metric
        for metric in metrics
        if metric.model_name == selection.selected_model and metric.split == "test"
    ]
    avg_mae = (
        sum(metric.mae for metric in test_metrics) / len(test_metrics) if test_metrics else 0.0
    )
    return (
        "# Executive Load Forecast Summary\n\n"
        f"- Selected model: `{selection.selected_model}`\n"
        f"- Forecast target: `{target_name}` in `{target_unit}`\n"
        f"- Average selected-model test MAE: `{avg_mae:.6f}`\n"
        "- Expected demand direction is available in the forecast CSV by comparing "
        "forecast origins and predicted values.\n"
        "- Higher uncertainty is indicated by wider prediction intervals.\n"
        "- Results are based on fictional synthetic data and do not represent a live grid.\n"
        "- No business savings, operational deployment, or Power BI dashboard is claimed.\n"
    )


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"
