"""Artifact-backed manuscript table generation."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import ManuscriptState, ManuscriptTable
from gapforge.models import ExperimentExecutionRecord, ExperimentResultArtifact, Provenance, ResultSummary, from_dict, to_plain
from gapforge.results.parser import ResultParser
from gapforge.state import slugify, utc_now_iso

TABLE_TYPES = {"result_table", "baseline_comparison", "ablation", "dataset_summary", "reproducibility", "custom"}


class ManuscriptTableGenerator:
    """Generate conservative manuscript tables from recorded result artifacts."""

    def __init__(self, config) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.result_parser = ResultParser(config)

    def generate(self, manuscript_id: str, table_type: str) -> ManuscriptTable:
        if table_type not in TABLE_TYPES:
            raise ValueError(f"Unsupported manuscript table type: {table_type}")
        state = self.manuscript_manager.load_state(manuscript_id)
        context = _asset_context(self.workspace_manager, self.result_parser, state)
        if table_type in {"result_table", "baseline_comparison"} and not context.artifacts:
            raise ValueError("No result artifacts are available; manuscript tables cannot be generated.")
        table_id = _next_asset_id(self.manuscript_manager.manuscript_root(manuscript_id) / "tables", table_type)
        table_path = Path("tables") / f"{table_id}.md"
        title = _table_title(table_type)
        caption = _caption(table_type, context)
        content = _render_table_content(table_type, context, title, caption)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        (root / table_path).write_text(content, encoding="utf-8")
        source_result_ids = _artifact_backed_execution_ids(context)
        table = ManuscriptTable(
            id=table_id,
            manuscript_id=manuscript_id,
            title=title,
            caption=caption,
            source_result_ids=source_result_ids,
            source_artifact_ids=[artifact.id for artifact in context.artifacts],
            path=str(table_path),
            table_type=table_type,
            status="generated",
            provenance=Provenance(
                created_by_skill="manuscript-table",
                source_ids=[manuscript_id, *source_result_ids, *[artifact.id for artifact in context.artifacts]],
                timestamp=utc_now_iso(),
                reasoning_summary="Generated a manuscript table from recorded execution/result artifacts; no results were invented.",
            ),
        )
        _write_asset_json(root / "tables" / f"{table.id}.json", table)
        state.table_ids = _unique([*state.table_ids, table.id])
        self.manuscript_manager._save_state(state)
        return table

    def list_tables(self, manuscript_id: str) -> list[ManuscriptTable]:
        root = self.manuscript_manager.manuscript_root(manuscript_id) / "tables"
        return _load_assets(root, ManuscriptTable)


class _AssetContext:
    def __init__(
        self,
        executions: list[ExperimentExecutionRecord],
        artifacts: list[ExperimentResultArtifact],
        summaries: list[ResultSummary],
    ) -> None:
        self.executions = executions
        self.artifacts = artifacts
        self.summaries = summaries


def _asset_context(
    workspace_manager: ExperimentWorkspaceManager,
    result_parser: ResultParser,
    state: ManuscriptState,
) -> _AssetContext:
    workspace = workspace_manager.load_workspace(state.manuscript.workspace_id)
    executions = workspace_manager.list_execution_records(workspace.id)
    artifacts = workspace_manager.list_result_artifacts(workspace.id)
    summaries: list[ResultSummary] = []
    for execution in executions:
        if execution.result_artifact_ids:
            summaries.append(result_parser.load_or_parse_summary(execution.id))
    return _AssetContext(executions=executions, artifacts=artifacts, summaries=summaries)


def _render_table_content(table_type: str, context: _AssetContext, title: str, caption: str) -> str:
    if table_type == "baseline_comparison":
        return _render_baseline_comparison(context, title, caption)
    return _render_result_table(context, title, caption)


def _render_result_table(context: _AssetContext, title: str, caption: str) -> str:
    lines = [
        f"# {title}",
        "",
        caption,
        "",
        "| Execution | Run type | Status | Metric | Value | Sample size | Artifact | Limitations |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    rows = 0
    for summary in context.summaries:
        execution = _execution_by_id(context.executions, summary.execution_id)
        run_type = _run_type(execution)
        for metric in summary.metric_results:
            lines.append(
                f"| `{execution.id}` | `{run_type}` | `{execution.status}` | `{metric.metric_id}` | "
                f"{metric.value:g} | {metric.sample_size or 0} | `{metric.raw_artifact_id}` | "
                f"{'; '.join(summary.limitations) or 'none'} |"
            )
            rows += 1
        if execution.status == "failed" and not summary.metric_results:
            failure_reason = execution.failure_reason or "; ".join(summary.failures) or "failed"
            lines.append(
                f"| `{execution.id}` | `{run_type}` | `failed` | failure |  | 0 | "
                f"{', '.join(execution.result_artifact_ids) or 'none'} | {failure_reason} |"
            )
            rows += 1
    if rows == 0:
        for execution in context.executions:
            if execution.status == "failed":
                lines.append(
                    f"| `{execution.id}` | `{_run_type(execution)}` | `failed` | failure |  | 0 | "
                    f"{', '.join(execution.result_artifact_ids) or 'none'} | {execution.failure_reason or 'failed'} |"
                )
                rows += 1
    if rows == 0:
        raise ValueError("No metric results or failed-run records are available for a manuscript table.")
    return "\n".join(lines).rstrip() + "\n"


def _render_baseline_comparison(context: _AssetContext, title: str, caption: str) -> str:
    lines = [
        f"# {title}",
        "",
        caption,
        "",
        "| Baseline | Run type | Metric | Value | Execution | Artifact |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    rows = 0
    for summary in context.summaries:
        execution = _execution_by_id(context.executions, summary.execution_id)
        run_type = _run_type(execution)
        for metric in summary.metric_results:
            lines.append(
                f"| `{metric.baseline_id or 'none'}` | `{run_type}` | `{metric.metric_id}` | "
                f"{metric.value:g} | `{execution.id}` | `{metric.raw_artifact_id}` |"
            )
            rows += 1
    if rows == 0:
        raise ValueError("No baseline comparison rows can be generated without metric result artifacts.")
    return "\n".join(lines).rstrip() + "\n"


def _caption(table_type: str, context: _AssetContext) -> str:
    executions = [_execution_by_id(context.executions, execution_id) for execution_id in _artifact_backed_execution_ids(context)]
    run_types = _unique([_run_type(execution) for execution in executions])
    failed = [execution.id for execution in executions if execution.status == "failed"]
    limitation = " Failed runs are included as failure rows." if failed else ""
    return (
        f"Artifact-backed {table_type.replace('_', ' ')} generated from {len(context.artifacts)} result artifact(s). "
        f"Run type labels visible: {', '.join(run_types) or 'none'}.{limitation} "
        "Smoke and pilot rows are not presented as main results."
    )


def _table_title(table_type: str) -> str:
    return {
        "result_table": "Result Table",
        "baseline_comparison": "Baseline Comparison",
        "ablation": "Ablation Table",
        "dataset_summary": "Dataset Summary",
        "reproducibility": "Reproducibility Table",
    }.get(table_type, "Custom Table")


def _run_type(execution: ExperimentExecutionRecord) -> str:
    for value in ("smoke", "pilot", "main", "ablation", "negative_control", "reproduction"):
        if value in execution.manifest_id:
            return value
    return "unknown"


def _execution_by_id(executions: list[ExperimentExecutionRecord], execution_id: str) -> ExperimentExecutionRecord:
    for execution in executions:
        if execution.id == execution_id:
            return execution
    raise FileNotFoundError(f"No execution record found for {execution_id}")


def _artifact_backed_execution_ids(context: _AssetContext) -> list[str]:
    artifact_execution_ids = {artifact.execution_id for artifact in context.artifacts}
    return _unique([summary.execution_id for summary in context.summaries if summary.execution_id in artifact_execution_ids])


def _next_asset_id(root: Path, asset_type: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(asset_type)}"
    candidate = base
    suffix = 2
    while (root / f"{candidate}.json").exists() or (root / f"{candidate}.md").exists() or (root / f"{candidate}.svg").exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _write_asset_json(path: Path, asset: ManuscriptTable) -> None:
    path.write_text(json.dumps(to_plain(asset), indent=2) + "\n", encoding="utf-8")


def _load_assets(root: Path, model):
    if not root.exists():
        return []
    return [from_dict(model, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(root.glob("*.json"))]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
