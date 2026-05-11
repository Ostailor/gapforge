"""Curate selected benchmark related-work paper attachments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_completion import _category_score, _is_real_paper
from gapforge.selected_benchmark.related_work_search import RequiredRelatedWorkSearchManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

ALLOWED_RELATIONSHIPS = {
    "closest_prior_work",
    "background",
    "method_source",
    "benchmark_source",
    "analogy_source",
    "counterevidence",
    "baseline_source",
}


@dataclass(slots=True)
class RelatedWorkCategoryAttachment:
    id: str
    benchmark_id: str
    category: str
    paper_id: str
    relationship: str = "background"
    relevance_score: float = 0.0
    curator: str = ""
    evidence_span_ids: list[str] = field(default_factory=list)
    notes: str = ""
    status: str = "needs_review"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-curation"))


@dataclass(slots=True)
class RelatedWorkCurationReport:
    id: str
    benchmark_id: str
    category_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    accepted_paper_count: int = 0
    rejected_paper_count: int = 0
    closest_prior_work_ids: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-curation"))


class RelatedWorkCurationManager:
    """Attach, reject, waive, and report curated related-work paper records."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def attach_paper(
        self,
        benchmark_id: str,
        *,
        category: str,
        paper_id: str,
        relationship: str = "background",
        relevance_score: float | None = None,
        curator: str = "",
        evidence_span_ids: list[str] | None = None,
        notes: str = "",
    ) -> RelatedWorkCategoryAttachment:
        if category not in REQUIRED_RELATED_WORK_CATEGORIES:
            raise ValueError(f"Unknown related-work category: {category}")
        if relationship not in ALLOWED_RELATIONSHIPS:
            raise ValueError(f"Unknown related-work relationship: {relationship}")
        paper = self._resolve_paper(benchmark_id, paper_id)
        real = _is_real_paper(paper)
        score = relevance_score if relevance_score is not None else min(1.0, max(0.1, _category_score(category, paper) / 4))
        status = "accepted" if real else "needs_review"
        attachment_notes = notes
        if not real:
            attachment_notes = _join_notes(
                notes,
                "Paper is fallback, fixture, or lacks traceable metadata; it cannot complete the category.",
            )
        attachment = RelatedWorkCategoryAttachment(
            id=_attachment_id(benchmark_id, category, paper_id),
            benchmark_id=benchmark_id,
            category=category,
            paper_id=paper_id,
            relationship=relationship,
            relevance_score=score,
            curator=curator,
            evidence_span_ids=evidence_span_ids or [],
            notes=attachment_notes,
            status=status,
            provenance=Provenance(
                created_by_skill="selected-related-work-curation",
                source_ids=[benchmark_id, paper_id],
                timestamp=utc_now_iso(),
                reasoning_summary=f"Curated paper `{paper_id}` for required related-work category `{category}`.",
            ),
        )
        attachments = self._replace_attachment(self.load_attachments(benchmark_id), attachment)
        self._write_attachments(benchmark_id, attachments)
        self.report(benchmark_id)
        return attachment

    def reject_paper(self, benchmark_id: str, *, paper_id: str, reason: str, curator: str = "") -> list[RelatedWorkCategoryAttachment]:
        if not reason.strip():
            raise ValueError("Rejected related-work papers require a reason.")
        self._resolve_paper(benchmark_id, paper_id)
        attachments = self.load_attachments(benchmark_id)
        matching = [attachment for attachment in attachments if attachment.paper_id == paper_id]
        if not matching:
            matching = [
                RelatedWorkCategoryAttachment(
                    id=_attachment_id(benchmark_id, "uncategorized", paper_id),
                    benchmark_id=benchmark_id,
                    category="uncategorized",
                    paper_id=paper_id,
                    curator=curator,
                )
            ]
        rejected: list[RelatedWorkCategoryAttachment] = []
        for attachment in matching:
            updated = RelatedWorkCategoryAttachment(
                id=attachment.id,
                benchmark_id=attachment.benchmark_id,
                category=attachment.category,
                paper_id=attachment.paper_id,
                relationship=attachment.relationship,
                relevance_score=attachment.relevance_score,
                curator=curator or attachment.curator,
                evidence_span_ids=list(attachment.evidence_span_ids),
                notes=_join_notes(attachment.notes, reason),
                status="rejected",
                provenance=Provenance(
                    created_by_skill="selected-related-work-curation",
                    source_ids=[benchmark_id, paper_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary=f"Rejected related-work paper `{paper_id}` with a curator-supplied reason.",
                ),
            )
            attachments = self._replace_attachment(attachments, updated)
            rejected.append(updated)
        self._write_attachments(benchmark_id, attachments)
        self.report(benchmark_id)
        return rejected

    def waive_category(self, benchmark_id: str, *, category: str, reason: str, curator: str) -> RelatedWorkCurationReport:
        if category not in REQUIRED_RELATED_WORK_CATEGORIES:
            raise ValueError(f"Unknown related-work category: {category}")
        if not reason.strip():
            raise ValueError("Related-work category waiver reason is required.")
        if not curator.strip():
            raise ValueError("Related-work category waiver requires a human curator.")
        waivers = self._load_waivers(benchmark_id)
        waivers[category] = {"reason": reason, "curator": curator, "timestamp": utc_now_iso()}
        self._write_waivers(benchmark_id, waivers)
        return self.report(benchmark_id)

    def auto_curate(self, benchmark_id: str, *, curator: str = "auto-curation") -> RelatedWorkCurationReport:
        campaign = RequiredRelatedWorkSearchManager(self.config).load_or_plan(benchmark_id)
        for category, search in campaign.category_searches.items():
            for index, paper_id in enumerate(search.accepted_paper_ids):
                relationship = "closest_prior_work" if index == 0 else "background"
                self.attach_paper(
                    benchmark_id,
                    category=category,
                    paper_id=paper_id,
                    relationship=relationship,
                    curator=curator,
                    notes="Auto-curated from executable related-work search accepted results.",
                )
        return self.report(benchmark_id)

    def report(self, benchmark_id: str) -> RelatedWorkCurationReport:
        attachments = self.load_attachments(benchmark_id)
        paper_by_id = self._paper_by_id(benchmark_id)
        waivers = self._load_waivers(benchmark_id)
        category_statuses: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        missing: list[str] = []
        closest_ids: list[str] = []
        for category in REQUIRED_RELATED_WORK_CATEGORIES:
            category_attachments = [attachment for attachment in attachments if attachment.category == category]
            accepted_real = [
                attachment
                for attachment in category_attachments
                if attachment.status == "accepted" and _is_real_paper(paper_by_id.get(attachment.paper_id, _missing_paper()))
            ]
            rejected = [attachment for attachment in category_attachments if attachment.status == "rejected"]
            needs_review = [attachment for attachment in category_attachments if attachment.status == "needs_review"]
            if category in waivers:
                status = "waived"
            elif accepted_real:
                status = "complete"
            else:
                status = "missing"
                missing.append(category)
            closest = [
                attachment.paper_id for attachment in accepted_real if attachment.relationship in {"closest_prior_work", "counterevidence"}
            ]
            closest_ids.extend(attachment.paper_id for attachment in accepted_real if attachment.relationship == "closest_prior_work")
            if needs_review:
                warnings.append(f"{category} has paper attachments that need review and do not complete the category.")
            if status == "missing" and not category_attachments:
                warnings.append(f"{category} has no curated accepted real paper.")
            category_statuses[category] = {
                "status": status,
                "accepted_paper_ids": [attachment.paper_id for attachment in accepted_real],
                "rejected_paper_ids": [attachment.paper_id for attachment in rejected],
                "needs_review_paper_ids": [attachment.paper_id for attachment in needs_review],
                "closest_prior_work_ids": closest,
                "waiver": waivers.get(category, {}),
            }
        accepted_ids = sorted(
            {
                attachment.paper_id
                for attachment in attachments
                if attachment.status == "accepted" and _is_real_paper(paper_by_id.get(attachment.paper_id, _missing_paper()))
            }
        )
        rejected_ids = sorted({attachment.paper_id for attachment in attachments if attachment.status == "rejected"})
        report = RelatedWorkCurationReport(
            id=f"related-work-curation-report-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            category_statuses=category_statuses,
            accepted_paper_count=len(accepted_ids),
            rejected_paper_count=len(rejected_ids),
            closest_prior_work_ids=sorted(set(closest_ids)),
            missing_categories=missing,
            warnings=_dedupe(warnings),
            provenance=Provenance(
                created_by_skill="selected-related-work-curation",
                source_ids=[benchmark_id, *accepted_ids, *rejected_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Rendered related-work curation status from accepted, rejected, and waived category records.",
            ),
        )
        self._write_report(report)
        return report

    def load_attachments(self, benchmark_id: str) -> list[RelatedWorkCategoryAttachment]:
        path = self.attachments_path(benchmark_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RelatedWorkCategoryAttachment, item) for item in payload]

    def attachments_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._curation_dir(spec.project_id) / "related_work_attachments.json"

    def report_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._curation_dir(spec.project_id) / "related_work_curation_report.json"

    def _resolve_paper(self, benchmark_id: str, paper_id: str) -> Paper:
        paper = self._paper_by_id(benchmark_id).get(paper_id)
        if paper is None:
            raise ValueError(f"Related-work paper ID `{paper_id}` is not a known Paper record; fake citations are rejected.")
        return paper

    def _paper_by_id(self, benchmark_id: str) -> dict[str, Paper]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _replace_attachment(
        self,
        attachments: list[RelatedWorkCategoryAttachment],
        attachment: RelatedWorkCategoryAttachment,
    ) -> list[RelatedWorkCategoryAttachment]:
        return [*[_item for _item in attachments if _item.id != attachment.id], attachment]

    def _write_attachments(self, benchmark_id: str, attachments: list[RelatedWorkCategoryAttachment]) -> None:
        path = self.attachments_path(benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([to_plain(attachment) for attachment in attachments], indent=2) + "\n", encoding="utf-8")

    def _load_waivers(self, benchmark_id: str) -> dict[str, dict[str, str]]:
        path = self._waiver_path(benchmark_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_waivers(self, benchmark_id: str, waivers: dict[str, dict[str, str]]) -> None:
        path = self._waiver_path(benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(waivers, indent=2) + "\n", encoding="utf-8")

    def _waiver_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._curation_dir(spec.project_id) / "related_work_category_waivers.json"

    def _write_report(self, report: RelatedWorkCurationReport) -> None:
        path = self.report_path(report.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_related_work_curation_report(report), encoding="utf-8")

    def _curation_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "related_work_curation"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_related_work_curation_report(report: RelatedWorkCurationReport) -> str:
    lines = [
        "# Related-Work Curation Report",
        "",
        f"- Benchmark ID: `{report.benchmark_id}`",
        f"- Accepted paper count: {report.accepted_paper_count}",
        f"- Rejected paper count: {report.rejected_paper_count}",
        f"- Closest prior work IDs: {', '.join(report.closest_prior_work_ids) or 'none'}",
        f"- Missing categories: {', '.join(report.missing_categories) or 'none'}",
        "",
        "## Categories",
        "",
    ]
    for category, status in report.category_statuses.items():
        lines.extend(
            [
                f"### {category}",
                f"- Status: `{status.get('status', 'missing')}`",
                f"- Accepted paper IDs: {', '.join(status.get('accepted_paper_ids', [])) or 'none'}",
                f"- Rejected paper IDs: {', '.join(status.get('rejected_paper_ids', [])) or 'none'}",
                f"- Needs-review paper IDs: {', '.join(status.get('needs_review_paper_ids', [])) or 'none'}",
                f"- Closest prior-work IDs: {', '.join(status.get('closest_prior_work_ids', [])) or 'none'}",
            ]
        )
        waiver = status.get("waiver", {})
        if waiver:
            lines.append(f"- Waiver: {waiver.get('reason', '')} ({waiver.get('curator', 'unknown curator')})")
        lines.append("")
    lines.extend(["## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.warnings] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Category completion requires accepted real paper records or a human waiver with reason.",
            "- Counterevidence and closest prior work must remain visible.",
            "- Unknown paper IDs are rejected as fake citations.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _attachment_id(benchmark_id: str, category: str, paper_id: str) -> str:
    return f"related-work-attachment-{slugify(benchmark_id)}-{slugify(category)}-{slugify(paper_id)}"


def _join_notes(existing: str, note: str) -> str:
    if not existing:
        return note
    if not note:
        return existing
    return f"{existing} {note}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _missing_paper() -> Paper:
    return Paper(id="", title="", authors=[], abstract="", year=0, source="missing")
