"""Benchmark suite rendering helpers."""

from __future__ import annotations

from gapforge.models import BenchmarkRecord, BenchmarkSuite


def render_benchmark_suite_status_markdown(
    suite: BenchmarkSuite,
    benchmarks: list[BenchmarkRecord],
    blockers: list[str],
) -> str:
    benchmark_ids = {record.id for record in benchmarks}
    lines = [
        f"# Benchmark Suite `{suite.id}`",
        "",
        f"- Name: {suite.name}",
        f"- Source profile: `{suite.source_profile}`",
        f"- Benchmarks: {', '.join(f'`{item}`' for item in suite.benchmark_ids) or 'none'}",
        f"- Required tasks: {', '.join(f'`{item}`' for item in suite.required_tasks) or 'none'}",
        f"- Optional tasks: {', '.join(f'`{item}`' for item in suite.optional_tasks) or 'none'}",
        "",
        suite.description or "No description recorded.",
        "",
        "## Benchmark Records",
        "",
    ]
    if benchmarks:
        lines.extend([f"- `{record.id}`: {record.name}" for record in benchmarks])
    else:
        lines.append("- none")
    missing = [benchmark_id for benchmark_id in suite.benchmark_ids if benchmark_id not in benchmark_ids]
    if missing:
        blockers.extend(f"Suite references missing benchmark `{benchmark_id}`." for benchmark_id in missing)
    lines.extend(["", "## Readiness Blockers", ""])
    lines.extend([f"- {item}" for item in blockers] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"
