"""Main result analysis for selected benchmark executions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.main_run import MainRunManager, SelectedMainExecution
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class MainAnalysisResult:
    id: str
    benchmark_id: str
    execution_id: str
    dataset_id: str
    run_type: str = "main"
    powered_alpha_levels: list[str] = field(default_factory=list)
    publication_claim_blocked: bool = True
    publication_blockers: list[str] = field(default_factory=list)
    output_paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-analysis"))


class MainAnalysisManager:
    """Analyze saved main-run artifacts and render claim-gated summaries."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.main_run_manager = MainRunManager(config)

    def analyze(self, execution_id: str) -> MainAnalysisResult:
        execution = self.main_run_manager.status(execution_id)
        if execution.run_type != "main":
            raise ValueError(f"Execution `{execution_id}` is `{execution.run_type}`, not main.")
        metrics = _read_json(execution.output_paths["metrics_json"])
        predictions = _read_json(execution.output_paths["predictions_json"])
        baseline_comparison = _read_json(execution.output_paths["baseline_comparison"])
        error_analysis = _read_json(execution.output_paths["error_analysis"])
        low_fpr = _read_json(execution.output_paths["low_fpr_report_json"])
        output_dir = self._analysis_dir(execution)
        output_paths = self._write_outputs(
            output_dir=output_dir,
            metrics=_main_metrics(metrics, execution=execution),
            baseline_comparison=baseline_comparison,
            error_analysis=error_analysis,
            low_fpr_report=low_fpr,
            prediction_summary=_prediction_summary(predictions),
        )
        result = MainAnalysisResult(
            id=f"main-analysis-{slugify(execution.id)}",
            benchmark_id=execution.benchmark_id,
            execution_id=execution.id,
            dataset_id=execution.dataset_id,
            run_type="main",
            powered_alpha_levels=list(execution.powered_alpha_levels),
            publication_claim_blocked=execution.publication_claim_blocked,
            publication_blockers=list(execution.publication_blockers),
            output_paths=output_paths,
            warnings=[
                *execution.warnings,
                "Main analysis is synthetic benchmark analysis, not deployment-validity evidence.",
                "Go/no-go decisions must also inspect related work, reviewer status, and manuscript traceability.",
            ],
            provenance=Provenance(
                created_by_skill="selected-main-analysis",
                source_ids=[execution.benchmark_id, execution.id, execution.dataset_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Analyzed saved selected benchmark main metrics, predictions, baseline comparison, and low-FPR report.",
            ),
        )
        self._write_json(output_dir / "analysis_result.json", result)
        (output_dir / "main_report.md").write_text(render_selected_main_analysis(result), encoding="utf-8")
        return result

    def load_latest_for_benchmark(self, benchmark_id: str) -> MainAnalysisResult:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        root = self._benchmark_dir(spec.project_id) / "main_analysis"
        candidates = sorted(root.glob("*/analysis_result.json"), key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            result = from_dict(MainAnalysisResult, json.loads(path.read_text(encoding="utf-8")))
            if result.benchmark_id == benchmark_id:
                return result
        raise FileNotFoundError(f"No selected main analysis found for `{benchmark_id}`.")

    def report(self, benchmark_id: str) -> str:
        result = self.load_latest_for_benchmark(benchmark_id)
        report = render_selected_main_analysis(result)
        Path(result.output_paths["main_report_md"]).write_text(report, encoding="utf-8")
        return report

    def _write_outputs(
        self,
        *,
        output_dir: Path,
        metrics: dict[str, Any],
        baseline_comparison: dict[str, Any],
        error_analysis: dict[str, Any],
        low_fpr_report: dict[str, Any],
        prediction_summary: dict[str, Any],
    ) -> dict[str, str]:
        paths = {
            "main_metrics_json": output_dir / "main_metrics.json",
            "main_baseline_comparison_json": output_dir / "main_baseline_comparison.json",
            "main_error_analysis_json": output_dir / "main_error_analysis.json",
            "main_low_fpr_report_json": output_dir / "main_low_fpr_report.json",
            "main_prediction_summary_json": output_dir / "main_prediction_summary.json",
            "main_report_md": output_dir / "main_report.md",
        }
        self._write_json(paths["main_metrics_json"], metrics)
        self._write_json(paths["main_baseline_comparison_json"], baseline_comparison)
        self._write_json(paths["main_error_analysis_json"], error_analysis)
        self._write_json(paths["main_low_fpr_report_json"], low_fpr_report)
        self._write_json(paths["main_prediction_summary_json"], prediction_summary)
        return {key: str(path) for key, path in paths.items()}

    def _analysis_dir(self, execution: SelectedMainExecution) -> Path:
        spec = self.benchmark_manager.load_spec(execution.benchmark_id)
        path = self._benchmark_dir(spec.project_id) / "main_analysis" / f"main-analysis-{slugify(execution.id)}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_selected_main_analysis(result: MainAnalysisResult) -> str:
    low_fpr = _read_json(result.output_paths["main_low_fpr_report_json"])
    comparison = _read_json(result.output_paths["main_baseline_comparison_json"])
    errors = _read_json(result.output_paths["main_error_analysis_json"])
    lines = [
        f"# Main Result Analysis `{result.execution_id}`",
        "",
        f"- Benchmark ID: `{result.benchmark_id}`",
        f"- Dataset ID: `{result.dataset_id}`",
        f"- Run type: `{result.run_type}`",
        f"- Powered alpha levels: {', '.join(result.powered_alpha_levels) or 'none'}",
        f"- Publication claim blocked: {str(result.publication_claim_blocked).lower()}",
        "",
        "## Low-FPR Status",
        "",
        f"- Supported alpha levels: {', '.join(low_fpr.get('supported_alpha_levels', [])) or 'none'}",
        f"- Underpowered alpha levels: {', '.join(low_fpr.get('underpowered_alpha_levels', [])) or 'none'}",
        f"- Zero-FP upper bound: {low_fpr.get('zero_false_positive_upper_bound', 'not available')}",
        "",
        "## Baseline Comparison",
        "",
        f"- Baseline rows: {len(comparison.get('rows', []))}",
        "",
        "## Error Analysis",
        "",
        f"- Failure count: {errors.get('failure_count', 0)}",
        f"- Missing monitor outputs: {', '.join(errors.get('missing_monitor_outputs', [])) or 'none'}",
        "",
        "## Publication Blockers",
        "",
    ]
    lines.extend([f"- {blocker}" for blocker in result.publication_blockers] or ["- none"])
    lines.extend(["", "## Non-Claims", "", "- Synthetic main analysis does not establish deployment validity."])
    return "\n".join(lines).rstrip() + "\n"


def _main_metrics(metrics_payload: dict[str, Any], *, execution: SelectedMainExecution) -> dict[str, Any]:
    by_name = {item.get("metric_name") or item.get("metric_id"): item for item in metrics_payload.get("metrics", [])}
    return {
        "run_type": "main",
        "execution_id": execution.id,
        "dataset_id": execution.dataset_id,
        "powered_alpha_levels": execution.powered_alpha_levels,
        "per_episode_false_positive_rate": _metric_value(by_name, "per_episode_false_positive_rate"),
        "zero_false_positive_upper_bound": _metric_value(by_name, "zero_false_positive_upper_bound"),
        "true_positive_rate_at_fixed_false_positive_budget": _metric_value(by_name, "true_positive_rate_at_fixed_false_positive_budget"),
        "raw_metric_results": metrics_payload.get("metrics", []),
    }


def _prediction_summary(predictions_payload: dict[str, Any]) -> dict[str, Any]:
    by_monitor = predictions_payload.get("predictions_by_monitor", {})
    return {
        "monitor_count": len(by_monitor),
        "prediction_count": sum(len(items) for items in by_monitor.values() if isinstance(items, list)),
        "monitors": sorted(by_monitor),
    }


def _metric_value(by_name: dict[str, Any], name: str) -> Any:
    item = by_name.get(name)
    if not item:
        return "not available"
    return item.get("value", "not available")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
