"""Parse experiment result artifacts into auditable empirical claims."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import (
    EmpiricalClaim,
    ExperimentExecutionRecord,
    ExperimentResultArtifact,
    ExperimentRunManifest,
    ExperimentWorkspace,
    MetricRecord,
    MetricResult,
    Provenance,
    ResultSummary,
    from_dict,
    to_plain,
)
from gapforge.results.claims import claims_from_metric_results
from gapforge.results.tables import render_empirical_claims_table, render_result_summary_markdown
from gapforge.state import slugify, utc_now_iso


class ResultParser:
    """Parse result artifacts for one experiment execution."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.metric_registry = MetricRegistry(config)

    def parse_execution(self, execution_id: str) -> ResultSummary:
        workspace, execution = ExperimentRunner(self.config).find_execution(execution_id)
        manifest = _require_manifest(self.workspace_manager.list_manifests(workspace.id), execution.manifest_id)
        artifacts = [
            artifact
            for artifact in self.workspace_manager.list_result_artifacts(workspace.id)
            if artifact.execution_id == execution.id and artifact.id in execution.result_artifact_ids
        ]
        metrics = self.metric_registry.list_metrics(workspace.id)
        metric_results: list[MetricResult] = []
        failures: list[str] = []
        limitations: list[str] = []
        if execution.status == "failed":
            failures.append(execution.failure_reason or "Execution failed without a recorded reason.")
        for artifact in artifacts:
            if artifact.artifact_type != "metrics_json":
                continue
            parsed, parse_limitations = _parse_metrics_artifact(
                artifact=artifact,
                execution=execution,
                manifest=manifest,
                metrics=metrics,
            )
            metric_results.extend(parsed)
            limitations.extend(parse_limitations)
        if not artifacts:
            limitations.append("No result artifact metadata is linked to this execution; no empirical claim was created.")
        elif not metric_results:
            limitations.append("No parseable metrics_json artifact was found; no empirical claim was created.")
        claims = claims_from_metric_results(execution=execution, metric_results=metric_results, limitations=_unique(limitations))
        summary = ResultSummary(
            execution_id=execution.id,
            metric_results=metric_results,
            empirical_claims=claims,
            failures=_unique(failures),
            limitations=_unique(limitations),
            provenance=Provenance(
                created_by_skill="result-parser",
                source_ids=[execution.id, *[artifact.id for artifact in artifacts]],
                timestamp=utc_now_iso(),
                reasoning_summary="Parsed artifact-backed metric results and wrote empirical claims without fabricating missing outputs.",
            ),
        )
        self._write_summary(workspace, summary)
        self._write_empirical_claim_ledger(workspace, claims)
        return summary

    def load_or_parse_summary(self, execution_id: str) -> ResultSummary:
        workspace, _execution = ExperimentRunner(self.config).find_execution(execution_id)
        path = Path(workspace.root_dir) / "reports" / f"result_summary_{execution_id}.json"
        if path.exists():
            return from_dict(ResultSummary, json.loads(path.read_text(encoding="utf-8")))
        return self.parse_execution(execution_id)

    def empirical_claims_for_workspace(self, workspace_id: str) -> list[EmpiricalClaim]:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        path = Path(workspace.root_dir) / "reports" / "empirical_claims.json"
        if not path.exists():
            return []
        return [from_dict(EmpiricalClaim, item) for item in json.loads(path.read_text(encoding="utf-8"))]

    def render_empirical_claims(self, workspace_id: str) -> str:
        claims = self.empirical_claims_for_workspace(workspace_id)
        return "# Empirical Claims\n\n" + render_empirical_claims_table(claims) + "\n"

    def _write_summary(self, workspace: ExperimentWorkspace, summary: ResultSummary) -> None:
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / f"result_summary_{summary.execution_id}.json").write_text(
            json.dumps(to_plain(summary), indent=2) + "\n",
            encoding="utf-8",
        )
        (reports / f"result_summary_{summary.execution_id}.md").write_text(render_result_summary_markdown(summary), encoding="utf-8")

    def _write_empirical_claim_ledger(self, workspace: ExperimentWorkspace, claims: list[EmpiricalClaim]) -> None:
        reports = Path(workspace.root_dir) / "reports"
        path = reports / "empirical_claims.json"
        existing = [from_dict(EmpiricalClaim, item) for item in json.loads(path.read_text(encoding="utf-8"))] if path.exists() else []
        merged = _merge_claims(existing, claims)
        path.write_text(json.dumps(to_plain(merged), indent=2) + "\n", encoding="utf-8")
        (reports / "empirical_claim_ledger.md").write_text(
            "# Empirical Claim Ledger\n\n" + render_empirical_claims_table(merged) + "\n",
            encoding="utf-8",
        )


