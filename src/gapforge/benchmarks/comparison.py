"""Benchmark comparison reports."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from gapforge.benchmarks.registry import BenchmarkRegistry
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import BenchmarkComparison, Provenance, ResultRecord, from_dict, to_plain
from gapforge.results.database import ResultDatabaseBuilder
from gapforge.state import utc_now_iso


class BenchmarkComparisonBuilder:
    """Compare internal benchmark rows without overclaiming."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.benchmark_registry = BenchmarkRegistry(config)
        self.result_database = ResultDatabaseBuilder(config)

    def compare(self, *, workspace_id: str, benchmark_id: str) -> BenchmarkComparison:
        benchmark = self.benchmark_registry.load_benchmark(benchmark_id)
        table = self.result_database.load_or_build(workspace_id)
        rows = [row for row in table.rows if row.benchmark_id == benchmark_id]
        required_baselines = set(benchmark.baseline_ids)
        baseline_rows = [row for row in rows if _is_required_baseline(row.baseline_id, required_baselines)]
        proposed_rows = [row for row in rows if not _is_required_baseline(row.baseline_id, required_baselines)]
        observed_required = {
            required for required in required_baselines if any(_baseline_matches(row.baseline_id, required) for row in baseline_rows)
        }
        missing = [_display_baseline_id(item) for item in sorted(required_baselines - observed_required)]
        comparison = BenchmarkComparison(
            id=f"benchmark-comparison-{benchmark_id}-{workspace_id}",
            benchmark_id=benchmark_id,
            workspace_id=workspace_id,
            baseline_results=[_row_summary(row) for row in baseline_rows],
            proposed_method_results=[_row_summary(row) for row in proposed_rows],
            comparison_metrics=_comparison_metrics(baseline_rows, proposed_rows),
            statistical_notes=_statistical_notes(rows, benchmark.leaderboard_url),
            missing_baselines=missing,
            limitations=_limitations(rows, missing, benchmark.leaderboard_url),
            provenance=Provenance(
                created_by_skill="benchmark-comparison",
                source_ids=[workspace_id, benchmark_id, *[row.id for row in rows]],
                timestamp=utc_now_iso(),
                reasoning_summary="Compared internal benchmark results while separating run types and avoiding SOTA claims.",
            ),
        )
        self._write_report(workspace_id, comparison)
        return comparison

    def render_workspace_report(self, workspace_id: str) -> str:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        comparisons = []
        for path in sorted((Path(workspace.root_dir) / "reports").glob("benchmark_comparison_*.json")):
            comparisons.append(from_dict(BenchmarkComparison, json.loads(path.read_text(encoding="utf-8"))))
        lines = ["# Benchmark Comparison Reports", ""]
        if not comparisons:
            lines.append("No benchmark comparison reports have been generated.")
            return "\n".join(lines).rstrip() + "\n"
        for comparison in comparisons:
            lines.extend([render_benchmark_comparison(comparison).strip(), ""])
        return "\n".join(lines).rstrip() + "\n"

    def _write_report(self, workspace_id: str, comparison: BenchmarkComparison) -> None:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / f"benchmark_comparison_{comparison.benchmark_id}.json").write_text(
            json.dumps(to_plain(comparison), indent=2) + "\n",
            encoding="utf-8",
        )
        (reports / f"benchmark_comparison_{comparison.benchmark_id}.md").write_text(
            render_benchmark_comparison(comparison),
            encoding="utf-8",
        )


