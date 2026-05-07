"""Aggregate benchmark result records."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import AggregateResult, Provenance, ResultRecord, to_plain
from gapforge.results.database import ResultDatabaseBuilder
from gapforge.state import utc_now_iso


class ResultAggregator:
    """Aggregate result rows without mixing smoke and main runs by default."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.database = ResultDatabaseBuilder(config)

    def aggregate(self, workspace_id: str, *, include_smoke: bool = False) -> list[AggregateResult]:
        table = self.database.load_or_build(workspace_id)
        groups: dict[tuple[str, str, str, str, str], list[ResultRecord]] = defaultdict(list)
        for row in table.rows:
            if row.run_type == "smoke" and not include_smoke:
                continue
            key = (row.benchmark_id, row.dataset_id, row.baseline_id, row.metric_id, row.run_type)
            groups[key].append(row)
        aggregates = [_aggregate_group(workspace_id, key, rows) for key, rows in sorted(groups.items())]
        self._write_aggregates(workspace_id, aggregates)
        return aggregates

    def _write_aggregates(self, workspace_id: str, aggregates: list[AggregateResult]) -> None:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "aggregate_results.json").write_text(json.dumps(to_plain(aggregates), indent=2) + "\n", encoding="utf-8")
        (reports / "aggregate_results.md").write_text(render_aggregate_results_markdown(aggregates), encoding="utf-8")


def render_aggregate_results_markdown(aggregates: list[AggregateResult]) -> str:
    lines = [
        "# Aggregate Results",
        "",
        "| Aggregate | Metric | Baseline | N | Seeds | Mean | Std | CI |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | --- |",
    ]
    if not aggregates:
        lines.append("| none | none | none | 0 | none |  |  |  |")
        return "\n".join(lines).rstrip() + "\n"
    for aggregate in aggregates:
        lines.append(
            f"| `{aggregate.id}` | `{aggregate.metric_id}` | `{aggregate.baseline_id or 'missing'}` | {aggregate.n} | "
            f"{', '.join(str(seed) for seed in aggregate.seeds) or 'none'} | {aggregate.mean:g} | {aggregate.std:g} | "
            f"{_format_ci(aggregate.confidence_interval)} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _aggregate_group(workspace_id: str, key: tuple[str, str, str, str, str], rows: list[ResultRecord]) -> AggregateResult:
    benchmark_id, dataset_id, baseline_id, metric_id, run_type = key
    values = [row.value for row in rows]
    aggregate_mean = mean(values)
    aggregate_std = stdev(values) if len(values) > 1 else 0.0
    margin = 1.96 * aggregate_std / math.sqrt(len(values)) if len(values) > 1 else 0.0
    seeds = sorted(set(row.seed for row in rows))
    return AggregateResult(
        id=f"aggregate-{benchmark_id or 'benchmark'}-{dataset_id or 'dataset'}-{baseline_id or 'missing'}-{metric_id}-{run_type}".replace(
            " ", "-"
        ),
        workspace_id=workspace_id,
        metric_id=metric_id,
        baseline_id=baseline_id,
        mean=round(aggregate_mean, 12),
        std=round(aggregate_std, 12),
        confidence_interval=[round(aggregate_mean - margin, 12), round(aggregate_mean + margin, 12)] if len(values) > 1 else [],
        n=len(values),
        seeds=seeds,
        provenance=Provenance(
            created_by_skill="result-aggregation",
            source_ids=[workspace_id, *[row.id for row in rows]],
            timestamp=utc_now_iso(),
            reasoning_summary="Aggregated result records with run-type separation so smoke results cannot masquerade as main results.",
        ),
    )


def _format_ci(values: list[float]) -> str:
    if not values:
        return "missing"
    if len(values) == 2:
        return f"[{values[0]:g}, {values[1]:g}]"
    return ", ".join(f"{value:g}" for value in values)
