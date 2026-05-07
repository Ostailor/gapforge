"""Error analysis reports from prediction artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ErrorAnalysisReport, Provenance, from_dict, to_plain
from gapforge.results.slices import build_error_slice, error_counts, error_examples, load_predictions_for_execution
from gapforge.state import utc_now_iso


class ErrorAnalysisBuilder:
    """Create error reports without fabricating examples."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def analyze_execution(self, execution_id: str) -> ErrorAnalysisReport:
        workspace, execution = ExperimentRunner(self.config).find_execution(execution_id)
        predictions = load_predictions_for_execution(self.workspace_manager, workspace.id, execution_id)
        limitations: list[str] = []
        slices = []
        top_error_types: list[str] = []
        qualitative_examples = []
        if not predictions:
            limitations.append("No predictions artifact is linked to this execution; error analysis requires artifact-backed predictions.")
        else:
            counts = error_counts(predictions)
            top_error_types = _rank_error_types(
                counts, low_fpr=_is_low_fpr_execution(workspace.id, execution.manifest_id, self.workspace_manager)
            )
            qualitative_examples = error_examples(predictions)
            slices.append(
                build_error_slice(
                    workspace_id=workspace.id,
                    execution_id=execution_id,
                    slice_name="all",
                    filter_description="All prediction artifact rows.",
                    predictions=predictions,
                )
            )
            if _is_low_fpr_execution(workspace.id, execution.manifest_id, self.workspace_manager):
                limitations.append("Low-FPR context: false positives are emphasized and should be inspected before claiming success.")
        report = ErrorAnalysisReport(
            id=f"error-analysis-{execution_id}",
            workspace_id=workspace.id,
            execution_id=execution_id,
            top_error_types=top_error_types,
            slices=slices,
            qualitative_examples=qualitative_examples,
            limitations=limitations,
            provenance=Provenance(
                created_by_skill="error-analysis",
                source_ids=[workspace.id, execution_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Built an error analysis report from prediction artifacts only.",
            ),
        )
        self._write_report(workspace.root_dir, report)
        return report

    def render_workspace_report(self, workspace_id: str) -> str:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        reports = []
        for path in sorted((Path(workspace.root_dir) / "reports").glob("error_analysis_*.json")):
            reports.append(from_dict(ErrorAnalysisReport, json.loads(path.read_text(encoding="utf-8"))))
        lines = ["# Error Analysis Reports", ""]
        if not reports:
            lines.append("No error analysis reports have been generated.")
            return "\n".join(lines).rstrip() + "\n"
        for report in reports:
            lines.extend([f"## `{report.id}`", "", render_error_analysis_report(report).strip(), ""])
        return "\n".join(lines).rstrip() + "\n"

    def _write_report(self, root_dir: str, report: ErrorAnalysisReport) -> None:
        reports = Path(root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / f"error_analysis_{report.execution_id}.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (reports / f"error_analysis_{report.execution_id}.md").write_text(render_error_analysis_report(report), encoding="utf-8")


def render_error_analysis_report(report: ErrorAnalysisReport) -> str:
    lines = [
        f"# Error Analysis Report `{report.id}`",
        "",
        f"- Workspace ID: `{report.workspace_id}`",
        f"- Execution ID: `{report.execution_id}`",
        "",
        "## Top Error Types",
        "",
    ]
    lines.extend([f"- {item}" for item in report.top_error_types] or ["- none"])
    lines.extend(["", "## Slices", ""])
    if report.slices:
        for error_slice in report.slices:
            lines.append(f"- `{error_slice.slice_name}` sample count {error_slice.sample_count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Qualitative Artifact Examples", ""])
    lines.extend([f"- `{example.get('id', 'unknown')}` {example}" for example in report.qualitative_examples] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in report.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _rank_error_types(counts: dict[str, int], *, low_fpr: bool) -> list[str]:
    keys = ["false_positive", "false_negative", "other", "true_positive", "true_negative"]
    if not low_fpr:
        keys = sorted(keys, key=lambda key: counts.get(key, 0), reverse=True)
    return [f"{key}: {counts[key]}" for key in keys if counts.get(key, 0) > 0 and key in {"false_positive", "false_negative", "other"}]


def _is_low_fpr_execution(workspace_id: str, manifest_id: str, manager: ExperimentWorkspaceManager) -> bool:
    manifest = next((item for item in manager.list_manifests(workspace_id) if item.id == manifest_id), None)
    if manifest is None:
        return False
    text = " ".join(manifest.metric_ids).lower()
    return any(term in text for term in ["false positive", "fpr", "specificity", "low-fpr", "low fpr"])
