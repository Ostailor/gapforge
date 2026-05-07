"""Full-manuscript reviewer simulation and rebuttal planning."""

from __future__ import annotations

import json

from gapforge.artifact_eval.package import load_artifact_evaluation_package
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import (
    BibliographyRecord,
    ManuscriptReviewPanel,
    ManuscriptSection,
    ManuscriptState,
    ManuscriptTraceabilityReport,
    SubmissionChecklist,
)
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.models import (
    ArtifactEvaluationPackage,
    NoveltyDossier,
    Provenance,
    RebuttalPlan,
    RelatedWorkMatrix,
    ResearchProgramState,
    ResearchRunState,
    ReviewerReview,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication.package import ReplicationPackageExporter
from gapforge.reviewers.scoring import decision_risk, score_from_issues
from gapforge.state import ResearchStateManager, utc_now_iso

REVIEW_ROLES = [
    "novelty reviewer",
    "empirical reviewer",
    "clarity reviewer",
    "related-work reviewer",
    "reproducibility/artifact reviewer",
    "ethics/limitations reviewer",
    "area chair",
]


class ManuscriptReviewPanelBuilder:
    """Attack a full manuscript before submission using deterministic reviewer roles."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def review(self, manuscript_id: str) -> ManuscriptReviewPanel:
        context = _ReviewContext.from_manuscript(self, manuscript_id)
        reviews = [
            _novelty_review(context),
            _empirical_review(context),
            _clarity_review(context),
            _related_work_review(context),
            _reproducibility_artifact_review(context),
            _ethics_limitations_review(context),
        ]
        risk = decision_risk(reviews)
        required_fixes = _unique([fix for review in reviews for fix in review.required_fixes])
        fatal_flaws = _unique([flaw for review in reviews for flaw in review.fatal_flaws])
        area_chair = _area_chair_review(context, reviews, risk, required_fixes, fatal_flaws)
        all_reviews = [*reviews, area_chair]
        panel = ManuscriptReviewPanel(
            manuscript_id=manuscript_id,
            reviewer_reports=all_reviews,
            area_chair_summary=area_chair.strengths[0] if area_chair.strengths else "",
            meta_review=_meta_review(context, risk, required_fixes, fatal_flaws),
            decision_risk=risk,
            required_fixes=required_fixes,
            fatal_flaws=fatal_flaws,
            rebuttal_plan=[_rebuttal_for(review) for review in reviews if review.required_fixes or review.fatal_flaws],
            provenance=Provenance(
                created_by_skill="manuscript-review-panel",
                source_ids=_unique(
                    [
                        manuscript_id,
                        context.state.manuscript.project_id,
                        context.state.manuscript.workspace_id,
                        context.traceability_report.manuscript_id,
                        context.bibliography.id if context.bibliography else "",
                        context.artifact_package.id if context.artifact_package else "",
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Simulated full-manuscript reviewers against evidence-linked manuscript state without inventing experiments."
                ),
            ),
        )
        self._write_panel(panel)
        return panel

    def meta_review(self, manuscript_id: str) -> str:
        return self._ensure_panel(manuscript_id).meta_review + "\n"

    def fix_list(self, manuscript_id: str) -> str:
        panel = self._ensure_panel(manuscript_id)
        return render_manuscript_fix_list(panel)

    def _ensure_panel(self, manuscript_id: str) -> ManuscriptReviewPanel:
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        path = root / "reviews" / "manuscript_review_panel.json"
        if path.exists():
            return from_dict(ManuscriptReviewPanel, json.loads(path.read_text(encoding="utf-8")))
        return self.review(manuscript_id)

    def _write_panel(self, panel: ManuscriptReviewPanel) -> None:
        root = self.manuscript_manager.manuscript_root(panel.manuscript_id)
        reviews_dir = root / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "manuscript_review_panel.json").write_text(json.dumps(to_plain(panel), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "manuscript_review_panel.md").write_text(render_manuscript_review_panel_markdown(panel), encoding="utf-8")
        (reviews_dir / "reviewer_reports.json").write_text(json.dumps(to_plain(panel.reviewer_reports), indent=2) + "\n", encoding="utf-8")
        (reviews_dir / "area_chair_summary.md").write_text(panel.area_chair_summary.rstrip() + "\n", encoding="utf-8")
        (reviews_dir / "rebuttal_plan.md").write_text(render_manuscript_rebuttal_plan(panel), encoding="utf-8")
        (reviews_dir / "fix_list.md").write_text(render_manuscript_fix_list(panel), encoding="utf-8")


class _ReviewContext:
    def __init__(
        self,
        *,
        state: ManuscriptState,
        program: ResearchProgramState,
        runs: list[ResearchRunState],
        bibliography: BibliographyRecord | None,
        traceability_report: ManuscriptTraceabilityReport,
        related_work_matrix: RelatedWorkMatrix | None,
        novelty_dossiers: list[NoveltyDossier],
        artifact_ids: list[str],
        replication_package_id: str,
        artifact_package: ArtifactEvaluationPackage | None,
        submission_checklist: SubmissionChecklist | None,
    ) -> None:
        self.state = state
        self.program = program
        self.runs = runs
        self.bibliography = bibliography
        self.traceability_report = traceability_report
        self.related_work_matrix = related_work_matrix
        self.novelty_dossiers = novelty_dossiers
        self.artifact_ids = artifact_ids
        self.replication_package_id = replication_package_id
        self.artifact_package = artifact_package
        self.submission_checklist = submission_checklist

    @classmethod
    def from_manuscript(cls, builder: ManuscriptReviewPanelBuilder, manuscript_id: str) -> _ReviewContext:
        state = builder.manuscript_manager.load_state(manuscript_id)
        program = builder.project_manager.load_project(state.manuscript.project_id)
        runs = _load_runs(builder.state_manager, program)
        bibliography = _load_bibliography(builder.config, manuscript_id)
        traceability_report = ManuscriptTraceabilityAuditor(builder.config).audit(manuscript_id)
        artifacts = _workspace_artifact_ids(builder.workspace_manager, state)
        replication = _latest_replication(builder.config, state.manuscript.workspace_id)
        artifact_package = _latest_artifact_package(builder.config, manuscript_id)
        submission_checklist = _safe_submission_checklist(builder.config, manuscript_id)
        return cls(
            state=state,
            program=program,
            runs=runs,
            bibliography=bibliography,
            traceability_report=traceability_report,
            related_work_matrix=_related_work_matrix(program, runs, state.manuscript.direction_id),
            novelty_dossiers=_novelty_dossiers(runs, state.manuscript.direction_id),
            artifact_ids=artifacts,
            replication_package_id=replication.id if replication else "",
            artifact_package=artifact_package,
            submission_checklist=submission_checklist,
        )


def render_manuscript_review_panel_markdown(panel: ManuscriptReviewPanel) -> str:
    lines = [
        f"# Manuscript Review Panel `{panel.manuscript_id}`",
        "",
        f"- Decision risk: `{panel.decision_risk}`",
        f"- Required fixes: {len(panel.required_fixes)}",
        f"- Fatal flaws: {len(panel.fatal_flaws)}",
        "",
        "## Area Chair Summary",
        "",
        panel.area_chair_summary or "No area chair summary generated.",
        "",
        "## Meta Review",
        "",
        panel.meta_review or "No meta-review generated.",
        "",
        "## Reviewer Reports",
        "",
    ]
    for review in panel.reviewer_reports:
        lines.extend(
            [
                f"### {review.reviewer_id}: {review.role}",
                "",
                f"- Score: {review.score:.1f}",
                f"- Confidence: {review.confidence}",
                f"- Evidence: {', '.join(review.evidence_or_prior_work) or 'none'}",
                "",
                "**Strengths**",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in review.strengths] or ["- none"])
        lines.extend(["", "**Weaknesses**", ""])
        lines.extend([f"- {item}" for item in review.weaknesses] or ["- none"])
        lines.extend(["", "**Required Fixes**", ""])
        lines.extend([f"- {item}" for item in review.required_fixes] or ["- none"])
        lines.extend(["", "**Fatal Flaws**", ""])
        lines.extend([f"- {item}" for item in review.fatal_flaws] or ["- none", ""])
    lines.extend(["## Rebuttal Plan", "", render_manuscript_rebuttal_plan(panel).rstrip()])
    return "\n".join(lines).rstrip() + "\n"


def render_manuscript_rebuttal_plan(panel: ManuscriptReviewPanel) -> str:
    lines = [
        f"# Rebuttal Plan `{panel.manuscript_id}`",
        "",
        "Rebuttal actions are fixes and evidence-gathering tasks. They are not fabricated responses.",
        "",
    ]
    if not panel.rebuttal_plan:
        lines.append("- none")
        return "\n".join(lines).rstrip() + "\n"
    for plan in panel.rebuttal_plan:
        lines.extend(
            [
                f"## `{plan.target_review_id}`",
                "",
                f"- Strategy: {plan.response_strategy}",
                f"- Evidence needed: {', '.join(plan.evidence_needed) or 'none'}",
                f"- Experiments to add: {', '.join(plan.experiments_to_add) or 'none'}",
                f"- Citations to add: {', '.join(plan.citations_to_add) or 'none'}",
                f"- Claims to soften: {', '.join(plan.claims_to_soften) or 'none'}",
                f"- Risks: {', '.join(plan.risks) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_manuscript_fix_list(panel: ManuscriptReviewPanel) -> str:
    lines = [
        f"# Manuscript Fix List `{panel.manuscript_id}`",
        "",
        "## Fatal Flaws",
        "",
    ]
    lines.extend([f"- {item}" for item in panel.fatal_flaws] or ["- none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {item}" for item in panel.required_fixes] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _novelty_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = _section_evidence(context.state, ["introduction", "related_work"])
    novelty_claims = [claim for claim in context.state.claim_uses if claim.use_type == "novelty"]
    if novelty_claims and not context.novelty_dossiers:
        fatal.append("Novelty claims are present but no novelty dossier is linked for this manuscript direction.")
        fixes.append("Link or generate a novelty dossier and prior-work recall assessment before submission.")
    if context.novelty_dossiers:
        evidence.extend([f"novelty_dossier:{dossier.target_id}" for dossier in context.novelty_dossiers])
        if any(dossier.missing_searches for dossier in context.novelty_dossiers):
            weaknesses.append("Novelty dossier has missing searches.")
            fixes.append("Complete the missing novelty searches and update the related-work discussion.")
    elif not novelty_claims:
        weaknesses.append("No explicit novelty claim is available for reviewers to assess.")
        fixes.append("State the novelty contribution or remove novelty-oriented positioning.")
    return _review("R1", "novelty reviewer", weaknesses, fixes, fatal, evidence)


def _empirical_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    result_sections = _sections(context.state, ["results", "experiments"])
    evidence = _section_evidence(context.state, ["results", "experiments"])
    result_claims = [claim for claim in context.state.claim_uses if claim.use_type == "result"]
    if result_claims and not any(section.source_artifact_ids for section in result_sections):
        fatal.append("Result claims are present but manuscript sections do not link result artifacts.")
        fixes.append("Link result claims to recorded result artifacts or remove/soften the result claims.")
    if result_claims and not context.artifact_ids:
        fatal.append("No experiment result artifacts exist in the workspace for claimed results.")
        fixes.append("Run experiments and parse result artifacts before claiming empirical results.")
    if result_claims and not any("baseline" in table_id for table_id in context.state.table_ids):
        weaknesses.append("No baseline comparison table is linked to the manuscript.")
        fixes.append("Generate an artifact-backed baseline comparison table or state that no baseline claim is made.")
    evidence.extend([f"artifact:{artifact_id}" for artifact_id in context.artifact_ids])
    return _review("R2", "empirical reviewer", weaknesses, fixes, fatal, evidence)


def _clarity_review(context: _ReviewContext) -> ReviewerReview:
    required = ["abstract", "introduction", "method", "results", "limitations", "conclusion"]
    present = {section.section_type for section in context.state.sections}
    missing = [section_type for section_type in required if section_type not in present]
    weaknesses = [f"Missing manuscript section `{section_type}`." for section_type in missing]
    fixes = [f"Draft and review the `{section_type}` section." for section_type in missing]
    if any(section.status != "approved" for section in context.state.sections):
        weaknesses.append("One or more manuscript sections are not approved.")
        fixes.append("Move section drafts through review before submission.")
    return _review("R3", "clarity reviewer", weaknesses, fixes, [], _section_evidence(context.state, required))


def _related_work_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence = _section_evidence(context.state, ["related_work"])
    related_sections = _sections(context.state, ["related_work"])
    if not related_sections:
        fatal.append("Related-work section is missing.")
        fixes.append("Add a related-work section linked to known paper records and closest prior work.")
    if context.bibliography is None or not context.bibliography.entries:
        fatal.append("Bibliography is missing, so related-work claims cannot be checked.")
        fixes.append("Build a bibliography from known paper records before submission.")
    else:
        evidence.append(context.bibliography.id)
    if context.related_work_matrix is None:
        weaknesses.append("No related-work matrix is available for coverage review.")
        fixes.append("Build or attach a related-work matrix covering closest prior work and baselines.")
    else:
        evidence.append(f"related_work_matrix:{context.related_work_matrix.direction_id}")
        if context.related_work_matrix.missing_categories:
            weaknesses.append("Related-work matrix lists missing categories.")
            fixes.append("Resolve missing related-work categories or explicitly limit the claim scope.")
    return _review("R4", "related-work reviewer", weaknesses, fixes, fatal, evidence)


def _reproducibility_artifact_review(context: _ReviewContext) -> ReviewerReview:
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    evidence: list[str] = []
    if not context.replication_package_id:
        fatal.append("No replication package exists for the manuscript workspace.")
        fixes.append("Export a replication package before submission.")
    else:
        evidence.append(f"replication_package:{context.replication_package_id}")
    if context.artifact_package is None:
        fatal.append("No artifact evaluation package is linked to this manuscript.")
        fixes.append("Export an artifact evaluation package before artifact review.")
    else:
        evidence.append(f"artifact_eval:{context.artifact_package.id}")
        if context.artifact_package.status != "review_ready":
            weaknesses.append(f"Artifact evaluation package status is `{context.artifact_package.status}`.")
            fixes.append("Resolve artifact evaluation package blockers before submission.")
    if context.submission_checklist is not None:
        evidence.append(f"submission_checklist:{context.submission_checklist.status}")
        if context.submission_checklist.status != "submission_ready":
            weaknesses.append("Submission checklist is not submission_ready.")
            fixes.extend(context.submission_checklist.blocking_issues)
    else:
        weaknesses.append("Submission checklist has not been generated.")
        fixes.append("Run `gapforge submission-checklist` and address blockers.")
    return _review("R5", "reproducibility/artifact reviewer", weaknesses, fixes, fatal, evidence)


def _ethics_limitations_review(context: _ReviewContext) -> ReviewerReview:
    sections = _sections(context.state, ["limitations", "ethics"])
    section_types = {section.section_type for section in sections}
    weaknesses: list[str] = []
    fixes: list[str] = []
    fatal: list[str] = []
    if "limitations" not in section_types:
        fatal.append("Limitations section is missing.")
        fixes.append("Add limitations that disclose known blockers, failed runs, and scope limits.")
    if any(warning.warning_type == "hidden_limitation" for warning in context.traceability_report.overclaim_warnings):
        fatal.append("Known blockers are hidden from limitations.")
        fixes.append("Add known major blockers to the limitations section.")
    if "ethics" not in section_types:
        weaknesses.append("Ethics section is absent.")
        fixes.append("Add an ethics section or justify why it is not required by the venue.")
    evidence = _section_evidence(context.state, ["limitations", "ethics"])
    return _review("R6", "ethics/limitations reviewer", weaknesses, fixes, fatal, evidence)


def _area_chair_review(
    context: _ReviewContext,
    reviews: list[ReviewerReview],
    risk: str,
    required_fixes: list[str],
    fatal_flaws: list[str],
) -> ReviewerReview:
    summary = (
        f"Area chair risk for `{context.state.manuscript.id}` is `{risk}`. "
        f"{len(fatal_flaws)} fatal flaw(s) and {len(required_fixes)} required fix(es) must be resolved before submission."
    )
    fatal = ["Panel found fatal manuscript flaws."] if fatal_flaws else []
    fixes = ["Address all reviewer required fixes before submission."] if required_fixes else []
    return _review(
        "AC",
        "area chair",
        weaknesses=[],
        fixes=fixes,
        fatal=fatal,
        evidence=[f"review:{review.reviewer_id}" for review in reviews],
        strengths=[summary],
    )


def _review(
    reviewer_id: str,
    role: str,
    weaknesses: list[str],
    fixes: list[str],
    fatal: list[str],
    evidence: list[str],
    strengths: list[str] | None = None,
) -> ReviewerReview:
    score = score_from_issues(base=8.0, major=len(weaknesses), fatal=len(fatal))
    return ReviewerReview(
        reviewer_id=reviewer_id,
        role=role,
        score=score,
        confidence="high" if evidence else "medium",
        strengths=strengths or (["Evidence-linked review found no blocking issue for this role."] if not weaknesses and not fatal else []),
        weaknesses=_unique(weaknesses),
        questions=["Which exact manuscript section/evidence artifact resolves each required fix?"] if fixes or fatal else [],
        required_fixes=_unique(fixes),
        fatal_flaws=_unique(fatal),
        evidence_or_prior_work=_unique(evidence),
        provenance=Provenance(
            created_by_skill="manuscript-review-panel",
            source_ids=evidence,
            timestamp=utc_now_iso(),
            reasoning_summary=f"Deterministic {role} attacked manuscript state using section and evidence links.",
        ),
    )


def _rebuttal_for(review: ReviewerReview) -> RebuttalPlan:
    return RebuttalPlan(
        target_review_id=review.reviewer_id,
        response_strategy="Resolve the reviewer issue with manuscript edits, linked evidence, or claim softening; do not invent results.",
        evidence_needed=_unique([*review.evidence_or_prior_work, *review.required_fixes]),
        experiments_to_add=[fix for fix in review.required_fixes if "Run experiments" in fix or "baseline comparison" in fix],
        citations_to_add=[fix for fix in review.required_fixes if "bibliography" in fix.lower() or "related-work" in fix.lower()],
        claims_to_soften=[fix for fix in review.required_fixes if "soften" in fix.lower() or "remove" in fix.lower()],
        risks=_unique([*review.fatal_flaws, *review.weaknesses]),
        provenance=Provenance(
            created_by_skill="manuscript-rebuttal-plan",
            source_ids=[review.reviewer_id, *review.evidence_or_prior_work],
            timestamp=utc_now_iso(),
            reasoning_summary="Converted manuscript reviewer objections into concrete fixes without fabricating rebuttal answers.",
        ),
    )


def _meta_review(context: _ReviewContext, risk: str, required_fixes: list[str], fatal_flaws: list[str]) -> str:
    if fatal_flaws:
        return f"The manuscript `{context.state.manuscript.id}` should not be submitted. Fatal flaws remain: {'; '.join(fatal_flaws)}"
    if required_fixes:
        return (
            f"The manuscript `{context.state.manuscript.id}` has `{risk}` decision risk and needs fixes before submission: "
            f"{'; '.join(required_fixes)}"
        )
    return f"The manuscript `{context.state.manuscript.id}` has no simulated blocking reviewer issue, but human review is still required."


def _section_evidence(state: ManuscriptState, section_types: list[str]) -> list[str]:
    evidence: list[str] = []
    for section in _sections(state, section_types):
        evidence.append(f"section:{section.id}")
        evidence.extend(f"claim:{claim_id}" for claim_id in section.source_claim_ids)
        evidence.extend(f"paper:{paper_id}" for paper_id in section.source_paper_ids)
        evidence.extend(f"result:{result_id}" for result_id in section.source_result_ids)
        evidence.extend(f"artifact:{artifact_id}" for artifact_id in section.source_artifact_ids)
    return _unique(evidence)


def _sections(state: ManuscriptState, section_types: list[str]) -> list[ManuscriptSection]:
    wanted = set(section_types)
    return [section for section in state.sections if section.section_type in wanted]


def _load_runs(state_manager: ResearchStateManager, program: ResearchProgramState) -> list[ResearchRunState]:
    runs: list[ResearchRunState] = []
    for run_id in program.run_ids or program.project.run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return runs


def _load_bibliography(config: GapForgeConfig, manuscript_id: str) -> BibliographyRecord | None:
    try:
        return ManuscriptBibliographyManager(config).load(manuscript_id)
    except FileNotFoundError:
        return None


def _workspace_artifact_ids(workspace_manager: ExperimentWorkspaceManager, state: ManuscriptState) -> list[str]:
    try:
        return [artifact.id for artifact in workspace_manager.list_result_artifacts(state.manuscript.workspace_id)]
    except FileNotFoundError:
        return []


def _latest_replication(config: GapForgeConfig, workspace_id: str):
    try:
        return ReplicationPackageExporter(config).latest_for_workspace(workspace_id)
    except FileNotFoundError:
        return None


def _latest_artifact_package(config: GapForgeConfig, manuscript_id: str) -> ArtifactEvaluationPackage | None:
    for path in sorted(config.project_root.glob(f"*/manuscripts/{manuscript_id}/artifact_evaluation/*/artifact_evaluation_package.json")):
        return load_artifact_evaluation_package(config, path.parent.name)
    return None


def _safe_submission_checklist(config: GapForgeConfig, manuscript_id: str) -> SubmissionChecklist | None:
    try:
        return SubmissionChecklistManager(config).build(manuscript_id)
    except Exception:
        return None


def _related_work_matrix(
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    direction_id: str,
) -> RelatedWorkMatrix | None:
    matrices = [matrix for matrix in program.related_work_matrices if matrix.direction_id == direction_id]
    for run in runs:
        matrices.extend(matrix for matrix in run.related_work_matrices if matrix.direction_id == direction_id)
    return matrices[0] if matrices else None


def _novelty_dossiers(runs: list[ResearchRunState], direction_id: str) -> list[NoveltyDossier]:
    dossiers: list[NoveltyDossier] = []
    for run in runs:
        dossiers.extend(dossier for dossier in run.novelty_dossiers if dossier.target_id == direction_id)
    return dossiers


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
