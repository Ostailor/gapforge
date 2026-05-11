"""Refresh closest-prior-work dossier from curated selected benchmark related work."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager
from gapforge.selected_benchmark.related_work_reading import RelatedWorkReadingManager, RelatedWorkReadingStatus
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

COMPARISON_DIMENSIONS = [
    "problem setting",
    "low-FPR/specificity focus",
    "sequential evaluation",
    "multi-agent collusion/covert coordination",
    "benchmark/protocol contribution",
    "observability modes",
    "honest null distribution",
    "collusive alternatives",
    "baselines",
    "metrics/statistics",
]


@dataclass(slots=True)
class SelectedBenchmarkPriorWorkDossier:
    id: str
    benchmark_id: str
    closest_prior_work_ids: list[str] = field(default_factory=list)
    comparison_table: list[dict[str, Any]] = field(default_factory=list)
    what_is_new: list[str] = field(default_factory=list)
    what_is_not_new: list[str] = field(default_factory=list)
    decisive_difference_needed: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    novelty_status: str = "unknown"
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-prior-work-refresh"))


class SelectedBenchmarkPriorWorkRefreshManager:
    """Build a novelty-positioning dossier from curated prior work."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.curation_manager = RelatedWorkCurationManager(config)
        self.reading_manager = RelatedWorkReadingManager(config)

    def refresh(self, benchmark_id: str) -> SelectedBenchmarkPriorWorkDossier:
        curation_report = self.curation_manager.report(benchmark_id)
        readings = self.reading_manager.load_statuses(benchmark_id)
        if not readings:
            readings = self.reading_manager.read(benchmark_id)
        paper_by_id = self._paper_by_id(benchmark_id)
        closest_ids = list(curation_report.closest_prior_work_ids)
        closest_text = _combined_prior_text(closest_ids, readings, paper_by_id)
        comparison_table = [_comparison_row(dimension, closest_text) for dimension in COMPARISON_DIMENSIONS]
        covered_dimensions = [row for row in comparison_table if row["prior_work_coverage"] == "covered"]
        missing_dimensions = [row for row in comparison_table if row["prior_work_coverage"] != "covered"]
        what_is_new = _what_is_new(missing_dimensions)
        what_is_not_new = _what_is_not_new(covered_dimensions, closest_ids)
        decisive_difference = _decisive_difference(curation_report.missing_categories, missing_dimensions)
        counterevidence = _counterevidence(readings, self.curation_manager.load_attachments(benchmark_id))
        novelty_status = _novelty_status(
            missing_categories=curation_report.missing_categories,
            covered_count=len(covered_dimensions),
            closest_prior_work_ids=closest_ids,
            decisive_difference=decisive_difference,
        )
        confidence = _confidence(novelty_status, readings, curation_report.missing_categories)
        dossier = SelectedBenchmarkPriorWorkDossier(
            id=f"selected-prior-work-dossier-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            closest_prior_work_ids=closest_ids,
            comparison_table=comparison_table,
            what_is_new=what_is_new,
            what_is_not_new=what_is_not_new,
            decisive_difference_needed=decisive_difference,
            counterevidence=counterevidence,
            novelty_status=novelty_status,
            confidence=confidence,
            provenance=Provenance(
                created_by_skill="selected-prior-work-refresh",
                source_ids=[benchmark_id, *closest_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Refreshed selected benchmark closest-prior-work dossier from curated attachments and reading evidence.",
            ),
        )
        self._write_dossier(dossier)
        return dossier

    def load_or_refresh(self, benchmark_id: str) -> SelectedBenchmarkPriorWorkDossier:
        path = self.dossier_path(benchmark_id)
        if not path.exists():
            return self.refresh(benchmark_id)
        return from_dict(SelectedBenchmarkPriorWorkDossier, json.loads(path.read_text(encoding="utf-8")))

    def dossier_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._dossier_dir(spec.project_id) / "selected_prior_work_dossier.json"

    def _paper_by_id(self, benchmark_id: str) -> dict[str, Paper]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _write_dossier(self, dossier: SelectedBenchmarkPriorWorkDossier) -> None:
        path = self.dossier_path(dossier.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(dossier), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_selected_prior_work_dossier(dossier), encoding="utf-8")

    def _dossier_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "prior_work_dossier"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_selected_prior_work_dossier(dossier: SelectedBenchmarkPriorWorkDossier) -> str:
    lines = [
        "# Selected Benchmark Prior-Work Dossier",
        "",
        f"- Benchmark ID: `{dossier.benchmark_id}`",
        f"- Novelty status: `{dossier.novelty_status}`",
        f"- Confidence: `{dossier.confidence}`",
        f"- Closest prior work IDs: {', '.join(dossier.closest_prior_work_ids) or 'none'}",
        "",
        "## Comparison Table",
        "",
        "| Dimension | Prior-work coverage | Selected benchmark claim | Difference needed | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in dossier.comparison_table:
        lines.append(
            "| {dimension} | {prior_work_coverage} | {selected_benchmark_claim} | {difference_needed} | {evidence} |".format(
                dimension=row.get("dimension", ""),
                prior_work_coverage=row.get("prior_work_coverage", ""),
                selected_benchmark_claim=row.get("selected_benchmark_claim", ""),
                difference_needed=row.get("difference_needed", ""),
                evidence=row.get("evidence", ""),
            )
        )
    lines.extend(["", "## What Is New", ""])
    lines.extend([f"- {item}" for item in dossier.what_is_new] or ["- none"])
    lines.extend(["", "## What Is Not New", ""])
    lines.extend([f"- {item}" for item in dossier.what_is_not_new] or ["- none"])
    lines.extend(["", "## Decisive Difference Needed", ""])
    lines.extend([f"- {item}" for item in dossier.decisive_difference_needed] or ["- none"])
    lines.extend(["", "## Counterevidence", ""])
    lines.extend([f"- {item}" for item in dossier.counterevidence] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _combined_prior_text(
    closest_ids: list[str],
    readings: list[RelatedWorkReadingStatus],
    paper_by_id: dict[str, Paper],
) -> str:
    parts: list[str] = []
    for paper_id in closest_ids:
        paper = paper_by_id.get(paper_id)
        if paper:
            parts.extend([paper.title, paper.abstract])
        for reading in readings:
            if reading.paper_id == paper_id:
                parts.extend(reading.extracted_contributions)
                parts.extend(reading.extracted_limitations)
                parts.append(reading.relevance_to_selected_benchmark)
    return " ".join(part for part in parts if part).lower()


def _comparison_row(dimension: str, text: str) -> dict[str, str]:
    keywords = _dimension_keywords(dimension)
    positive_text = _drop_negated_sentences(text)
    hit_count = sum(1 for keyword in keywords if keyword in positive_text)
    coverage = "covered" if hit_count >= _coverage_threshold(dimension) else "partial" if hit_count else "not_found"
    return {
        "dimension": dimension,
        "prior_work_coverage": coverage,
        "selected_benchmark_claim": _selected_claim(dimension),
        "difference_needed": "Show selected benchmark adds this dimension." if coverage == "covered" else "Preserve as claimed difference.",
        "evidence": "keyword evidence from curated closest-prior-work readings" if hit_count else "no matching closest-prior-work evidence",
    }


def _drop_negated_sentences(text: str) -> str:
    sentences = [part.strip() for part in text.replace("?", ".").replace("!", ".").split(".") if part.strip()]
    return " ".join(
        sentence for sentence in sentences if not any(marker in sentence for marker in ["does not", "not solve", "not evaluate", "without"])
    )


def _dimension_keywords(dimension: str) -> list[str]:
    return {
        "problem setting": ["collusion audit", "collusion audits", "detector", "audit"],
        "low-FPR/specificity focus": ["low-fpr", "low false-positive", "low false positive", "specificity", "false alarm"],
        "sequential evaluation": ["sequential", "change-point", "change point", "repeated"],
        "multi-agent collusion/covert coordination": ["multi-agent", "collusion", "covert coordination", "covert"],
        "benchmark/protocol contribution": ["benchmark", "protocol", "evaluation"],
        "observability modes": ["observability", "transcript", "action-only"],
        "honest null distribution": ["honest null", "benign", "null distribution"],
        "collusive alternatives": ["collusive alternative", "collusive alternatives", "collusive"],
        "baselines": ["baseline", "baselines"],
        "metrics/statistics": ["metric", "metrics", "statistics", "statistical"],
    }[dimension]


def _coverage_threshold(dimension: str) -> int:
    return 1 if dimension in {"baselines", "metrics/statistics", "benchmark/protocol contribution"} else 2


def _selected_claim(dimension: str) -> str:
    return {
        "problem setting": "Collusion audit benchmark for the selected multi-agent monitoring problem.",
        "low-FPR/specificity focus": "Low-FPR specificity-centered evaluation.",
        "sequential evaluation": "Sequential evaluation over repeated audit windows.",
        "multi-agent collusion/covert coordination": "Multi-agent collusion and covert-coordination threat framing.",
        "benchmark/protocol contribution": "Benchmark/protocol contribution rather than deployment-valid monitor claim.",
        "observability modes": "Transcript-visible and action-only observability modes.",
        "honest null distribution": "Explicit honest null distribution and hard negatives.",
        "collusive alternatives": "Explicit collusive alternatives.",
        "baselines": "Baseline comparisons and missing-baseline blockers.",
        "metrics/statistics": "Low-FPR metrics, uncertainty, and sequential statistics.",
    }[dimension]


def _what_is_new(missing_dimensions: list[dict[str, Any]]) -> list[str]:
    if not missing_dimensions:
        return []
    labels = [str(row["dimension"]) for row in missing_dimensions]
    if any(label in labels for label in ["sequential evaluation", "low-FPR/specificity focus", "benchmark/protocol contribution"]):
        return ["Potential novelty depends on the sequential low-FPR benchmark combination and its supported evidence."]
    if "multi-agent collusion/covert coordination" in labels:
        return ["Potential novelty depends on applying sequential low-FPR evaluation to multi-agent collusion/covert coordination."]
    return [f"Potentially new relative to closest prior work: {', '.join(labels)}."]


def _what_is_not_new(covered_dimensions: list[dict[str, Any]], closest_ids: list[str]) -> list[str]:
    if not covered_dimensions:
        return []
    dimensions = ", ".join(str(row["dimension"]) for row in covered_dimensions)
    prefix = f"Closest prior work `{', '.join(closest_ids)}`" if closest_ids else "Closest prior work"
    return [f"{prefix} already covers: {dimensions}."]


def _decisive_difference(missing_categories: list[str], missing_dimensions: list[dict[str, Any]]) -> list[str]:
    if missing_categories:
        return [f"Complete or waive missing related-work categories before novelty can be assessed: {', '.join(missing_categories)}."]
    if not missing_dimensions:
        return ["Show a decisive contribution beyond a prior benchmark that appears to cover the core claim."]
    dimensions = ", ".join(str(row["dimension"]) for row in missing_dimensions)
    return [f"Demonstrate that the selected benchmark materially adds: {dimensions}."]


def _counterevidence(readings: list[RelatedWorkReadingStatus], attachments: list[Any]) -> list[str]:
    counter_ids = {attachment.paper_id for attachment in attachments if attachment.relationship == "counterevidence"}
    items = [reading.relevance_to_selected_benchmark for reading in readings if reading.paper_id in counter_ids]
    for reading in readings:
        items.extend(reading.extracted_limitations)
    return _dedupe([item for item in items if item])


def _novelty_status(
    *,
    missing_categories: list[str],
    covered_count: int,
    closest_prior_work_ids: list[str],
    decisive_difference: list[str],
) -> str:
    if missing_categories:
        return "unknown"
    if closest_prior_work_ids and covered_count >= 8:
        return "duplicate"
    if closest_prior_work_ids and covered_count >= 6:
        return "weak"
    if closest_prior_work_ids and decisive_difference:
        return "plausible"
    if closest_prior_work_ids:
        return "strong"
    return "unknown"


def _confidence(novelty_status: str, readings: list[RelatedWorkReadingStatus], missing_categories: list[str]) -> str:
    if missing_categories or novelty_status == "unknown":
        return "low"
    if any(reading.confidence == "high" for reading in readings):
        return "high"
    if readings:
        return "medium"
    return "low"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
