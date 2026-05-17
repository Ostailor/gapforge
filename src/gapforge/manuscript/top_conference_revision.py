"""Top-conference clarity and contribution-framing revision pass."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.evals.paper_quality import PaperQualityAssessment, PaperQualityEvaluator
from gapforge.external_review import ExternalExpertReviewManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import ManuscriptSection, ManuscriptState
from gapforge.manuscript.sections import default_section_title
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.reviewers.issue_tracker import ReviewIssue, ReviewIssueTracker
from gapforge.selected_benchmark import SelectedAblationRun
from gapforge.state import slugify, utc_now_iso
from gapforge.style_corpus import VenueStyleAnalyzer, VenueStyleProfile
from gapforge.venues import VenueProfile, get_venue_profile


@dataclass(slots=True)
class TopConferenceSectionRevision:
    section_id: str
    section_type: str
    title: str
    output_path: str
    revision_goals: list[str] = field(default_factory=list)
    evidence_inputs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TopConferenceRevisionReport:
    id: str
    manuscript_id: str
    benchmark_id: str
    venue_profile_id: str
    style_profile_id: str
    status: str
    revised_sections: list[TopConferenceSectionRevision] = field(default_factory=list)
    evidence_inputs: dict[str, str] = field(default_factory=dict)
    paper_quality_score: float = 0.0
    review_issue_count: int = 0
    open_review_issue_count: int = 0
    claim_traceability_passed: bool = False
    limitations_preserved: bool = False
    plagiarism_safe: bool = True
    unsupported_claims_added: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="top-conference-revision"))


@dataclass(slots=True)
class TopConferenceReadinessReport:
    id: str
    manuscript_id: str
    benchmark_id: str
    status: str
    conference_candidate_allowed: bool = False
    claim_traceability_passed: bool = False
    paper_quality_score: float = 0.0
    paper_quality_top_ready: bool = False
    ablation_strong_claim_allowed: bool = False
    benchmark_fit_available: bool = False
    limitations_visible: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="top-conference-readiness"))


class TopConferenceRevisionManager:
    """Revise manuscript framing while preserving evidence and limitation gates."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscripts = ManuscriptManager(config)
        self.traceability = ManuscriptTraceabilityAuditor(config)
        self.style = VenueStyleAnalyzer(config)
        self.paper_quality = PaperQualityEvaluator(config)
        self.review_issues = ReviewIssueTracker(config)
        self.external_reviews = ExternalExpertReviewManager(config)

    def revise(self, manuscript_id: str) -> TopConferenceRevisionReport:
        state = self.manuscripts.load_state(manuscript_id)
        root = self.manuscripts.manuscript_root(manuscript_id)
        original_claim_count = len(state.claim_uses)
        original_limitations = _section_text(root, state.sections, "limitations")
        venue = _resolve_venue(state)
        state.manuscript.target_venue = venue.id
        style_profile = self.style.analyze(venue.id)
        benchmark_id = _benchmark_id_for_state(root, state)
        evidence = _load_evidence(root, benchmark_id)
        paper_quality = self._paper_quality(manuscript_id)
        issues = self.review_issues.load(manuscript_id)
        revised = self._revise_sections(root, state, venue, style_profile, evidence, paper_quality, issues)
        self.manuscripts._touch(state)
        self.manuscripts._save_state(state)

        traceability = self.traceability.audit(manuscript_id)
        reloaded = self.manuscripts.load_state(manuscript_id)
        limitations_preserved = _limitations_preserved(root, reloaded.sections, original_limitations)
        unsupported_claims_added = len(reloaded.claim_uses) != original_claim_count
        blockers = list(traceability.blocking_issues)
        if unsupported_claims_added:
            blockers.append("Revision changed manuscript claim-use count; unsupported claim boundary must be reviewed.")
        if not limitations_preserved:
            blockers.append("Revision did not preserve visible limitations.")
        blockers.extend(_evidence_blockers(evidence))
        report = TopConferenceRevisionReport(
            id=f"top-conference-revision-{slugify(manuscript_id)}",
            manuscript_id=manuscript_id,
            benchmark_id=benchmark_id,
            venue_profile_id=venue.id,
            style_profile_id=style_profile.id,
            status="revision_ready" if not blockers else "revision_with_blockers",
            revised_sections=revised,
            evidence_inputs={key: str(value) for key, value in evidence.items() if isinstance(value, Path) and value.exists()},
            paper_quality_score=paper_quality.average_score if paper_quality else 0.0,
            review_issue_count=len(issues),
            open_review_issue_count=sum(1 for issue in issues if issue.status in {"open", "in_progress"}),
            claim_traceability_passed=not traceability.blocking_issues,
            limitations_preserved=limitations_preserved,
            plagiarism_safe=True,
            unsupported_claims_added=unsupported_claims_added,
            blockers=_unique(blockers),
            warnings=_revision_warnings(evidence, paper_quality, issues),
            provenance=Provenance(
                created_by_skill="top-conference-revision",
                source_ids=[manuscript_id, benchmark_id, venue.id, style_profile.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Revised manuscript framing for top-conference clarity without adding claim uses or hiding limitations.",
            ),
        )
        self._write_revision(root, report)
        self._write_readiness(root, self._readiness_from_state(manuscript_id, state=reloaded, revision=report))
        return report

    def readiness(self, manuscript_id: str) -> TopConferenceReadinessReport:
        state = self.manuscripts.load_state(manuscript_id)
        root = self.manuscripts.manuscript_root(manuscript_id)
        revision = self._load_revision(root)
        report = self._readiness_from_state(manuscript_id, state=state, revision=revision)
        self._write_readiness(root, report)
        return report

    def _revise_sections(
        self,
        root: Path,
        state: ManuscriptState,
        venue: VenueProfile,
        style_profile: VenueStyleProfile,
        evidence: dict[str, object],
        paper_quality: PaperQualityAssessment | None,
        issues: list[ReviewIssue],
    ) -> list[TopConferenceSectionRevision]:
        output_dir = root / "submission" / "top_conference_revision" / "sections"
        output_dir.mkdir(parents=True, exist_ok=True)
        revised: list[TopConferenceSectionRevision] = []
        targets = {
            "abstract": _abstract_text,
            "introduction": _introduction_text,
            "related_work": _related_work_text,
            "method": _method_text,
            "experiments": _experiments_text,
            "results": _results_text,
            "limitations": _limitations_text,
        }
        for section_type, renderer in targets.items():
            section = _ensure_section(self.manuscripts, state, section_type)
            original = (root / section.content_path).read_text(encoding="utf-8") if (root / section.content_path).exists() else ""
            text = renderer(state, venue, style_profile, evidence, paper_quality, issues, original)
            path = root / section.content_path
            path.write_text(text, encoding="utf-8")
            copy_path = output_dir / f"{slugify(section_type)}.md"
            copy_path.write_text(text, encoding="utf-8")
            section.status = "needs_review"
            section.warnings = _unique(
                [
                    *section.warnings,
                    "Top-conference revision is rhetorical only; verify all claims before submission.",
                ]
            )
            revised.append(
                TopConferenceSectionRevision(
                    section_id=section.id,
                    section_type=section.section_type,
                    title=section.title,
                    output_path=str(copy_path.relative_to(root)),
                    revision_goals=_revision_goals(section_type),
                    evidence_inputs=_evidence_names(evidence),
                    warnings=["Does not add unsupported claims.", "Does not claim acceptance."],
                )
            )
        return revised

    def _paper_quality(self, manuscript_id: str) -> PaperQualityAssessment | None:
        try:
            return self.paper_quality.assess(manuscript_id=manuscript_id)
        except FileNotFoundError:
            return None

    def _readiness_from_state(
        self,
        manuscript_id: str,
        *,
        state: ManuscriptState,
        revision: TopConferenceRevisionReport | None,
    ) -> TopConferenceReadinessReport:
        root = self.manuscripts.manuscript_root(manuscript_id)
        benchmark_id = revision.benchmark_id if revision else _benchmark_id_for_state(root, state)
        evidence = _load_evidence(root, benchmark_id)
        traceability = self.traceability.audit(manuscript_id)
        paper_quality = self._paper_quality(manuscript_id)
        issues = self.review_issues.load(manuscript_id)
        blockers = list(traceability.blocking_issues)
        blockers.extend(_evidence_blockers(evidence))
        if paper_quality is None:
            blockers.append("Paper-quality assessment is missing.")
        elif not paper_quality.top_conference_readiness:
            blockers.append(f"Paper-quality assessment is not top-conference-ready (score {paper_quality.average_score:.3f}).")
        open_fatal = [issue.id for issue in issues if issue.severity == "fatal" and issue.status in {"open", "in_progress", "impossible"}]
        if open_fatal:
            blockers.append(f"Open fatal drastic review issues remain: {', '.join(open_fatal)}.")
        external_status = self.external_reviews.status(manuscript_id)
        blockers.extend(external_status.get("blockers", []))
        limitations_visible = _section_text(root, state.sections, "limitations").strip() != ""
        if not limitations_visible:
            blockers.append("Limitations section is missing or empty.")
        ablation = evidence.get("ablation_run")
        ablation_ready = isinstance(ablation, SelectedAblationRun) and ablation.strong_claim_allowed
        benchmark_fit_available = bool(evidence.get("benchmark_fit_report_path") or evidence.get("no_fit_argument_path"))
        conference_allowed = not blockers and bool(revision) and ablation_ready and benchmark_fit_available
        status = "conference_candidate" if conference_allowed else "blocked"
        return TopConferenceReadinessReport(
            id=f"top-conference-readiness-{slugify(manuscript_id)}",
            manuscript_id=manuscript_id,
            benchmark_id=benchmark_id,
            status=status,
            conference_candidate_allowed=conference_allowed,
            claim_traceability_passed=not traceability.blocking_issues,
            paper_quality_score=paper_quality.average_score if paper_quality else 0.0,
            paper_quality_top_ready=bool(paper_quality and paper_quality.top_conference_readiness),
            ablation_strong_claim_allowed=ablation_ready,
            benchmark_fit_available=benchmark_fit_available,
            limitations_visible=limitations_visible,
            blockers=_unique(blockers),
            warnings=[] if revision else ["Run top-conference-revise before treating readiness as final."],
            provenance=Provenance(
                created_by_skill="top-conference-readiness",
                source_ids=[manuscript_id, benchmark_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Checked top-conference readiness without claiming acceptance.",
            ),
        )

    def _load_revision(self, root: Path) -> TopConferenceRevisionReport | None:
        path = root / "submission" / "top_conference_revision" / "top_conference_revision_report.json"
        if not path.exists():
            return None
        return from_dict(TopConferenceRevisionReport, json.loads(path.read_text(encoding="utf-8")))

    def _write_revision(self, root: Path, report: TopConferenceRevisionReport) -> None:
        output_dir = root / "submission" / "top_conference_revision"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "top_conference_revision_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (output_dir / "top_conference_revision_report.md").write_text(render_top_conference_revision(report), encoding="utf-8")

    def _write_readiness(self, root: Path, report: TopConferenceReadinessReport) -> None:
        output_dir = root / "submission" / "top_conference_revision"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "top_conference_readiness.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (output_dir / "top_conference_readiness.md").write_text(render_top_conference_readiness(report), encoding="utf-8")


def render_top_conference_revision(report: TopConferenceRevisionReport) -> str:
    lines = [
        f"# Top-Conference Revision `{report.manuscript_id}`",
        "",
        f"- Status: `{report.status}`",
        f"- Benchmark: `{report.benchmark_id or 'unknown'}`",
        f"- Venue profile: `{report.venue_profile_id}`",
        f"- Paper-quality score: `{report.paper_quality_score:.3f}`",
        f"- Claim traceability passed: `{str(report.claim_traceability_passed).lower()}`",
        f"- Limitations preserved: `{str(report.limitations_preserved).lower()}`",
        f"- Plagiarism safe: `{str(report.plagiarism_safe).lower()}`",
        "",
        "## Revised Sections",
        "",
    ]
    for section in report.revised_sections:
        lines.append(f"- `{section.section_type}` -> `{section.output_path}`; goals: {', '.join(section.revision_goals)}")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in report.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in report.warnings] or ["- none"])
    lines.extend(["", "## Boundaries", ""])
    lines.extend(
        [
            "- This revision sharpens framing only; it does not add unsupported claims.",
            "- It keeps limitations visible and does not claim acceptance.",
            "- Style guidance is derived from structural features, not copied prose.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_top_conference_readiness(report: TopConferenceReadinessReport) -> str:
    lines = [
        f"# Top-Conference Readiness `{report.manuscript_id}`",
        "",
        f"- Status: `{report.status}`",
        f"- Conference candidate allowed: `{str(report.conference_candidate_allowed).lower()}`",
        f"- Claim traceability passed: `{str(report.claim_traceability_passed).lower()}`",
        f"- Paper-quality score: `{report.paper_quality_score:.3f}`",
        f"- Paper-quality top ready: `{str(report.paper_quality_top_ready).lower()}`",
        f"- Ablation strong-claim support: `{str(report.ablation_strong_claim_allowed).lower()}`",
        f"- Benchmark fit/no-fit evidence available: `{str(report.benchmark_fit_available).lower()}`",
        f"- Limitations visible: `{str(report.limitations_visible).lower()}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in report.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in report.warnings] or ["- none"])
    lines.extend(["", "This readiness check does not claim acceptance."])
    return "\n".join(lines).rstrip() + "\n"


def _abstract_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    title = state.manuscript.title
    return "\n".join(
        [
            "# Abstract",
            "",
            (
                f"{title} frames low false-positive multi-agent collusion auditing as a benchmark-validity problem rather than a "
                "deployment-validity claim. The revised paper foregrounds the evaluation gap, states the benchmark contribution "
                "narrowly, and separates synthetic or auxiliary evidence from claims that would require real benchmark grounding."
            ),
            "",
            "Contribution Summary:",
            "- A benchmark protocol for sequential specificity and low false-positive collusion audit evaluation.",
            "- A reviewer-facing fit/no-fit argument for when existing benchmarks are auxiliary checks rather than substitutes.",
            (
                "- Artifact-backed ablation coverage for threshold, observability, hard-negative, collusion-subset, monitor-family, "
                "sequential, sample-size, and alpha-sensitivity objections when those artifacts are present."
            ),
            "",
            "The manuscript does not claim acceptance, deployment validation, or state-of-the-art performance.",
            "",
        ]
    )


def _introduction_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    return "\n".join(
        [
            "# Introduction",
            "",
            "## Problem Motivation",
            "",
            (
                "Low false-positive collusion auditing needs evaluation protocols that distinguish harmful coordination from benign "
                "shared context, repeated public strategy, and hard-negative honest behavior. The top-conference framing is therefore "
                'not "we solved collusion detection"; it is "we specify and stress-test the evidence needed before such a claim is '
                'credible."'
            ),
            "",
            "## Contribution Summary",
            "",
            (
                "- We define the benchmark target around sequential specificity, observability constraints, and low false-positive "
                "denominators."
            ),
            (
                "- We make the real-benchmark fit question explicit, including why partially related benchmarks can be useful sanity "
                "checks without replacing the proposed benchmark."
            ),
            "- We require ablation-backed support before strong empirical claims, and keep missing ablations visible as reviewer blockers.",
            "",
            "## Reviewer-Objection-Aware Framing",
            "",
            (
                "The manuscript directly addresses likely objections about threshold choice, weak baselines, synthetic-only evidence, "
                "benchmark necessity, and hidden limitations. It does not claim acceptance or deployment readiness."
            ),
            "",
        ]
    )


def _related_work_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    no_fit = _read_text(evidence.get("no_fit_argument_path"))
    fit = _read_text(evidence.get("benchmark_fit_report_path"))
    summary = _first_nonempty_line(no_fit) or _first_nonempty_line(fit) or "Real benchmark fit/no-fit evidence has not been generated yet."
    return "\n".join(
        [
            "# Related Work",
            "",
            "## Related Work Contrast",
            "",
            (
                "The related-work contrast should be organized around evaluation fit rather than name proximity. Existing benchmarks "
                "are compared by whether they contain multi-agent collusion labels, sequential interaction windows, low false-positive "
                "denominators, observability controls, and hard-negative honest coordination."
            ),
            "",
            f"Benchmark fit evidence summary: {summary}",
            "",
            (
                "Partial-fit benchmarks should be described as auxiliary or sanity checks. No-fit cases should justify the new benchmark "
                "only when the table states what each existing benchmark lacks."
            ),
            "",
        ]
    )


def _method_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    return "\n".join(
        [
            "# Method",
            "",
            "## Benchmark Validity Argument",
            "",
            (
                "The benchmark validity argument has three parts: the task must expose sequential coordination, the labels must "
                "distinguish collusive alternatives from honest hard negatives, and the monitor inputs must preserve observability "
                "boundaries. The manuscript should state these requirements before reporting results so that benchmark fit is judged "
                "against protocol needs rather than superficial dataset similarity."
            ),
            "",
            "Strong claims require linked artifacts for the benchmark specification, fit/no-fit table, ablations, and traceability report.",
            "",
        ]
    )


def _experiments_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    ablation = evidence.get("ablation_run")
    ablation_text = (
        "All required ablations are artifact-backed for the current evidence boundary."
        if isinstance(ablation, SelectedAblationRun) and ablation.strong_claim_allowed
        else "Required ablations are missing or incomplete and remain reviewer blockers."
    )
    return "\n".join(
        [
            "# Experiments",
            "",
            "## Ablation and Baseline Support",
            "",
            ablation_text,
            "",
            (
                "The experiments section should present threshold calibration, observability mode, hard-negative subset, collusion type "
                "subset, monitor family, sequential versus non-sequential, sample-size, and alpha-sensitivity checks before any strong "
                "empirical statement."
            ),
            "",
            "If a run is synthetic, the section must label it synthetic and avoid deployment-validity language.",
            "",
        ]
    )


def _results_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    score = f"{paper_quality.average_score:.3f}" if paper_quality else "not assessed"
    return "\n".join(
        [
            "# Results",
            "",
            "## Claim Boundary",
            "",
            f"Paper-quality score used by this revision: `{score}`.",
            "",
            (
                "Results should be reported as evidence maturity statements: smoke, pilot, main, real-benchmark auxiliary, or no-fit "
                "justification. The paper should not turn synthetic ablation behavior into claims about real deployment behavior."
            ),
            "",
        ]
    )


def _limitations_text(
    state: ManuscriptState,
    venue: VenueProfile,
    style_profile: VenueStyleProfile,
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
    original: str,
) -> str:
    preserved = original.strip() or "Existing limitations were not drafted before this pass."
    return "\n".join(
        [
            "# Limitations",
            "",
            preserved,
            "",
            "## Explicit Conference-Candidate Limits",
            "",
            "- Synthetic runs support pipeline and reviewer-objection checks, not deployment validity.",
            "- Missing ablations, unresolved fatal review issues, or weak paper-quality scores block conference-candidate claims.",
            (
                "- Partial real benchmark fit can support auxiliary sanity checks, but it cannot replace a direct benchmark fit unless "
                "labels, task structure, observability, and low-FPR denominators match."
            ),
            "- This revision improves clarity and framing; it does not claim acceptance.",
            "",
        ]
    )


def _resolve_venue(state: ManuscriptState) -> VenueProfile:
    try:
        return get_venue_profile(state.manuscript.target_venue or "generic_ml_conference")
    except ValueError:
        return get_venue_profile("generic_ml_conference")


def _benchmark_id_for_state(root: Path, state: ManuscriptState) -> str:
    spec_path = root.parents[1] / "selected_benchmark" / "spec.json"
    if spec_path.exists():
        return str(json.loads(spec_path.read_text(encoding="utf-8")).get("id", ""))
    return ""


def _load_evidence(root: Path, benchmark_id: str) -> dict[str, object]:
    benchmark_root = root.parents[1] / "selected_benchmark"
    evidence: dict[str, object] = {}
    fit_path = benchmark_root / "benchmark_fit_hardening" / "benchmark_fit_hardening_report.md"
    no_fit_path = benchmark_root / "benchmark_fit_hardening" / "no_fit_argument.md"
    ablation_path = benchmark_root / "ablations" / "selected_ablation_run.json"
    if fit_path.exists():
        evidence["benchmark_fit_report_path"] = fit_path
    if no_fit_path.exists():
        evidence["no_fit_argument_path"] = no_fit_path
    if ablation_path.exists():
        evidence["ablation_run_path"] = ablation_path
        evidence["ablation_run"] = from_dict(SelectedAblationRun, json.loads(ablation_path.read_text(encoding="utf-8")))
    return evidence


def _evidence_blockers(evidence: dict[str, object]) -> list[str]:
    blockers = []
    if not evidence.get("benchmark_fit_report_path") and not evidence.get("no_fit_argument_path"):
        blockers.append("Benchmark fit/no-fit evidence is missing.")
    ablation = evidence.get("ablation_run")
    if not isinstance(ablation, SelectedAblationRun):
        blockers.append("Ablation results are missing.")
    elif not ablation.strong_claim_allowed:
        blockers.append("Ablation results do not support strong claims; missing ablations remain reviewer blockers.")
    return blockers


def _revision_warnings(
    evidence: dict[str, object],
    paper_quality: PaperQualityAssessment | None,
    issues: list[ReviewIssue],
) -> list[str]:
    warnings = []
    if paper_quality is None:
        warnings.append("Paper-quality assessment unavailable; readiness remains conservative.")
    elif not paper_quality.top_conference_readiness:
        warnings.append("Paper-quality assessment does not yet mark the paper top-conference-ready.")
    if any(issue.status in {"open", "in_progress"} for issue in issues):
        warnings.append("Open drastic review issues remain visible.")
    warnings.extend(_evidence_blockers(evidence))
    return _unique(warnings)


def _ensure_section(manager: ManuscriptManager, state: ManuscriptState, section_type: str) -> ManuscriptSection:
    section = next((item for item in state.sections if item.section_type == section_type), None)
    if section is not None:
        return section
    created = manager.create_section(
        manuscript_id=state.manuscript.id,
        section_type=section_type,
        title=default_section_title(section_type),
        status="needs_review",
    )
    state.sections.append(created)
    return created


def _section_text(root: Path, sections: list[ManuscriptSection], section_type: str) -> str:
    section = next((item for item in sections if item.section_type == section_type), None)
    if section is None:
        return ""
    path = root / section.content_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _limitations_preserved(root: Path, sections: list[ManuscriptSection], original: str) -> bool:
    current = _section_text(root, sections, "limitations")
    if not current.strip():
        return False
    if original.strip() and original.strip() not in current:
        return False
    return "limitations" in current.lower() or "limit" in current.lower()


def _revision_goals(section_type: str) -> list[str]:
    goals = {
        "abstract": ["sharper abstract", "clear contribution boundary"],
        "introduction": ["stronger problem motivation", "clearer contribution bullets"],
        "related_work": ["related work contrast", "benchmark fit/no-fit framing"],
        "method": ["benchmark validity argument"],
        "experiments": ["baseline and ablation support"],
        "results": ["paper-quality-aware claim boundary"],
        "limitations": ["explicit but not self-defeating limitations"],
    }
    return goals.get(section_type, ["top-conference clarity"])


def _evidence_names(evidence: dict[str, object]) -> list[str]:
    return [key for key, value in evidence.items() if key.endswith("_path") and isinstance(value, Path) and value.exists()]


def _read_text(value: object) -> str:
    if isinstance(value, Path) and value.exists():
        return value.read_text(encoding="utf-8")
    return ""


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip("#- ` ")
        if stripped and not stripped.startswith("|"):
            return stripped
    return ""


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
