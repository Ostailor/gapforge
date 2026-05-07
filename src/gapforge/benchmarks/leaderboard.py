"""Conservative benchmark leaderboard reports."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.benchmarks.registry import BenchmarkRegistry
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import LeaderboardReport, Provenance, to_plain
from gapforge.results.database import ResultDatabaseBuilder
from gapforge.state import utc_now_iso


class LeaderboardBuilder:
    """Build internal leaderboard reports and label missing external verification."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.benchmark_registry = BenchmarkRegistry(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.result_database = ResultDatabaseBuilder(config)

    def build(self, benchmark_id: str) -> LeaderboardReport:
        benchmark = self.benchmark_registry.load_benchmark(benchmark_id)
        workspace_id = _workspace_id_from_benchmark(benchmark)
        table = self.result_database.load_or_build(workspace_id)
        rows = [
            {
                "method": row.baseline_id or "unknown",
                "metric_id": row.metric_id,
                "value": row.value,
                "split": row.split,
                "run_type": row.run_type,
                "source": "internal",
                "execution_id": row.execution_id,
            }
            for row in table.rows
            if row.benchmark_id == benchmark_id
        ]
        limitations = ["External leaderboard was not fetched or verified; external entries are not included."]
        if benchmark.leaderboard_url:
            limitations.append(f"Leaderboard URL recorded but not fetched: {benchmark.leaderboard_url}")
        limitations.append("Internal smoke, pilot, and main rows are labeled by run type and must not be mixed.")
        report = LeaderboardReport(
            id=f"leaderboard-{benchmark_id}",
            benchmark_id=benchmark_id,
            rows=rows,
            source="internal",
            generated_at=utc_now_iso(),
            limitations=limitations,
            provenance=Provenance(
                created_by_skill="leaderboard-report",
                source_ids=[workspace_id, benchmark_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Rendered an internal leaderboard report without claiming verified external standing.",
            ),
        )
        _write_report(self.workspace_manager.load_workspace(workspace_id).root_dir, report)
        return report


def render_leaderboard_report(report: LeaderboardReport) -> str:
    lines = [
        f"# Leaderboard Report `{report.id}`",
        "",
        f"- Benchmark ID: `{report.benchmark_id}`",
        f"- Source: `{report.source}`",
        f"- Generated at: {report.generated_at or 'unknown'}",
        "",
        "## Rows",
        "",
    ]
    if report.rows:
        for row in report.rows:
            lines.append(
                f"- `{row.get('method', 'unknown')}` metric `{row.get('metric_id', 'unknown')}` value {row.get('value', 'unknown')} "
                f"split `{row.get('split', 'unknown')}` run type `{row.get('run_type', 'unknown')}` source `{row.get('source', 'unknown')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Limitations", ""])
    lines.extend([f"- {item}" for item in report.limitations] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _write_report(root_dir: str, report: LeaderboardReport) -> None:
    reports = Path(root_dir) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"leaderboard_{report.benchmark_id}.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
    (reports / f"leaderboard_{report.benchmark_id}.md").write_text(render_leaderboard_report(report), encoding="utf-8")


def _workspace_id_from_benchmark(benchmark) -> str:
    return benchmark.provenance.source_ids[0] if benchmark.provenance.source_ids else ""
