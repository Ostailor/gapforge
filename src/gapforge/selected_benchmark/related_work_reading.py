"""Evidence-backed reading pass for selected benchmark related work."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.fulltext.sectionizer import create_evidence_span_from_quote
from gapforge.models import EvidenceSpan, Paper, PaperSection, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCategoryAttachment, RelatedWorkCurationManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


@dataclass(slots=True)
class RelatedWorkReadingStatus:
    id: str
    benchmark_id: str
    paper_id: str
    category: str
    source_basis: str = "metadata_only"
    sections_used: list[str] = field(default_factory=list)
    evidence_span_ids: list[str] = field(default_factory=list)
    extracted_contributions: list[str] = field(default_factory=list)
    extracted_limitations: list[str] = field(default_factory=list)
    relevance_to_selected_benchmark: str = ""
    confidence: str = "low"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-reading"))


class RelatedWorkReadingManager:
    """Read curated selected-benchmark related-work papers enough for positioning."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.curation_manager = RelatedWorkCurationManager(config)

    def read(self, benchmark_id: str, *, paper_id: str | None = None) -> list[RelatedWorkReadingStatus]:
        attachments = [
            attachment
            for attachment in self.curation_manager.load_attachments(benchmark_id)
            if attachment.status == "accepted" and (paper_id is None or attachment.paper_id == paper_id)
        ]
        statuses = [self._read_attachment(benchmark_id, attachment) for attachment in attachments]
        self._write_statuses(benchmark_id, statuses)
        return statuses

    def report(self, benchmark_id: str) -> str:
        statuses = self.load_statuses(benchmark_id)
        if not statuses:
            statuses = self.read(benchmark_id)
        rendered = render_related_work_reading_report(statuses)
        self.report_path(benchmark_id).write_text(rendered, encoding="utf-8")
        return rendered

    def load_statuses(self, benchmark_id: str) -> list[RelatedWorkReadingStatus]:
        path = self.statuses_path(benchmark_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RelatedWorkReadingStatus, item) for item in payload]

    def statuses_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._reading_dir(spec.project_id) / "related_work_reading_statuses.json"

    def report_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._reading_dir(spec.project_id) / "related_work_reading_report.md"

    def _read_attachment(self, benchmark_id: str, attachment: RelatedWorkCategoryAttachment) -> RelatedWorkReadingStatus:
        paper, sections, run_ids = self._paper_context(benchmark_id, attachment.paper_id)
        selected_sections = _select_sections(sections)
        blockers: list[str] = []
        if selected_sections:
            source_basis = "full_text"
            confidence = "high"
            text_units = [section.text for section in selected_sections]
            evidence_spans = self._create_section_spans(attachment.paper_id, selected_sections)
        elif paper.abstract.strip():
            source_basis = "abstract_only"
            confidence = "medium"
            text_units = [paper.abstract]
            blockers.append("Full text not available; reading is abstract-only and lower confidence.")
            evidence_spans = [self._abstract_span(paper)]
        else:
            source_basis = "metadata_only"
            confidence = "low"
            text_units = [paper.title]
            blockers.append("Missing full text and abstract; reading is metadata-only.")
            evidence_spans = []
        if evidence_spans:
            self._persist_evidence_spans(run_ids, evidence_spans)
        contributions = _extract_contributions(text_units)
        limitations = _extract_limitations(text_units)
        status = RelatedWorkReadingStatus(
            id=f"related-work-reading-{slugify(benchmark_id)}-{slugify(attachment.paper_id)}-{slugify(attachment.category)}",
            benchmark_id=benchmark_id,
            paper_id=attachment.paper_id,
            category=attachment.category,
            source_basis=source_basis,
            sections_used=[section.id for section in selected_sections],
            evidence_span_ids=[span.id for span in evidence_spans],
            extracted_contributions=contributions,
            extracted_limitations=limitations,
            relevance_to_selected_benchmark=_relevance_note(attachment.category, paper, contributions, limitations),
            confidence=confidence,
            blockers=blockers,
            provenance=Provenance(
                created_by_skill="selected-related-work-reading",
                source_ids=[benchmark_id, attachment.paper_id, *[section.id for section in selected_sections]],
                timestamp=utc_now_iso(),
                reasoning_summary="Read curated related-work paper to extract contribution, limitation, and benchmark relevance evidence.",
            ),
        )
        self._write_status(benchmark_id, status)
        return status

    def _paper_context(self, benchmark_id: str, paper_id: str) -> tuple[Paper, list[PaperSection], list[str]]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        paper: Paper | None = None
        sections: list[PaperSection] = []
        run_ids: list[str] = []
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            if any(item.id == paper_id for item in state.papers):
                run_ids.append(run_id)
            for item in state.papers:
                if item.id == paper_id and paper is None:
                    paper = item
            sections.extend(section for section in state.paper_sections if section.paper_id == paper_id and section.text.strip())
        if paper is None:
            raise ValueError(f"Related-work paper ID `{paper_id}` is not a known Paper record.")
        return paper, sections, run_ids

    def _create_section_spans(self, paper_id: str, sections: list[PaperSection]) -> list[EvidenceSpan]:
        spans: list[EvidenceSpan] = []
        for section in sections:
            quote = _best_quote(section.text)
            if quote:
                evidence_type = "limitation" if section.section_type == "limitations" else "claim"
                spans.append(create_evidence_span_from_quote(section, quote, evidence_type=evidence_type, confidence="medium"))
        return spans

    def _abstract_span(self, paper: Paper) -> EvidenceSpan:
        quote = _best_quote(paper.abstract)
        return EvidenceSpan(
            id=f"related-work-abstract-span-{slugify(paper.id)}",
            paper_id=paper.id,
            quote=quote,
            locator=f"{paper.id}:abstract",
            evidence_type="abstract_summary",
            confidence="medium",
            provenance=Provenance(
                created_by_skill="selected-related-work-reading",
                source_ids=[paper.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created an evidence span from paper abstract because parsed full text was unavailable.",
            ),
        )

    def _persist_evidence_spans(self, run_ids: list[str], spans: list[EvidenceSpan]) -> None:
        if not run_ids:
            return
        run_id = run_ids[0]
        state = self.state_manager.load_run(run_id)
        existing = {span.id for span in state.evidence_spans}
        state.evidence_spans.extend(span for span in spans if span.id not in existing)
        self.state_manager.save_run(state)

    def _write_statuses(self, benchmark_id: str, statuses: list[RelatedWorkReadingStatus]) -> None:
        path = self.statuses_path(benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([to_plain(status) for status in statuses], indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_related_work_reading_report(statuses), encoding="utf-8")
        for status in statuses:
            self._write_status(benchmark_id, status)

    def _write_status(self, benchmark_id: str, status: RelatedWorkReadingStatus) -> None:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._reading_dir(spec.project_id) / "papers" / f"{slugify(status.paper_id)}-{slugify(status.category)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(status), indent=2) + "\n", encoding="utf-8")

    def _reading_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "related_work_reading"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_related_work_reading_report(statuses: list[RelatedWorkReadingStatus]) -> str:
    benchmark_id = statuses[0].benchmark_id if statuses else "unknown"
    lines = [
        "# Selected Related-Work Reading Report",
        "",
        f"- Benchmark ID: `{benchmark_id}`",
        f"- Papers read: {len(statuses)}",
        "",
        "## Papers",
        "",
    ]
    for status in statuses:
        lines.extend(
            [
                f"### {status.paper_id}",
                f"- Category: {status.category}",
                f"- Source basis: `{status.source_basis}`",
                f"- Confidence: `{status.confidence}`",
                f"- Sections used: {', '.join(status.sections_used) or 'none'}",
                f"- Evidence spans: {', '.join(status.evidence_span_ids) or 'none'}",
                f"- Relevance: {status.relevance_to_selected_benchmark or 'not assessed'}",
                "- Contributions:",
            ]
        )
        lines.extend([f"  - {item}" for item in status.extracted_contributions] or ["  - none"])
        lines.append("- Limitations:")
        lines.extend([f"  - {item}" for item in status.extracted_limitations] or ["  - none"])
        lines.append("- Blockers:")
        lines.extend([f"  - {item}" for item in status.blockers] or ["  - none"])
        lines.append("")
    lines.extend(["## Claim Boundary", ""])
    lines.extend(
        [
            "- Full-text readings provide stronger novelty-positioning evidence than abstract-only readings.",
            "- Abstract-only readings remain usable but must be labeled lower confidence.",
            "- Metadata-only readings cannot support strong novelty comparisons.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _select_sections(sections: list[PaperSection]) -> list[PaperSection]:
    priority = {"abstract", "introduction", "related_work", "method", "results", "limitations", "conclusion", "unknown"}
    selected = [section for section in sections if section.section_type in priority]
    return selected[:4] if selected else sections[:4]


def _extract_contributions(text_units: list[str]) -> list[str]:
    sentences = _sentences(text_units)
    matches = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in ["solve", "propose", "evaluate", "benchmark", "calibrat", "method"])
    ]
    return (matches or sentences[:1])[:3]


def _extract_limitations(text_units: list[str]) -> list[str]:
    sentences = _sentences(text_units)
    matches = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in ["does not", "limitation", "limited", "future", "not solve", "not evaluate"])
    ]
    return matches[:3]


def _relevance_note(category: str, paper: Paper, contributions: list[str], limitations: list[str]) -> str:
    if contributions and limitations:
        return f"Supports `{category}` positioning while preserving limitations for `{paper.id}`."
    if contributions:
        return f"Supports `{category}` positioning for the selected benchmark; limitation evidence needs review."
    return f"Provides weak metadata-level context for `{category}`; not enough for strong novelty positioning."


def _best_quote(text: str) -> str:
    sentences = _sentences([text])
    return sentences[0] if sentences else text.strip()[:220]


def _sentences(text_units: list[str]) -> list[str]:
    text = " ".join(unit.strip().replace("\n", " ") for unit in text_units if unit.strip())
    raw = [part.strip() for part in text.replace("?", ".").replace("!", ".").split(".")]
    return [part + "." for part in raw if part][:8]
