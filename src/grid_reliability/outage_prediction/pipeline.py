"""Outage prediction pipeline and CLI."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grid_reliability.common.exceptions import ConfigurationError
from grid_reliability.common.metadata import __version__
from grid_reliability.common.paths import resolve_project_root
from grid_reliability.common.settings import load_settings
from grid_reliability.data_generation.writers import sha256_file
from grid_reliability.outage_prediction.baselines import (
    OperationalWarningHeuristic,
    PrevalenceBaseline,
    RecentOutageHeuristic,
)
from grid_reliability.outage_prediction.calibration import calibration_metadata
from grid_reliability.outage_prediction.classification import LogisticRegressionModel
from grid_reliability.outage_prediction.config import (
    OutagePredictionConfig,
    load_outage_prediction_config,
)
from grid_reliability.outage_prediction.data import load_inputs
from grid_reliability.outage_prediction.explainability import classify_risk, reason_codes
from grid_reliability.outage_prediction.features import build_feature_rows, feature_names
from grid_reliability.outage_prediction.imbalance import class_summary
from grid_reliability.outage_prediction.labels import apply_labels
from grid_reliability.outage_prediction.metrics import evaluate_predictions
from grid_reliability.outage_prediction.models import (
    ClassificationMetric,
    FeatureRow,
    ModelSelection,
    OutagePredictionError,
    PredictionResult,
    SplitRows,
)
from grid_reliability.outage_prediction.panel import build_panel
from grid_reliability.outage_prediction.persistence import write_outputs
from grid_reliability.outage_prediction.reporting import write_reports
from grid_reliability.outage_prediction.selection import select_model
from grid_reliability.outage_prediction.splitting import chronological_split


@dataclass(frozen=True)
class OutagePredictionResult:
    run_id: str
    selected_model: str
    prediction_path: Path
    metrics_path: Path
    manifest_path: Path
    model_metadata_path: Path
    report_paths: dict[str, Path]
    metrics: list[ClassificationMetric]
    prediction_row_count: int


def build_run_id(config: OutagePredictionConfig, provided: str | None = None) -> str:
    if provided:
        return provided
    if config.run_id_strategy == "deterministic":
        return "outage-prediction-ci"
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def run_outage_prediction(
    config: OutagePredictionConfig,
    *,
    project_root: Path | None = None,
    run_id: str | None = None,
) -> OutagePredictionResult:
    root = (project_root or resolve_project_root()).resolve()
    settings = load_settings(project_root=root)
    effective_run_id = build_run_id(config, run_id)
    datasets, input_checksums = load_inputs(root / config.interim_root, config)
    panel_rows = build_panel(datasets, config)
    labelled_rows = apply_labels(panel_rows, datasets["outage_history"], config)
    feature_rows = build_feature_rows(labelled_rows, datasets, config)
    _validate_overall_classes(feature_rows, config)
    splits = chronological_split(feature_rows, config)
    names = feature_names(feature_rows)
    models, failed_models = _train_models(config, splits.train, names)
    predictions = _score_models(models, splits, names, effective_run_id, config)
    metrics = evaluate_predictions(
        predictions,
        threshold=config.classification_threshold,
        horizon=config.prediction_horizon_intervals,
    )
    selection = select_model(
        metrics,
        predictions,
        candidate_models=config.candidate_models,
        selection_metric=config.selection_metric,
        configured_threshold=config.classification_threshold,
        failed_models=failed_models,
    )
    output_paths = write_outputs(
        root / config.output_root,
        root / config.model_root,
        effective_run_id,
        predictions,
        metrics,
        selection,
        _payloads(
            settings.project_name,
            root,
            effective_run_id,
            config,
            splits,
            feature_rows,
            names,
            input_checksums,
            metrics,
            selection,
            predictions,
            failed_models,
        ),
    )
    report_paths = write_reports(
        root / config.report_root,
        effective_run_id,
        config,
        [row for row in predictions if row.model_name == selection.selected_model],
        metrics,
        selection,
    )
    return OutagePredictionResult(
        run_id=effective_run_id,
        selected_model=selection.selected_model,
        prediction_path=output_paths["predictions"],
        metrics_path=output_paths["metrics"],
        manifest_path=output_paths["manifest"],
        model_metadata_path=output_paths["model_metadata"],
        report_paths=report_paths,
        metrics=metrics,
        prediction_row_count=len(predictions),
    )


def _train_models(
    config: OutagePredictionConfig,
    train_rows: list[FeatureRow],
    names: list[str],
) -> tuple[dict[str, Any], dict[str, str]]:
    models: dict[str, Any] = {}
    failed: dict[str, str] = {}
    for model_name in config.candidate_models:
        model: Any
        if model_name == "prevalence":
            model = PrevalenceBaseline()
        elif model_name == "recent_outage_heuristic":
            model = RecentOutageHeuristic()
        elif model_name == "operational_warning_heuristic":
            model = OperationalWarningHeuristic()
        elif model_name == "logistic_regression":
            model = LogisticRegressionModel(positive_class_weight=config.positive_class_weight)
        try:
            model.fit(train_rows, names)
            models[model_name] = model
        except (ValueError, ArithmeticError) as exc:
            failed[model_name] = str(exc)
    return models, failed


def _score_models(
    models: dict[str, Any],
    splits: SplitRows,
    names: list[str],
    run_id: str,
    config: OutagePredictionConfig,
) -> list[PredictionResult]:
    predictions: list[PredictionResult] = []
    split_rows = {"train": splits.train, "validation": splits.validation, "test": splits.test}
    for model_name, model in sorted(models.items()):
        for split, rows in split_rows.items():
            for row, score in zip(rows, model.predict_proba(rows, names), strict=True):
                bounded = min(1.0, max(0.0, float(score)))
                predictions.append(
                    PredictionResult(
                        run_id=run_id,
                        row=row,
                        model_name=model_name,
                        risk_score=round(bounded, 6),
                        risk_band=classify_risk(bounded, row, config),
                        predicted_outage_flag=bounded >= config.classification_threshold,
                        classification_threshold=config.classification_threshold,
                        data_split=split,
                        reason_codes=reason_codes(row, config),
                    )
                )
    return sorted(
        predictions,
        key=lambda item: (
            item.model_name,
            item.data_split,
            item.row.labelled.panel.observation_timestamp,
            item.row.labelled.panel.entity.entity_id,
        ),
    )


def _payloads(
    project_name: str,
    root: Path,
    run_id: str,
    config: OutagePredictionConfig,
    splits: SplitRows,
    rows: list[FeatureRow],
    names: list[str],
    input_checksums: dict[str, str],
    metrics: list[ClassificationMetric],
    selection: ModelSelection,
    predictions: list[PredictionResult],
    failed_models: dict[str, str],
) -> dict[str, dict[str, Any]]:
    split_counts = {
        "train": class_summary(splits.train),
        "validation": class_summary(splits.validation),
        "test": class_summary(splits.test),
        "overall": class_summary(rows),
    }
    selected_predictions = [
        row for row in predictions if row.model_name == selection.selected_model
    ]
    base = {
        "project": project_name,
        "run_id": run_id,
        "component_version": __version__,
        "schema_version": config.schema_version,
        "entity_type": config.entity_type.value,
        "observation_frequency_minutes": config.observation_frequency_minutes,
        "prediction_horizon_intervals": config.prediction_horizon_intervals,
        "feature_lookback_intervals": config.feature_lookback_intervals,
        "classification_threshold": selection.selected_threshold,
        "selected_model": selection.selected_model,
        "selected_threshold": selection.selected_threshold,
        "class_counts": split_counts,
        "synthetic_data_declaration": "Outage prediction uses fictional synthetic data only.",
        "limitations": [
            "Not certified engineering protection logic.",
            "No reliability KPIs, Azure deployment, endpoint, dashboard, "
            "or operational automation.",
            "CI profile is intentionally small; calibration is raw-score interpretation only.",
        ],
    }
    return {
        "metrics": {
            **base,
            "metrics": [asdict(metric) for metric in metrics],
            "calibration": calibration_metadata(
                config.calibration_method,
                [row for row in selected_predictions if row.data_split == "validation"],
            ),
            "risk_band_counts": _counts(row.risk_band.value for row in selected_predictions),
            "reason_code_counts": _counts(
                code for row in selected_predictions for code in row.reason_codes
            ),
            "failed_models": failed_models,
        },
        "model_metadata": {
            **base,
            "model_parameters": {"positive_class_weight": config.positive_class_weight},
            "training_period": _period(splits.train),
            "validation_period": _period(splits.validation),
            "test_period": _period(splits.test),
            "input_checksums": input_checksums,
            "package_versions": {"grid_reliability": __version__},
            "intended_use": "Synthetic local outage-risk decision support.",
        },
        "feature_schema": {
            "features": names,
            "feature_count": len(names),
            "availability": "All feature windows end at or before the observation timestamp.",
            "prohibited_fields": [
                "future outage flags",
                "restoration fields from future outages",
                "future weather",
                "future telemetry",
                "future maintenance",
                "ingestion metadata",
                "label source outage id",
            ],
        },
        "preprocessing_metadata": {
            "categorical_encoding": (
                "No model categorical encoding; entity context retained for reporting."
            ),
            "missing_value_handling": "Missing aggregates use explicit zero or missing indicators.",
            "feature_order": names,
            "class_weighting": {"positive_class_weight": config.positive_class_weight},
            "calibration_method": config.calibration_method,
        },
        "manifest": {
            **base,
            "repository_revision": _repo_revision(root),
            "configuration_checksum": sha256_file(
                root
                / "configs"
                / f"outage_prediction{'_ci' if config.profile == 'ci' else ''}.yaml"
            )
            if (
                root
                / "configs"
                / f"outage_prediction{'_ci' if config.profile == 'ci' else ''}.yaml"
            ).exists()
            else None,
            "input_files": {name: f"{name}.jsonl" for name in sorted(input_checksums)},
            "input_checksums": input_checksums,
            "label_definition": (
                "1 when an unplanned outage starts after observation time and on or before "
                "the horizon boundary."
            ),
            "split_boundaries": asdict(splits.boundaries),
            "purge_intervals": config.prediction_horizon_intervals,
            "candidate_models": list(config.candidate_models),
            "row_counts": {
                "panel_labelled_feature_rows": len(rows),
                "prediction_rows": len(predictions),
            },
            "failed_models": failed_models,
        },
    }


def _validate_overall_classes(rows: list[FeatureRow], config: OutagePredictionConfig) -> None:
    positives = sum(row.labelled.label for row in rows)
    negatives = len(rows) - positives
    if positives < config.minimum_positive_examples:
        raise OutagePredictionError("Insufficient positive outage labels.")
    if negatives < config.minimum_negative_examples:
        raise OutagePredictionError("Insufficient negative outage labels.")


def _period(rows: list[FeatureRow]) -> dict[str, str | None]:
    if not rows:
        return {"start": None, "end": None}
    timestamps = [row.labelled.panel.observation_timestamp for row in rows]
    return {
        "start": min(timestamps).isoformat().replace("+00:00", "Z"),
        "end": max(timestamps).isoformat().replace("+00:00", "Z"),
    }


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _repo_revision(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local outage prediction.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--interim-root")
    parser.add_argument("--output-root")
    parser.add_argument("--report-root")
    parser.add_argument("--run-id")
    parser.add_argument("--entity-type")
    parser.add_argument("--entity-id")
    parser.add_argument("--prediction-horizon", type=int)
    parser.add_argument("--classification-threshold", type=float)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args(argv)
    try:
        config = load_outage_prediction_config(
            args.config,
            interim_root=args.interim_root,
            output_root=args.output_root,
            report_root=args.report_root,
            entity_type=args.entity_type,
            entity_id=args.entity_id,
            prediction_horizon=args.prediction_horizon,
            classification_threshold=args.classification_threshold,
            seed=args.seed,
        )
        result = run_outage_prediction(config, run_id=args.run_id)
    except ConfigurationError as exc:
        parser.error(str(exc))
        return 2
    except OutagePredictionError as exc:
        print({"status": "failed", "error": str(exc)})
        return 3
    except Exception as exc:
        print({"status": "failed", "error": str(exc)})
        return 1
    print(
        "Outage prediction run "
        f"{result.run_id}: selected_model={result.selected_model}; "
        f"predictions={result.prediction_row_count}; "
        f"scores={result.prediction_path}; report={result.report_paths['evaluation']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
