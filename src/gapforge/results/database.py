"""Workspace result database for benchmark comparisons."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import (
    ExperimentExecutionRecord,
    ExperimentRunManifest,
    MetricResult,
    Provenance,
    ResultRecord,
    ResultTable,
    from_dict,
    to_plain,
)
from gapforge.results.parser import ResultParser
from gapforge.state import utc_now_iso


class ResultDatabaseBuilder:
    """Build a normalized result table from parsed execution summaries."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.parser = ResultParser(config)

    def build(self, workspace_id: str) -> ResultTable:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        manifests = {manifest.id: manifest for manifest in self.workspace_manager.list_manifests(workspace_id)}
        artifacts_by_id = {artifact.id: artifact for artifact in self.workspace_manager.list_result_artifacts(workspace_id)}
        rows: list[ResultRecord] = []
        failed_execution_ids: list[str] = []
        for execution in self.workspace_manager.list_execution_records(workspace_id):
            if execution.status == "failed":
                failed_execution_ids.append(execution.id)
            if execution.status != "complete":
                continue
            manifest = manifests.get(execution.manifest_id)
            if manifest is None:
                continue
            summary = self.parser.load_or_parse_summary(execution.id)
            for metric_result in summary.metric_results:
                rows.append(
                    _record_from_metric_result(
                        workspace_id=workspace_id,
                        execution=execution,
                        manifest=manifest,
                        metric_result=metric_result,
                        benchmark_id=_benchmark_id_for_metric(metric_result, artifacts_by_id.get(metric_result.raw_artifact_id)),
                    )
                )
        table = ResultTable(
            id=f"result-table-{workspace_id}",
            workspace_id=workspace_id,
            rows=rows,
            grouped_by=["benchmark_id", "dataset_id", "baseline_id", "metric_id", "split", "run_type"],
            generated_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="result-database",
                source_ids=[workspace.root_dir, workspace_id, *[row.execution_id for row in rows]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Built an auditable result table from complete artifact-backed executions; failed executions are listed separately."
                ),
            ),
        )
        _reports_dir(workspace.root_dir).mkdir(parents=True, exist_ok=True)
        self._write_table(workspace.root_dir, table)
        _write_failed_executions(workspace.root_dir, failed_execution_ids)
        return table

    def load_or_build(self, workspace_id: str) -> ResultTable:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        path = _table_path(workspace.root_dir)
        if path.exists():
            return from_dict(ResultTable, json.loads(path.read_text(encoding="utf-8")))
        return self.build(workspace_id)

    def export_csv(self, workspace_id: str) -> Path:
        table = self.load_or_build(workspace_id)
        workspace = self.workspace_manager.load_workspace(workspace_id)
        path = _reports_dir(workspace.root_dir) / "result_table.csv"
        fieldnames = [
            "workspace_id",
            "execution_id",
            "benchmark_id",
            "dataset_id",
            "baseline_id",
            "metric_id",
            "split",
            "seed",
            "value",
            "confidence_interval",
            "run_type",
            "artifact_id",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in table.rows:
                writer.writerow(
                    {
                        "workspace_id": row.workspace_id,
                        "execution_id": row.execution_id,
                        "benchmark_id": row.benchmark_id,
                        "dataset_id": row.dataset_id,
                        "baseline_id": row.baseline_id,
                        "metric_id": row.metric_id,
                        "split": row.split,
                        "seed": row.seed,
                        "value": row.value,
                        "confidence_interval": json.dumps(row.confidence_interval),
                        "run_type": row.run_type,
                        "artifact_id": row.artifact_id,
                    }
                )
        return path

    def _write_table(self, root_dir: str, table: ResultTable) -> None:
        _table_path(root_dir).write_text(json.dumps(to_plain(table), indent=2) + "\n", encoding="utf-8")
        (_reports_dir(root_dir) / "result_table.md").write_text(render_result_table_markdown(table), encoding="utf-8")


def render_result_table_markdown(table: ResultTable) -> str:
    root_dir = _root_for_table(table)
    failed = _load_failed_executions(root_dir) if root_dir else []
    lines = [
        f"# Result Table `{table.id}`",
        "",
        f"- Workspace ID: `{table.workspace_id}`",
        f"- Rows: {len(table.rows)}",
        f"- Grouped by: {', '.join(table.grouped_by) or 'none'}",
        f"- Generated at: {table.generated_at or 'unknown'}",
        "",
        "## Rows",
        "",
        "| Execution | Benchmark | Dataset | Baseline | Metric | Split | Seed | Run type | Value | CI | Artifact |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | --- | --- |",
    ]
    if table.rows:
        for row in table.rows:
            lines.append(
                f"| `{row.execution_id}` | `{row.benchmark_id or 'unknown'}` | `{row.dataset_id or 'unknown'}` | "
                f"`{row.baseline_id or 'missing'}` | `{row.metric_id}` | `{row.split or 'unknown'}` | {row.seed} | "
                f"`{row.run_type or 'unknown'}` | {row.value:g} | {_format_ci(row.confidence_interval)} | `{row.artifact_id}` |"
            )
    else:
        lines.append("| none | none | none | none | none | none |  | none |  | none | none |")
    lines.extend(["", "## Failed Executions Excluded From Aggregates", ""])
    lines.extend([f"- `{execution_id}`" for execution_id in failed] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _record_from_metric_result(
    *,
    workspace_id: str,
    execution: ExperimentExecutionRecord,
    manifest: ExperimentRunManifest,
    metric_result: MetricResult,
    benchmark_id: str,
) -> ResultRecord:
    return ResultRecord(
        id=f"result-record-{_stable_id(execution.id, metric_result.id)}",
        workspace_id=workspace_id,
        execution_id=execution.id,
        benchmark_id=benchmark_id,
        dataset_id=metric_result.dataset_id,
        baseline_id=metric_result.baseline_id,
        metric_id=metric_result.metric_id,
        split=metric_result.split_name,
        seed=manifest.random_seed,
        value=metric_result.value,
        confidence_interval=metric_result.confidence_interval,
        run_type=manifest.run_type,
        artifact_id=metric_result.raw_artifact_id,
        provenance=Provenance(
            created_by_skill="result-database",
            source_ids=[execution.id, metric_result.raw_artifact_id, metric_result.metric_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Normalized one parsed metric result into a benchmark result database row.",
        ),
    )


def _benchmark_id_for_metric(metric_result: MetricResult, artifact: Any) -> str:
    if artifact is None or not getattr(artifact, "path", ""):
        return ""
    try:
        payload = json.loads(Path(artifact.path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    entries = payload.get("metric_results") if isinstance(payload, dict) else None
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if _matches_metric_result(entry, metric_result):
                return str(entry.get("benchmark_id") or "")
    return str(payload.get("benchmark_id") or "") if isinstance(payload, dict) else ""


def _matches_metric_result(entry: dict[str, Any], metric_result: MetricResult) -> bool:
    raw_metric = str(entry.get("metric_id") or entry.get("metric") or entry.get("name") or "")
    value = entry.get("value")
    try:
        numeric_value = float(str(value))
    except (TypeError, ValueError):
        numeric_value = None
    return bool(
        raw_metric
        and (
            metric_result.metric_id.endswith(raw_metric.replace(" ", "-"))
            or (numeric_value is not None and abs(numeric_value - metric_result.value) < 1e-12)
        )
    )


def _write_failed_executions(root_dir: str, failed_execution_ids: list[str]) -> None:
    (_reports_dir(root_dir) / "result_db_failed_executions.json").write_text(
        json.dumps(list(dict.fromkeys(failed_execution_ids)), indent=2) + "\n",
        encoding="utf-8",
    )


def _load_failed_executions(root_dir: str) -> list[str]:
    path = _reports_dir(root_dir) / "result_db_failed_executions.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _table_path(root_dir: str) -> Path:
    return _reports_dir(root_dir) / "result_table.json"


def _reports_dir(root_dir: str) -> Path:
    return Path(root_dir) / "reports"


def _root_for_table(table: ResultTable) -> str:
    source_ids = table.provenance.source_ids
    return source_ids[0] if source_ids and Path(source_ids[0]).exists() else ""


def _format_ci(values: list[float]) -> str:
    if not values:
        return "missing"
    if len(values) == 2:
        return f"[{values[0]:g}, {values[1]:g}]"
    return ", ".join(f"{value:g}" for value in values)


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
