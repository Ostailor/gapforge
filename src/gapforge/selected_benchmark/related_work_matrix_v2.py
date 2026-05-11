"""Manuscript-grade related-work matrix for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_completion import _is_real_paper
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCategoryAttachment, RelatedWorkCurationManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

RELATED_WORK_MATRIX_V2_RELATIONSHIPS = [
    "directly solves",
    "adjacent benchmark",
    "evaluation protocol source",
    "low-FPR/statistical source",
    "multi-agent/collusion source",
    "covert-channel source",
    "anomaly detection source",
    "specificity/screening source",
    "baseline source",
    "counterevidence",
    "background",
]


@dataclass(slots=True)
class SelectedBenchmarkRelatedWorkMatrixV2Entry:
    id: str
    benchmark_id: str
    category: str
    paper_id: str
    title: str
    relationship: str
    relevance_score: float = 0.0
    must_cite: bool = False
    baseline_source: bool = False
    reviewer_omission_risk: str = ""
    evidence_span_ids: list[str] = field(default_factory=list)
    notes: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-matrix-v2"))


@dataclass(slots=True)
class SelectedBenchmarkRelatedWorkMatrixV2:
    id: str
    benchmark_id: str
    entries: list[SelectedBenchmarkRelatedWorkMatrixV2Entry] = field(default_factory=list)
    category_coverage: dict[str, dict[str, Any]] = field(default_factory=dict)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    must_cite_ids: list[str] = field(default_factory=list)
    baseline_source_ids: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    reviewer_omission_risks: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-matrix-v2"))


class SelectedBenchmarkRelatedWorkMatrixV2Manager:
    """Build matrix-v2 from accepted curation records."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.curation_manager = RelatedWorkCurationManager(config)

    def build(self, benchmark_id: str) -> SelectedBenchmarkRelatedWorkMatrixV2:
        curation_report = self.curation_manager.report(benchmark_id)
        attachments = self.curation_manager.load_attachments(benchmark_id)
        paper_by_id = self._paper_by_id(benchmark_id)
        entries = [
            self._entry(benchmark_id, attachment, paper_by_id[attachment.paper_id])
            for attachment in attachments
            if _accepted_real_attachment(attachment, paper_by_id)
        ]
        category_coverage = _category_coverage(entries, curation_report.missing_categories)
        closest_prior_work_ids = _dedupe(
            [
                attachment.paper_id
                for attachment in attachments
                if attachment.status == "accepted" and attachment.relationship == "closest_prior_work"
            ]
        )
        must_cite_ids = _dedupe([entry.paper_id for entry in entries if entry.must_cite])
        baseline_source_ids = _dedupe([entry.paper_id for entry in entries if entry.baseline_source])
        reviewer_omission_risks = _reviewer_omission_risks(entries, curation_report.missing_categories)
        matrix = SelectedBenchmarkRelatedWorkMatrixV2(
            id=f"selected-related-work-matrix-v2-{benchmark_id}",
            benchmark_id=benchmark_id,
            entries=entries,
            category_coverage=category_coverage,
            closest_prior_work_ids=closest_prior_work_ids,
            must_cite_ids=must_cite_ids,
            baseline_source_ids=baseline_source_ids,
            missing_categories=list(curation_report.missing_categories),
            reviewer_omission_risks=reviewer_omission_risks,
            provenance=Provenance(
                created_by_skill="selected-related-work-matrix-v2",
                source_ids=[benchmark_id, *[entry.paper_id for entry in entries]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Built manuscript-grade related-work matrix from accepted curated related-work papers, "
                    "including must-cite, baseline-source, and reviewer-risk signals."
                ),
            ),
        )
        self._write_matrix(matrix)
        return matrix

    def load_or_build(self, benchmark_id: str) -> SelectedBenchmarkRelatedWorkMatrixV2:
        path = self.matrix_path(benchmark_id)
        if not path.exists():
            return self.build(benchmark_id)
        return from_dict(SelectedBenchmarkRelatedWorkMatrixV2, json.loads(path.read_text(encoding="utf-8")))

    def must_cite_report(self, benchmark_id: str) -> str:
        matrix = self.load_or_build(benchmark_id)
        return render_must_cite_report(matrix)

    def matrix_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._matrix_dir(spec.project_id) / "related_work_matrix_v2.json"

    def _entry(
        self,
        benchmark_id: str,
        attachment: RelatedWorkCategoryAttachment,
        paper: Paper,
    ) -> SelectedBenchmarkRelatedWorkMatrixV2Entry:
        relationship = _matrix_relationship(attachment, paper)
        baseline_source = relationship == "baseline source"
        must_cite = _must_cite(relationship, attachment)
        return SelectedBenchmarkRelatedWorkMatrixV2Entry(
            id=f"selected-related-work-matrix-v2-entry-{slugify(benchmark_id)}-{slugify(attachment.paper_id)}",
            benchmark_id=benchmark_id,
            category=attachment.category,
            paper_id=attachment.paper_id,
            title=paper.title,
            relationship=relationship,
            relevance_score=attachment.relevance_score,
            must_cite=must_cite,
            baseline_source=baseline_source,
            reviewer_omission_risk=_entry_omission_risk(relationship, attachment),
            evidence_span_ids=list(attachment.evidence_span_ids),
            notes=attachment.notes,
            provenance=Provenance(
                created_by_skill="selected-related-work-matrix-v2",
                source_ids=[benchmark_id, attachment.paper_id, attachment.id],
                timestamp=utc_now_iso(),
                reasoning_summary=f"Mapped curated related-work attachment to matrix-v2 relationship `{relationship}`.",
            ),
        )

    def _paper_by_id(self, benchmark_id: str) -> dict[str, Paper]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _write_matrix(self, matrix: SelectedBenchmarkRelatedWorkMatrixV2) -> None:
        path = self.matrix_path(matrix.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(matrix), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_related_work_matrix_v2(matrix), encoding="utf-8")
        (path.parent / "must_cite_paper_ids.json").write_text(json.dumps(matrix.must_cite_ids, indent=2) + "\n", encoding="utf-8")
        (path.parent / "must_cite.md").write_text(render_must_cite_report(matrix), encoding="utf-8")
        (path.parent / "baseline_source_paper_ids.json").write_text(
            json.dumps(matrix.baseline_source_ids, indent=2) + "\n",
            encoding="utf-8",
        )

    def _matrix_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "related_work_matrix_v2"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_related_work_matrix_v2(matrix: SelectedBenchmarkRelatedWorkMatrixV2) -> str:
    lines = [
        "# Selected Benchmark Related-Work Matrix V2",
        "",
        f"- Benchmark ID: `{matrix.benchmark_id}`",
        f"- Entries: {len(matrix.entries)}",
        f"- Must-cite IDs: {', '.join(matrix.must_cite_ids) or 'none'}",
        f"- Baseline source IDs: {', '.join(matrix.baseline_source_ids) or 'none'}",
        f"- Missing categories: {', '.join(matrix.missing_categories) or 'none'}",
        "",
        "## Entries",
        "",
        "| Category | Paper ID | Relationship | Must cite | Baseline source | Reviewer omission risk |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in matrix.entries:
        lines.append(
            f"| {entry.category} | `{entry.paper_id}` | {entry.relationship} | {entry.must_cite} | "
            f"{entry.baseline_source} | {entry.reviewer_omission_risk or 'none'} |"
        )
    lines.extend(["", "## Category Coverage", ""])
    for category, coverage in matrix.category_coverage.items():
        lines.append(f"- {category}: `{coverage.get('status', 'missing')}` ({', '.join(coverage.get('paper_ids', [])) or 'no papers'})")
    lines.extend(["", "## Reviewer Omission Risks", ""])
    lines.extend([f"- {risk}" for risk in matrix.reviewer_omission_risks] or ["- none"])
    lines.extend(["", "## Publication-Readiness Signals", ""])
    lines.extend(
        [
            "- Missing categories block publication readiness.",
            "- Directly-solving papers trigger no-go/revise until the contribution is reframed.",
            "- Baseline-source papers should feed the baseline plan.",
            "- Must-cite papers must appear in the manuscript bibliography.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_must_cite_report(matrix: SelectedBenchmarkRelatedWorkMatrixV2) -> str:
    lines = [
        "# Selected Benchmark Must-Cite Papers",
        "",
        f"- Benchmark ID: `{matrix.benchmark_id}`",
        f"- Must-cite count: {len(matrix.must_cite_ids)}",
        "",
        "## Must-Cite IDs",
        "",
    ]
    lines.extend([f"- `{paper_id}`" for paper_id in matrix.must_cite_ids] or ["- none"])
    lines.extend(
        [
            "",
            "## Bibliography Rule",
            "",
            "- Every must-cite paper must appear in the manuscript bibliography before readiness can pass.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _accepted_real_attachment(attachment: RelatedWorkCategoryAttachment, paper_by_id: dict[str, Paper]) -> bool:
    paper = paper_by_id.get(attachment.paper_id)
    return attachment.status == "accepted" and paper is not None and _is_real_paper(paper)


def _category_coverage(
    entries: list[SelectedBenchmarkRelatedWorkMatrixV2Entry],
    missing_categories: list[str],
) -> dict[str, dict[str, Any]]:
    by_category: dict[str, list[SelectedBenchmarkRelatedWorkMatrixV2Entry]] = {
        category: [] for category in REQUIRED_RELATED_WORK_CATEGORIES
    }
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry)
    return {
        category: {
            "status": "missing" if category in missing_categories or not by_category.get(category) else "complete",
            "paper_ids": [entry.paper_id for entry in by_category.get(category, [])],
            "relationships": [entry.relationship for entry in by_category.get(category, [])],
        }
        for category in REQUIRED_RELATED_WORK_CATEGORIES
    }


def _matrix_relationship(attachment: RelatedWorkCategoryAttachment, paper: Paper) -> str:
    text = " ".join([attachment.notes, paper.title, paper.abstract]).lower()
    if "directly solves" in text or "already solves" in text or "covers core contribution" in text:
        return "directly solves"
    if attachment.relationship == "baseline_source":
        return "baseline source"
    if attachment.relationship == "counterevidence":
        return "counterevidence"
    if attachment.relationship == "closest_prior_work":
        return "adjacent benchmark"
    if attachment.relationship == "benchmark_source" or attachment.category == "benchmark/evaluation protocol papers":
        return "evaluation protocol source"
    if attachment.category in {"low-FPR detection/evaluation", "sequential testing/change-point detection"}:
        return "low-FPR/statistical source"
    if attachment.category == "multi-agent collusion/covert coordination":
        return "multi-agent/collusion source"
    if attachment.category == "monitor evasion" or attachment.category == "cartel/covert-channel analogies if used":
        return "covert-channel source"
    if attachment.category == "anomaly detection specificity":
        return "anomaly detection source"
    if attachment.category == "medical screening specificity analogies if used":
        return "specificity/screening source"
    return "background"


def _must_cite(relationship: str, attachment: RelatedWorkCategoryAttachment) -> bool:
    if relationship in {"background"}:
        return attachment.relevance_score >= 0.75
    return relationship in {
        "directly solves",
        "adjacent benchmark",
        "evaluation protocol source",
        "low-FPR/statistical source",
        "baseline source",
        "counterevidence",
    }


def _entry_omission_risk(relationship: str, attachment: RelatedWorkCategoryAttachment) -> str:
    if relationship == "directly solves":
        return f"`{attachment.paper_id}` appears to directly solve the benchmark contribution; trigger no-go/revise."
    if relationship == "adjacent benchmark":
        return f"Omitting closest or adjacent benchmark `{attachment.paper_id}` risks an obvious-prior-work reviewer objection."
    if relationship == "baseline source":
        return f"Baseline-source paper `{attachment.paper_id}` should feed the baseline plan and bibliography."
    if relationship == "counterevidence":
        return f"Counterevidence paper `{attachment.paper_id}` must be preserved, cited, and addressed."
    if relationship in {"evaluation protocol source", "low-FPR/statistical source"}:
        return f"Omitting `{attachment.paper_id}` weakens methodological positioning for {attachment.category}."
    return ""


def _reviewer_omission_risks(
    entries: list[SelectedBenchmarkRelatedWorkMatrixV2Entry],
    missing_categories: list[str],
) -> list[str]:
    risks = [entry.reviewer_omission_risk for entry in entries if entry.reviewer_omission_risk]
    for category in missing_categories:
        risks.append(f"Missing category `{category}` blocks publication readiness.")
    if any(entry.relationship == "directly solves" for entry in entries):
        risks.append("A directly-solving prior paper is present; no-go/revise is required unless the contribution is reframed.")
    return _dedupe(risks)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