def _parse_metrics_artifact(
    *,
    artifact: ExperimentResultArtifact,
    execution: ExperimentExecutionRecord,
    manifest: ExperimentRunManifest,
    metrics: list[MetricRecord],
) -> tuple[list[MetricResult], list[str]]:
    payload = json.loads(Path(artifact.path).read_text(encoding="utf-8"))
    entries = _metric_entries(payload)
    metric_lookup = _metric_lookup(metrics)
    limitations: list[str] = _payload_limitations(payload)
    results: list[MetricResult] = []
    for index, entry in enumerate(entries, start=1):
        raw_metric = str(entry.get("metric_id") or entry.get("metric") or entry.get("name") or "")
        value = _numeric_value(entry.get("value"))
        if raw_metric == "" or value is None:
            continue
        metric_id = _resolve_metric_id(raw_metric, metric_lookup)
        ci = _confidence_interval(entry)
        sample_size = _sample_size(entry)
        metric_record = metric_lookup.get(_normalize_metric(raw_metric)) or metric_lookup.get(_normalize_metric(metric_id))
        if _is_low_fpr(metric_record, raw_metric) and not ci:
            limitations.append(f"Metric `{metric_id}` is low-FPR-related but lacks a confidence interval.")
        limitations.extend(_entry_limitations(entry))
        result = MetricResult(
            id=f"metric-result-{_stable_id(execution.id, artifact.id, metric_id, str(index))}",
            execution_id=execution.id,
            metric_id=metric_id,
            dataset_id=str(entry.get("dataset_id") or _first(manifest.dataset_ids)),
            baseline_id=str(entry.get("baseline_id") or _first(manifest.baseline_ids)),
            value=value,
            confidence_interval=ci,
            sample_size=sample_size,
            split_name=str(entry.get("split_name") or entry.get("split") or ""),
            raw_artifact_id=artifact.id,
            provenance=Provenance(
                created_by_skill="result-parser",
                source_ids=[execution.id, artifact.id, metric_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Parsed a metric result from a metrics_json experiment artifact.",
            ),
        )
        results.append(result)
    return results, limitations


def _payload_limitations(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    limitations: list[str] = []
    raw_limitations = payload.get("limitations", [])
    if isinstance(raw_limitations, list):
        limitations.extend(str(item) for item in raw_limitations if item)
    metadata = payload.get("metadata", {})
    if isinstance(metadata, dict) and metadata.get("smoke_underpowered"):
        limitations.append("Smoke outputs are underpowered and cannot support strong low-FPR claims.")
    return limitations


def _entry_limitations(entry: dict[str, Any]) -> list[str]:
    raw_limitations = entry.get("limitations", [])
    if isinstance(raw_limitations, list):
        return [str(item) for item in raw_limitations if item]
    return []


def _metric_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("metric_results"), list):
        return [item for item in payload["metric_results"] if isinstance(item, dict)]
    metrics_payload = payload.get("metrics") if isinstance(payload, dict) else None
    if isinstance(metrics_payload, dict):
        return _entries_from_dict(metrics_payload, payload)
    wiring_payload = payload.get("wiring_metrics") if isinstance(payload, dict) else None
    if isinstance(wiring_payload, dict):
        return _entries_from_dict(wiring_payload, payload)
    if isinstance(payload, dict):
        ignored = {"status", "results", "fixture_data", "workspace_id", "run_id", "metadata"}
        return [{"metric": key, "value": value, **_shared_metric_fields(payload)} for key, value in payload.items() if key not in ignored]
    return []


def _entries_from_dict(values: dict[str, Any], parent: dict[str, Any]) -> list[dict[str, Any]]:
    shared = _shared_metric_fields(parent)
    return [{"metric": key, "value": value, **shared} for key, value in values.items()]


def _shared_metric_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ["dataset_id", "baseline_id", "confidence_interval", "ci", "sample_size", "n", "split", "split_name"]
        if key in payload
    }


def _metric_lookup(metrics: list[MetricRecord]) -> dict[str, MetricRecord]:
    lookup: dict[str, MetricRecord] = {}
    for metric in metrics:
        lookup[_normalize_metric(metric.id)] = metric
        lookup[_normalize_metric(metric.name)] = metric
        lookup[slugify(metric.name)] = metric
    return lookup


def _resolve_metric_id(raw_metric: str, lookup: dict[str, MetricRecord]) -> str:
    metric = lookup.get(_normalize_metric(raw_metric)) or lookup.get(slugify(raw_metric))
    return metric.id if metric is not None else slugify(raw_metric)


def _numeric_value(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _confidence_interval(entry: dict[str, Any]) -> list[float]:
    raw = entry.get("confidence_interval", entry.get("ci", []))
    if isinstance(raw, list | tuple):
        values = [_numeric_value(item) for item in raw]
        return [value for value in values if value is not None]
    return []


def _sample_size(entry: dict[str, Any]) -> int:
    raw = entry.get("sample_size", entry.get("n", 0))
    value = _numeric_value(raw)
    return int(value) if value is not None else 0


def _is_low_fpr(metric: MetricRecord | None, raw_metric: str) -> bool:
    text = raw_metric.lower()
    if metric is not None:
        text += " " + metric.id.lower() + " " + metric.name.lower() + " " + metric.description.lower()
    return any(term in text for term in ["false positive", "fpr", "specificity", "low-fpr", "low fpr"])


def _require_manifest(manifests: list[ExperimentRunManifest], manifest_id: str) -> ExperimentRunManifest:
    for manifest in manifests:
        if manifest.id == manifest_id:
            return manifest
    raise FileNotFoundError(f"No manifest found for {manifest_id}")


def _merge_claims(existing: list[EmpiricalClaim], incoming: list[EmpiricalClaim]) -> list[EmpiricalClaim]:
    merged = {claim.id: claim for claim in existing}
    for claim in incoming:
        merged[claim.id] = claim
    return list(merged.values())


def _normalize_metric(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ")


def _first(values: list[str]) -> str:
    return values[0] if values else ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