def render_benchmark_comparison(comparison: BenchmarkComparison) -> str:
    lines = [
        f"# Benchmark Comparison `{comparison.id}`",
        "",
        f"- Benchmark ID: `{comparison.benchmark_id}`",
        f"- Workspace ID: `{comparison.workspace_id}`",
        "",
        "## Baseline Results",
        "",
    ]
    lines.extend(_render_rows(comparison.baseline_results))
    lines.extend(["", "## Proposed Method Results", ""])
    lines.extend(_render_rows(comparison.proposed_method_results))
    lines.extend(["", "## Comparison Metrics", ""])
    lines.extend([f"- {item}" for item in comparison.comparison_metrics] or ["- none"])
    lines.extend(["", "## Statistical Notes", ""])
    lines.extend([f"- {item}" for item in comparison.statistical_notes] or ["- none"])
    lines.extend(["", "## Missing Baselines", ""])
    lines.extend([f"- `{item}`" for item in comparison.missing_baselines] or ["- none"])
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in comparison.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _render_rows(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- none"]
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("run_type", "unknown"))].append(row)
    lines: list[str] = []
    for run_type, items in sorted(grouped.items()):
        lines.append(f"### Run type `{run_type}`")
        lines.append("")
        for row in items:
            lines.append(
                f"- `{row.get('baseline_id', 'missing')}` metric `{row.get('metric_id', 'unknown')}` "
                f"split `{row.get('split', 'unknown')}` seed {row.get('seed', 0)} value {row.get('value', 'unknown')}"
            )
        lines.append("")
    return lines


def _comparison_metrics(baseline_rows: list[ResultRecord], proposed_rows: list[ResultRecord]) -> list[str]:
    metrics: list[str] = []
    for proposed in proposed_rows:
        for baseline in baseline_rows:
            if (baseline.metric_id, baseline.split, baseline.run_type) != (proposed.metric_id, proposed.split, proposed.run_type):
                continue
            delta = proposed.value - baseline.value
            metrics.append(
                f"Run type `{proposed.run_type}` proposed vs {baseline.baseline_id}: "
                f"{proposed.metric_id} delta {delta:g} ({proposed.value:g} vs {baseline.value:g})."
            )
    return metrics


def _statistical_notes(rows: list[ResultRecord], leaderboard_url: str) -> list[str]:
    notes = ["Smoke and pilot results are reported separately from main results."]
    if not leaderboard_url:
        notes.append("No SOTA claim: no verified external leaderboard policy or evidence is linked.")
    else:
        notes.append("No SOTA claim unless the external leaderboard is fetched, verified, and policy allows it.")
    if any(not row.confidence_interval for row in rows):
        notes.append("Some result rows lack confidence intervals.")
    return notes


def _limitations(rows: list[ResultRecord], missing: list[str], leaderboard_url: str) -> list[str]:
    limitations = []
    if not rows:
        limitations.append("No internal result rows were found for this benchmark.")
    if missing:
        limitations.append("Missing required baseline results block strong comparative claims.")
        limitations.extend([f"Missing required baseline `{item}`." for item in missing])
    if not leaderboard_url:
        limitations.append("External leaderboard was not fetched or verified.")
    limitations.append("Benchmark comparison uses internal artifact-backed results only unless external rows are explicitly labeled.")
    return limitations


def _row_summary(row: ResultRecord) -> dict[str, object]:
    return {
        "id": row.id,
        "execution_id": row.execution_id,
        "benchmark_id": row.benchmark_id,
        "baseline_id": row.baseline_id,
        "metric_id": row.metric_id,
        "split": row.split,
        "seed": row.seed,
        "value": row.value,
        "confidence_interval": row.confidence_interval,
        "run_type": row.run_type,
        "artifact_id": row.artifact_id,
    }


def _is_required_baseline(baseline_id: str, required_baselines: set[str]) -> bool:
    return any(_baseline_matches(baseline_id, required) for required in required_baselines)


def _baseline_matches(observed: str, required: str) -> bool:
    observed_key = _baseline_key(observed)
    required_key = _baseline_key(required)
    return observed_key == required_key or observed_key in required_key or required_key in observed_key


def _display_baseline_id(baseline_id: str) -> str:
    key = _baseline_key(baseline_id)
    if key.startswith("baseline-"):
        key = key.removeprefix("baseline-")
    parts = key.split("-")
    if len(parts) > 1 and len(parts[-1]) >= 6 and all(ch in "0123456789abcdef" for ch in parts[-1]):
        return "-".join(parts[:-1])
    return key


def _baseline_key(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")
