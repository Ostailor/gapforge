"""Venue-aware manuscript rewriting with evidence gates intact."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import (
    ManuscriptReviewPanel,
    ManuscriptSection,
    ManuscriptState,
    ManuscriptTraceabilityReport,
    SubmissionChecklist,
)
from gapforge.manuscript.sections import default_section_title
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager, render_submission_checklist_markdown
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor, render_traceability_markdown
from gapforge.models import Provenance, RelatedWorkMatrix, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso
from gapforge.style_corpus import StyleCorpusManager, VenueStyleAnalyzer, VenueStyleProfile
from gapforge.style_corpus.style_features import StyleCorpusPaper
from gapforge.venues import VenueProfile, get_venue_profile


@dataclass(slots=True)
class RewrittenSectionRecord:
    section_id: str
    section_type: str
    title: str
    output_path: str
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ClaimSofteningReport:
    id: str
    manuscript_id: str
    unsupported_claim_ids: list[str] = field(default_factory=list)
    softened_claim_ids: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-venue-rewriter"))


@dataclass(slots=True)
class VenueStyleRevisionReport:
    id: str
    manuscript_id: str
    venue_profile_id: str
    status: str
    rewritten_sections: list[RewrittenSectionRecord] = field(default_factory=list)
    section_order_before: list[str] = field(default_factory=list)
    section_order_after: list[str] = field(default_factory=list)
    structural_changes: list[str] = field(default_factory=list)
    style_recommendation_ids: list[str] = field(default_factory=list)
    claim_softening_report_id: str = ""
    traceability_blockers: list[str] = field(default_factory=list)
    reviewer_blockers: list[str] = field(default_factory=list)
    checklist_blockers: list[str] = field(default_factory=list)
    related_work_summary: str = ""
    benchmark_result_summary: str = ""
    copied_text_warnings: list[str] = field(default_factory=list)
    limitations_preserved: bool = False
    publication_ready: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-venue-rewriter"))


@dataclass(slots=True)
class VenueRewriteResult:
    manuscript_id: str
    venue_profile_id: str
    rewritten_sections: list[RewrittenSectionRecord] = field(default_factory=list)
    style_revision_report: VenueStyleRevisionReport | None = None
    claim_softening_report: ClaimSofteningReport | None = None
    venue_checklist_update: SubmissionChecklist | None = None
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="manuscript-venue-rewriter"))


class VenueManuscriptRewriter:
    """Shape manuscript sections for a venue without changing the evidence boundary."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscripts = ManuscriptManager(config)
        self.projects = ProjectMemoryManager(config)
        self.traceability = ManuscriptTraceabilityAuditor(config)
        self.checklists = SubmissionChecklistManager(config)
        self.style_analyzer = VenueStyleAnalyzer(config)
        self.workspaces = ExperimentWorkspaceManager(config)
        self.style_corpus = StyleCorpusManager(config)

    def rewrite(self, manuscript_id: str, venue_profile_id: str) -> VenueRewriteResult:
        venue_profile = get_venue_profile(venue_profile_id)
        state = self.manuscripts.load_state(manuscript_id)
        root = self.manuscripts.manuscript_root(manuscript_id)
        before_order = [section.section_type for section in state.sections]
        original_limitation_content = _limitation_content(root, state.sections)

        state.manuscript.target_venue = venue_profile.id
        structural_changes = _ensure_required_sections(self.manuscripts, state, venue_profile)
        structural_changes.extend(_order_sections_for_venue(state, venue_profile))
        self.manuscripts._touch(state)
        self.manuscripts._save_state(state)

        style_profile = self.style_analyzer.analyze(venue_profile.id)
        style_recommendations = self.style_analyzer.recommend(manuscript_id)
        traceability_report = self.traceability.audit(manuscript_id)
        softening_report = _build_claim_softening_report(manuscript_id, traceability_report)
        rewritten_sections = self._rewrite_sections(root, state, venue_profile, style_profile, traceability_report)
        copied_text_warnings = _copied_text_warnings(root, state.sections, self.style_corpus.list_papers())
        reviewer_blockers = _load_reviewer_blockers(root)
        related_work_summary = _related_work_summary(self.projects.load_project(state.manuscript.project_id).related_work_matrices, state)
        benchmark_result_summary = _benchmark_result_summary(self.workspaces, state)
        checklist = self.checklists.build(manuscript_id)
        limitations_preserved = _limitations_preserved(root, state.sections, original_limitation_content)
        status = _rewrite_status(checklist, traceability_report, reviewer_blockers, copied_text_warnings)
        publication_ready = status == "publication_ready"
        if not limitations_preserved:
            checklist.blocking_issues.append("Venue rewrite did not preserve a limitations section.")
            checklist.status = "not_ready"
            publication_ready = False
            status = "not_publication_ready"
        if copied_text_warnings:
            checklist.blocking_issues.extend(copied_text_warnings)
            checklist.status = "not_ready"
            publication_ready = False
            status = "not_publication_ready"

        report = VenueStyleRevisionReport(
            id=f"venue-rewrite-{slugify(manuscript_id)}-{slugify(venue_profile.id)}",
            manuscript_id=manuscript_id,
            venue_profile_id=venue_profile.id,
            status=status,
            rewritten_sections=rewritten_sections,
            section_order_before=before_order,
            section_order_after=[section.section_type for section in state.sections],
            structural_changes=structural_changes,
            style_recommendation_ids=[recommendation.id for recommendation in style_recommendations],
            claim_softening_report_id=softening_report.id,
            traceability_blockers=traceability_report.blocking_issues,
            reviewer_blockers=reviewer_blockers,
            checklist_blockers=_unique(checklist.blocking_issues),
            related_work_summary=related_work_summary,
            benchmark_result_summary=benchmark_result_summary,
            copied_text_warnings=copied_text_warnings,
            limitations_preserved=limitations_preserved,
            publication_ready=publication_ready,
            provenance=Provenance(
                created_by_skill="manuscript-venue-rewriter",
                source_ids=[manuscript_id, venue_profile.id, style_profile.id, traceability_report.manuscript_id],
                timestamp=utc_now_iso(),
                reasoning_summary=("Rewrote manuscript section structure for venue style while preserving limitations and blocker gates."),
            ),
        )
        self._write_outputs(root, report, softening_report, checklist, traceability_report)
        return VenueRewriteResult(
            manuscript_id=manuscript_id,
            venue_profile_id=venue_profile.id,
            rewritten_sections=rewritten_sections,
            style_revision_report=report,
            claim_softening_report=softening_report,
            venue_checklist_update=checklist,
            provenance=Provenance(
                created_by_skill="manuscript-venue-rewriter",
                source_ids=[manuscript_id, venue_profile.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Completed venue-aware manuscript rewrite without adding unsupported claim uses.",
            ),
        )

    def render_style_report(self, manuscript_id: str) -> str:
        root = self.manuscripts.manuscript_root(manuscript_id)
        path = root / "submission" / "venue_style_revision_report.json"
        if not path.exists():
            state = self.manuscripts.load_state(manuscript_id)
            venue = state.manuscript.target_venue or "generic_ml_conference"
            self.rewrite(manuscript_id, venue)
        report = from_dict(VenueStyleRevisionReport, json.loads(path.read_text(encoding="utf-8")))
        return render_venue_style_revision_report(report)

    def _rewrite_sections(
        self,
        root: Path,
        state: ManuscriptState,
        venue_profile: VenueProfile,
        style_profile: VenueStyleProfile,
        traceability_report: ManuscriptTraceabilityReport,
    ) -> list[RewrittenSectionRecord]:
        rewrite_dir = root / "submission" / "venue_rewrite" / "sections"
        rewrite_dir.mkdir(parents=True, exist_ok=True)
        records: list[RewrittenSectionRecord] = []
        unsupported_claim_ids = set(traceability_report.unsupported_claims)
        for index, section in enumerate(state.sections, start=1):
            original_path = root / section.content_path
            original = original_path.read_text(encoding="utf-8") if original_path.exists() else ""
            rewritten, actions, warnings = _rewrite_section_text(
                section=section,
                original=original,
                index=index,
                venue_profile=venue_profile,
                style_profile=style_profile,
                unsupported_claim_ids=unsupported_claim_ids,
            )
            original_path.write_text(rewritten, encoding="utf-8")
            copy_path = rewrite_dir / f"{index:02d}-{slugify(section.section_type)}.md"
            copy_path.write_text(rewritten, encoding="utf-8")
            section.status = "needs_review" if section.status == "missing" else section.status
            section.warnings = _unique([*section.warnings, *warnings])
            records.append(
                RewrittenSectionRecord(
                    section_id=section.id,
                    section_type=section.section_type,
                    title=section.title,
                    output_path=str(copy_path.relative_to(root)),
                    actions=actions,
                    warnings=warnings,
                )
            )
        self.manuscripts._touch(state)
        self.manuscripts._save_state(state)
        return records

    def _write_outputs(
        self,
        root: Path,
        report: VenueStyleRevisionReport,
        softening_report: ClaimSofteningReport,
        checklist: SubmissionChecklist,
        traceability_report: ManuscriptTraceabilityReport,
    ) -> None:
        submission_dir = root / "submission"
        submission_dir.mkdir(parents=True, exist_ok=True)
        (submission_dir / "venue_style_revision_report.json").write_text(
            json.dumps(to_plain(report), indent=2) + "\n",
            encoding="utf-8",
        )
        (submission_dir / "venue_style_revision_report.md").write_text(render_venue_style_revision_report(report), encoding="utf-8")
        (submission_dir / "claim_softening_report.json").write_text(
            json.dumps(to_plain(softening_report), indent=2) + "\n",
            encoding="utf-8",
        )
        (submission_dir / "claim_softening_report.md").write_text(render_claim_softening_report(softening_report), encoding="utf-8")
        (submission_dir / "submission_checklist.json").write_text(json.dumps(to_plain(checklist), indent=2) + "\n", encoding="utf-8")
        (submission_dir / "submission_checklist.md").write_text(render_submission_checklist_markdown(checklist), encoding="utf-8")
        (submission_dir / "traceability_report.md").write_text(render_traceability_markdown(traceability_report), encoding="utf-8")


def render_venue_style_revision_report(report: VenueStyleRevisionReport) -> str:
    lines = [
        f"# Venue Style Revision `{report.manuscript_id}`",
        "",
        f"- Venue profile: `{report.venue_profile_id}`",
        f"- Status: `{report.status}`",
        f"- Publication-ready: {str(report.publication_ready).lower()}",
        f"- Limitations preserved: {str(report.limitations_preserved).lower()}",
        f"- Rewritten sections: {len(report.rewritten_sections)}",
        "",
        "## Boundary",
        "",
        (
            "Venue style changes are structural and rhetorical only. They do not override traceability, reviewer, checklist, "
            "or evidence gates."
        ),
        "",
        "## Section Order",
        "",
        f"- Before: {', '.join(report.section_order_before) or 'none'}",
        f"- After: {', '.join(report.section_order_after) or 'none'}",
        "",
        "## Structural Changes",
        "",
    ]
    lines.extend([f"- {change}" for change in report.structural_changes] or ["- none"])
    lines.extend(["", "## Rewritten Sections", ""])
    for section in report.rewritten_sections:
        lines.extend(
            [
                f"- `{section.section_type}` -> `{section.output_path}`",
                f"  Actions: {', '.join(section.actions) or 'none'}",
                f"  Warnings: {', '.join(section.warnings) or 'none'}",
            ]
        )
    lines.extend(["", "## Claim Softening", "", f"- Report: `{report.claim_softening_report_id or 'none'}`"])
    lines.extend(["", "## Inputs", ""])
    lines.append(f"- Related work: {report.related_work_summary}")
    lines.append(f"- Benchmark results: {report.benchmark_result_summary}")
    lines.extend(["", "## Blockers", ""])
    blockers = _unique([*report.traceability_blockers, *report.reviewer_blockers, *report.checklist_blockers, *report.copied_text_warnings])
    lines.extend([f"- {blocker}" for blocker in blockers] or ["- none"])
    if report.copied_text_warnings:
        lines.extend(["", "## Copied Text Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.copied_text_warnings)
    return "\n".join(lines).rstrip() + "\n"


def render_claim_softening_report(report: ClaimSofteningReport) -> str:
    lines = [
        f"# Claim Softening Report `{report.manuscript_id}`",
        "",
        f"- Unsupported claims: {len(report.unsupported_claim_ids)}",
        f"- Claims marked for softening: {len(report.softened_claim_ids)}",
        "",
        "## Recommendations",
        "",
    ]
    lines.extend([f"- {item}" for item in report.recommendations] or ["- none"])
    if report.blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in report.blockers)
    return "\n".join(lines).rstrip() + "\n"


def rewrite_result_json(result: VenueRewriteResult) -> str:
    return json.dumps(to_plain(result), indent=2) + "\n"


def _ensure_required_sections(
    manuscript_manager: ManuscriptManager,
    state: ManuscriptState,
    venue_profile: VenueProfile,
) -> list[str]:
    changes: list[str] = []
    existing = {section.section_type for section in state.sections}
    for section_type in venue_profile.required_sections:
        if section_type in existing:
            continue
        section = manuscript_manager.create_section(
            manuscript_id=state.manuscript.id,
            section_type=section_type,
            title=default_section_title(section_type),
            status="needs_review",
            warnings=[f"Created during venue rewrite for `{venue_profile.id}`; content still requires evidence-backed drafting."],
        )
        state.sections.append(section)
        existing.add(section_type)
        changes.append(f"Added missing required section `{section_type}` for venue profile `{venue_profile.id}`.")
    return changes


def _order_sections_for_venue(state: ManuscriptState, venue_profile: VenueProfile) -> list[str]:
    order = {section_type: index for index, section_type in enumerate(venue_profile.common_section_order)}
    before = [section.section_type for section in state.sections]
    state.sections = sorted(state.sections, key=lambda section: (order.get(section.section_type, 10_000), section.id))
    after = [section.section_type for section in state.sections]
    if before == after:
        return []
    return [f"Reordered sections to match venue profile `{venue_profile.id}` common section order."]


def _rewrite_section_text(
    *,
    section: ManuscriptSection,
    original: str,
    index: int,
    venue_profile: VenueProfile,
    style_profile: VenueStyleProfile,
    unsupported_claim_ids: set[str],
) -> tuple[str, list[str], list[str]]:
    title = section.title or default_section_title(section.section_type)
    body = _strip_existing_rewrite_block(original)
    if not body.strip():
        body = f"# {title}\n\n<!-- Draft this section using only linked claims, papers, results, and artifacts. -->\n"
    body = _normalize_heading(body, title)
    notes = [
        "<!-- venue-rewrite:start -->",
        f"Venue profile: {venue_profile.id}",
        f"Section position: {index}",
        "Rewrite boundary: structure and framing only; do not add unsupported claims or copy source-paper prose.",
        f"Linked claims: {', '.join(section.source_claim_ids) if section.source_claim_ids else 'none'}",
        f"Linked papers: {', '.join(section.source_paper_ids) if section.source_paper_ids else 'none'}",
        f"Linked results: {', '.join(section.source_result_ids) if section.source_result_ids else 'none'}",
        f"Linked artifacts: {', '.join(section.source_artifact_ids) if section.source_artifact_ids else 'none'}",
        *_section_specific_notes(section, venue_profile, style_profile),
        "<!-- venue-rewrite:end -->",
        "",
    ]
    actions = ["normalized heading", "inserted venue rewrite boundary notes"]
    warnings: list[str] = []
    unsupported_in_section = [claim_id for claim_id in section.source_claim_ids if claim_id in unsupported_claim_ids]
    if unsupported_in_section:
        warnings.append(f"Unsupported claim(s) require softening before publication use: {', '.join(unsupported_in_section)}.")
    if section.section_type == "limitations":
        actions.append("preserved limitations content")
    return "\n".join(notes) + body.rstrip() + "\n", actions, warnings


def _section_specific_notes(section: ManuscriptSection, venue_profile: VenueProfile, style_profile: VenueStyleProfile) -> list[str]:
    notes: list[str] = []
    if section.section_type == "introduction":
        notes.append("Introduction framing: separate problem, contribution type, evidence scope, and caveats.")
    if section.section_type == "related_work":
        related = style_profile.related_work_placement.get("position_counts_1_indexed", {})
        notes.append(f"Related-work placement evidence from style corpus: {related or 'insufficient corpus evidence'}.")
    if section.section_type in {"experiments", "results", "evaluation"}:
        notes.append("Experiment framing: label vetted, synthetic, auxiliary, and sanity-check evidence separately.")
    if section.section_type == "limitations":
        notes.append("Limitations boundary: preserve known blockers, benchmark-fit limits, and deployment-validity caveats.")
    if section.section_type == "ethics":
        notes.append("Ethics framing: state access, misuse, dataset, and monitoring risks without overstating mitigation.")
    if section.section_type not in venue_profile.common_section_order:
        notes.append("This section is outside the venue profile's common order; keep only if it improves evidence flow.")
    return notes


def _strip_existing_rewrite_block(text: str) -> str:
    return re.sub(r"<!-- venue-rewrite:start -->.*?<!-- venue-rewrite:end -->\s*", "", text, flags=re.DOTALL)


def _normalize_heading(text: str, title: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines[0] = f"# {title}"
        return "\n".join(lines).rstrip() + "\n"
    return f"# {title}\n\n{text.rstrip()}\n"


def _build_claim_softening_report(manuscript_id: str, traceability_report: ManuscriptTraceabilityReport) -> ClaimSofteningReport:
    unsupported = _unique(traceability_report.unsupported_claims)
    recommendations = [f"Claim `{claim_id}` must be softened, supported, or removed before venue submission." for claim_id in unsupported]
    recommendations.extend(
        f"{warning.warning_type}: {warning.suggested_fix}"
        for warning in traceability_report.overclaim_warnings
        if warning.warning_type in {"unsupported", "overstrong_novelty", "result_without_artifact", "smoke_as_main_result"}
    )
    return ClaimSofteningReport(
        id=f"claim-softening-{slugify(manuscript_id)}",
        manuscript_id=manuscript_id,
        unsupported_claim_ids=unsupported,
        softened_claim_ids=unsupported,
        recommendations=_unique(recommendations),
        blockers=traceability_report.blocking_issues,
        provenance=Provenance(
            created_by_skill="manuscript-venue-rewriter",
            source_ids=[manuscript_id, *unsupported],
            timestamp=utc_now_iso(),
            reasoning_summary="Marked unsupported manuscript claims for softening without changing claim text or evidence state.",
        ),
    )


def _limitation_content(root: Path, sections: list[ManuscriptSection]) -> dict[str, str]:
    result: dict[str, str] = {}
    for section in sections:
        if section.section_type != "limitations":
            continue
        path = root / section.content_path
        result[section.id] = path.read_text(encoding="utf-8") if path.exists() else ""
    return result


def _limitations_preserved(root: Path, sections: list[ManuscriptSection], original: dict[str, str]) -> bool:
    limitation_sections = [section for section in sections if section.section_type == "limitations"]
    if not limitation_sections:
        return False
    for section_id, original_content in original.items():
        section = next((item for item in limitation_sections if item.id == section_id), None)
        if section is None:
            return False
        current = (root / section.content_path).read_text(encoding="utf-8") if (root / section.content_path).exists() else ""
        original_without_notes = _strip_existing_rewrite_block(original_content).strip()
        current_without_notes = _strip_existing_rewrite_block(current)
        if original_content.strip() and original_without_notes not in current_without_notes:
            return False
    return True


def _copied_text_warnings(root: Path, sections: list[ManuscriptSection], style_papers: Sequence[StyleCorpusPaper]) -> list[str]:
    warnings: list[str] = []
    section_text = "\n".join(
        (root / section.content_path).read_text(encoding="utf-8") for section in sections if (root / section.content_path).exists()
    )
    if re.search(r"UNIQUE_[A-Z0-9_]*DO_NOT_COPY[A-Z0-9_]*", section_text):
        warnings.append("Copied-text detector matched a protected no-copy fixture marker in manuscript section text.")
    normalized_section_text = _normalize_for_copy_detection(section_text)
    for paper in style_papers:
        source_path = Path(getattr(paper, "local_source_path", ""))
        if not source_path.exists():
            continue
        for sentence in _source_sentences(source_path):
            if _normalize_for_copy_detection(sentence) in normalized_section_text:
                warnings.append(f"Possible copied source sentence from style corpus paper `{getattr(paper, 'id', 'unknown')}`.")
                break
    return _unique(warnings)


def _source_sentences(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\(section|subsection|title|caption)\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if len(sentence.split()) >= 10]


def _normalize_for_copy_detection(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _load_reviewer_blockers(root: Path) -> list[str]:
    path = root / "reviews" / "manuscript_review_panel.json"
    if not path.exists():
        return []
    panel = from_dict(ManuscriptReviewPanel, json.loads(path.read_text(encoding="utf-8")))
    return _unique([*panel.fatal_flaws, *panel.required_fixes])


def _related_work_summary(matrices: list[RelatedWorkMatrix], state: ManuscriptState) -> str:
    matrix = next((item for item in matrices if item.direction_id == state.manuscript.direction_id), None)
    if matrix is None:
        return "no related-work matrix available"
    return (
        f"entries={len(matrix.entries)}; must_cite={len(matrix.must_read_paper_ids)}; "
        f"missing_categories={', '.join(matrix.missing_categories) or 'none'}"
    )


def _benchmark_result_summary(workspaces: ExperimentWorkspaceManager, state: ManuscriptState) -> str:
    try:
        artifacts = workspaces.list_result_artifacts(state.manuscript.workspace_id)
    except FileNotFoundError:
        artifacts = []
    if not artifacts:
        return "no benchmark result artifacts linked"
    return f"result_artifacts={len(artifacts)}; ids={', '.join(artifact.id for artifact in artifacts[:5])}"


def _rewrite_status(
    checklist: SubmissionChecklist,
    traceability_report: ManuscriptTraceabilityReport,
    reviewer_blockers: list[str],
    copied_text_warnings: list[str],
) -> str:
    if checklist.blocking_issues or traceability_report.blocking_issues or reviewer_blockers or copied_text_warnings:
        return "not_publication_ready"
    if checklist.status == "submission_ready":
        return "publication_ready"
    return "venue_shaped_needs_review"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
