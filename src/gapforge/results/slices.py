"""Slice analysis over prediction artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ErrorSlice, ExperimentResultArtifact, MetricResult, Provenance
from gapforge.state import utc_now_iso


class SliceAnalysisBuilder:
    """Build simple classification/detection slices from prediction artifacts."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def analyze_slice(self, execution_id: str, slice_spec: str) -> ErrorSlice:
        workspace, execution = ExperimentRunner(self.config).find_execution(execution_id)
        predictions = load_predictions_for_execution(self.workspace_manager, workspace.id, execution_id)
        key, value = parse_slice_spec(slice_spec)
        filtered = [item for item in predictions if str(item.get(key, "")) == value]
        error_slice = build_error_slice(
            workspace_id=workspace.id,
            execution_id=execution_id,
            slice_name=slice_spec,
            filter_description=f"{key} equals {value}",
            predictions=filtered,
        )
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / f"slice_analysis_{execution_id}_{_safe_id(slice_spec)}.json").write_text(
            json.dumps(_to_plain_slice(error_slice), indent=2) + "\n",
            encoding="utf-8",
        )
        (reports / f"slice_analysis_{execution_id}_{_safe_id(slice_spec)}.md").write_text(
            render_error_slice_markdown(error_slice), encoding="utf-8"
        )
        return error_slice


def load_predictions_for_execution(manager: ExperimentWorkspaceManager, workspace_id: str, execution_id: str) -> list[dict[str, object]]:
    artifacts = [
        artifact
        for artifact in manager.list_result_artifacts(workspace_id)
        if artifact.execution_id == execution_id and artifact.artifact_type == "predictions"
    ]
    predictions: list[dict[str, object]] = []
    for artifact in artifacts:
        predictions.extend(_load_prediction_artifact(artifact))
    return predictions


def build_error_slice(
    *,
    workspace_id: str,
    execution_id: str,
    slice_name: str,
    filter_description: str,
    predictions: list[dict[str, object]],
) -> ErrorSlice:
    counts = error_counts(predictions)
    metrics = [
        _metric(execution_id, slice_name, "false_positive_count", counts["false_positive"]),
        _metric(execution_id, slice_name, "false_negative_count", counts["false_negative"]),
        _metric(execution_id, slice_name, "true_positive_count", counts["true_positive"]),
        _metric(execution_id, slice_name, "true_negative_count", counts["true_negative"]),
    ]
    return ErrorSlice(
        id=f"error-slice-{_stable_id(execution_id, slice_name)}",
        workspace_id=workspace_id,
        execution_id=execution_id,
        slice_name=slice_name,
        filter_description=filter_description,
        sample_count=len(predictions),
        metric_results=metrics,
        examples=error_examples(predictions),
        provenance=Provenance(
            created_by_skill="slice-analysis",
            source_ids=[workspace_id, execution_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Computed a slice from prediction artifacts only; examples are copied from artifacts.",
        ),
    )


def error_counts(predictions: list[dict[str, object]]) -> dict[str, int]:
    counts = {"false_positive": 0, "false_negative": 0, "true_positive": 0, "true_negative": 0, "other": 0}
    for item in predictions:
        label = _binary_value(item.get("label", item.get("y_true")))
        prediction = _binary_value(item.get("prediction", item.get("y_pred")))
        if label is None or prediction is None:
            counts["other"] += 1
        elif label == 0 and prediction == 1:
            counts["false_positive"] += 1
        elif label == 1 and prediction == 0:
            counts["false_negative"] += 1
        elif label == 1 and prediction == 1:
            counts["true_positive"] += 1
        elif label == 0 and prediction == 0:
            counts["true_negative"] += 1
    return counts


def error_examples(predictions: list[dict[str, object]], *, limit: int = 5) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    for item in predictions:
        label = _binary_value(item.get("label", item.get("y_true")))
        prediction = _binary_value(item.get("prediction", item.get("y_pred")))
        if label is not None and prediction is not None and label != prediction:
            examples.append(dict(item))
        if len(examples) >= limit:
            break
    return examples


def parse_slice_spec(slice_spec: str) -> tuple[str, str]:
    if "=" not in slice_spec:
        raise ValueError(f"Invalid slice spec `{slice_spec}`; expected field=value.")
    key, value = slice_spec.split("=", 1)
    if not key.strip():
        raise ValueError("Slice field cannot be empty.")
    return key.strip(), value.strip()


def render_error_slice_markdown(error_slice: ErrorSlice) -> str:
    lines = [
        f"# Error Slice `{error_slice.id}`",
        "",
        f"- Workspace ID: `{error_slice.workspace_id}`",
        f"- Execution ID: `{error_slice.execution_id}`",
        f"- Slice: `{error_slice.slice_name}`",
        f"- Filter: {error_slice.filter_description or 'none'}",
        f"- Sample count: {error_slice.sample_count}",
        "",
        "## Metrics",
        "",
    ]
    lines.extend([f"- `{metric.metric_id}`: {metric.value:g}" for metric in error_slice.metric_results] or ["- none"])
    lines.extend(["", "## Artifact Examples", ""])
    lines.extend([f"- `{example.get('id', 'unknown')}` {example}" for example in error_slice.examples] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _load_prediction_artifact(artifact: ExperimentResultArtifact) -> list[dict[str, object]]:
    payload = json.loads(Path(artifact.path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("predictions"), list):
        return [dict(item) for item in payload["predictions"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    return []


def _metric(execution_id: str, slice_name: str, metric_id: str, value: int) -> MetricResult:
    return MetricResult(
        id=f"metric-result-{_stable_id(execution_id, slice_name, metric_id)}",
        execution_id=execution_id,
        metric_id=metric_id,
        value=float(value),
        sample_size=value,
        provenance=Provenance(
            created_by_skill="slice-analysis",
            source_ids=[execution_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Computed a simple error-count metric from prediction artifacts.",
        ),
    )


def _binary_value(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float) and value in {0, 1}:
        return int(value)
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return int(value.strip())
    return None


def _to_plain_slice(error_slice: ErrorSlice) -> dict[str, object]:
    from gapforge.models import to_plain

    return to_plain(error_slice)


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-") or "slice"


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
