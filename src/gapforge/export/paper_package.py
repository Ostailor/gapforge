"""Paper package exporter for mature research directions."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.claim_ledger import ClaimLedger
from gapforge.config import GapForgeConfig
from gapforge.experiments.protocol import render_protocol_markdown
from gapforge.export.bibliography import render_bibtex
from gapforge.export.manuscript import (
    render_abstract,
    render_expected_results,
    render_intro_outline,
    render_limitations,
    render_method_outline,
)
from gapforge.export.rebuttal import render_rebuttal_plan, render_reviewer_objections
from gapforge.models import (
    EvidenceSpan,
    ExperimentPlan,
    ExperimentProtocol,
    Gap,
    NoveltyDossier,
    Paper,
    PaperPackage,
    Provenance,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ReviewPanel,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.renderer import render_related_work_matrix_markdown
from gapforge.reviewers.panel import render_review_panel_markdown
from gapforge.reviewers.rebuttal import render_rebuttal_plans_markdown
from gapforge.state import ResearchStateManager, utc_now_iso

EXPECTED_FILES = [
    "README.md",
    "abstract.md",
    "intro_outline.md",
    "related_work_matrix.md",
    "method_outline.md",
    "experiment_protocol.md",
    "expected_results.md",
    "limitations.md",
    "reviewer_objections.md",
    "review_panel.md",
    "rebuttal_plan.md",
    "bibliography.bib",
    "claim_ledger.md",
    "evidence_index.md",
]


class PaperPackageExporter:
    """Export conservative writing packages without inventing results."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)

    def export_project_direction(
        self,
        project_id: str,
        direction_id: str,
        *,
        allow_rejected: bool = False,
    ) -> PaperPackage:
        program = self.project_manager.load_project(project_id)
        direction = _require_direction(program, direction_id)
        if direction.maturity == "rejected" and not allow_rejected:
            raise ValueError("Rejected directions cannot be exported unless --allow-rejected is set.")
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        context = _ProjectExportContext.from_program(program, states, direction)
        package_dir = Path(program.project.root_dir) / "paper_packages" / direction.id
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _missing_requirements(direction, context)
        files = _write_package_files(package_dir, direction, context, missing)
        package = PaperPackage(
            id=f"paper-package-{direction.id}",
            direction_id=direction.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=direction.maturity,
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export",
                source_ids=[project_id, direction.id, *program.run_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported an auditable manuscript starter kit from project direction state.",
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def export_run_gap(self, run_id: str, gap_id: str, *, allow_rejected: bool = False) -> PaperPackage:
        state = self.state_manager.load_run(run_id)
        gap = _require_gap(state, gap_id)
        direction = ResearchDirection(
            id=gap.id,
            project_id="",
            title=gap.title or gap.id,
            summary=gap.description,
            linked_gap_ids=[gap.id],
            supporting_paper_ids=gap.supporting_paper_ids,
            maturity="experiment_ready" if state.experiments else "candidate",
            readiness_score=0.75 if state.experiments else 0.35,
        )
        if gap.novelty_status == "likely_not_new" and not allow_rejected:
            raise ValueError("Rejected or likely-not-new gaps cannot be exported unless --allow-rejected is set.")
        context = _ProjectExportContext.from_state(state, direction)
        package_dir = Path(state.run_dir) / "paper_packages" / gap.id
        package_dir.mkdir(parents=True, exist_ok=True)
        missing = _missing_requirements(direction, context)
        files = _write_package_files(package_dir, direction, context, missing)
        package = PaperPackage(
            id=f"paper-package-{gap.id}",
            direction_id=gap.id,
            created_at=utc_now_iso(),
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=direction.maturity,
            missing_requirements=missing,
            provenance=Provenance(
                created_by_skill="paper-package-export",
                source_ids=[run_id, gap.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported an auditable manuscript starter kit from run-level gap state.",
            ),
        )
        (package_dir / "paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package


class _ProjectExportContext:
    def __init__(
        self,
        *,
        gap: Gap | None,
        matrix: RelatedWorkMatrix | None,
        protocol: ExperimentProtocol | None,
        experiment: ExperimentPlan | None,
        dossier: NoveltyDossier | None,
        papers: list[Paper],
        evidence_spans: list[EvidenceSpan],
        claims_markdown: str,
        reviewer_objections_markdown: str,
        rebuttal_plan: str,
        review_panel_markdown: str,
        review_panel: ReviewPanel | None,
    ) -> None:
        self.gap = gap
        self.matrix = matrix
        self.protocol = protocol
        self.experiment = experiment
        self.dossier = dossier
        self.papers = papers
        self.evidence_spans = evidence_spans
        self.claims_markdown = claims_markdown
        self.reviewer_objections_markdown = reviewer_objections_markdown
        self.rebuttal_plan = rebuttal_plan
        self.review_panel_markdown = review_panel_markdown
        self.review_panel = review_panel

    @classmethod
    def from_program(
        cls, program: ResearchProgramState, states: list[ResearchRunState], direction: ResearchDirection
    ) -> _ProjectExportContext:
        gap = _first_gap(states, direction.linked_gap_ids)
        experiment = _first_experiment(states, direction.linked_experiment_ids, direction.linked_gap_ids)
        protocol = _first_protocol(
            [*program.experiment_protocols, *[protocol for state in states for protocol in state.experiment_protocols]],
            direction,
            experiment,
        )
        matrix = _first_matrix(
            [*program.related_work_matrices, *[matrix for state in states for matrix in state.related_work_matrices]], direction
        )
        dossier = _first_dossier(states, direction)
        papers = _relevant_papers(states, direction, matrix, dossier)
        objections = _linked_objections(states, experiment)
        panel = _first_review_panel(program.review_panels, direction)
        claims = [claim for state in states for claim in state.claims]
        evidence = [span for state in states for span in state.evidence_spans]
        return cls(
            gap=gap,
            matrix=matrix,
            protocol=protocol,
            experiment=experiment,
            dossier=dossier,
            papers=papers,
            evidence_spans=evidence,
            claims_markdown=ClaimLedger(claims).export_markdown(),
            reviewer_objections_markdown=render_reviewer_objections(objections),
            rebuttal_plan=render_rebuttal_plans_markdown([panel]) if panel is not None else render_rebuttal_plan(objections),
            review_panel_markdown=render_review_panel_markdown(panel)
            if panel is not None
            else "# Review Panel\n\nNo review panel linked yet. Run `gapforge review-panel`.\n",
            review_panel=panel,
        )

    @classmethod
    def from_state(cls, state: ResearchRunState, direction: ResearchDirection) -> _ProjectExportContext:
        gap = _first_gap([state], direction.linked_gap_ids)
        experiment = _first_experiment([state], direction.linked_experiment_ids, direction.linked_gap_ids)
        protocol = _first_protocol(state.experiment_protocols, direction, experiment)
        matrix = _first_matrix(state.related_work_matrices, direction)
        dossier = _first_dossier([state], direction)
        papers = _relevant_papers([state], direction, matrix, dossier)
        objections = _linked_objections([state], experiment)
        return cls(
            gap=gap,
            matrix=matrix,
            protocol=protocol,
            experiment=experiment,
            dossier=dossier,
            papers=papers,
            evidence_spans=state.evidence_spans,
            claims_markdown=ClaimLedger(state.claims).export_markdown(),
            reviewer_objections_markdown=render_reviewer_objections(objections),
            rebuttal_plan=render_rebuttal_plan(objections),
            review_panel_markdown="# Review Panel\n\nNo project-level review panel linked to this run-level export.\n",
            review_panel=None,
        )


def _write_package_files(
    package_dir: Path,
    direction: ResearchDirection,
    context: _ProjectExportContext,
    missing: list[str],
) -> list[Path]:
    contents = {
        "README.md": _render_readme(direction, missing),
        "abstract.md": render_abstract(direction, context.gap, context.protocol),
        "intro_outline.md": render_intro_outline(direction, context.gap, context.dossier),
        "related_work_matrix.md": render_related_work_matrix_markdown(context.matrix)
        if context.matrix is not None
        else "# Related Work Matrix\n\nMissing related-work matrix. Run `gapforge related-work-matrix`.\n",
        "method_outline.md": render_method_outline(context.protocol, context.experiment),
        "experiment_protocol.md": render_protocol_markdown(context.protocol)
        if context.protocol is not None
        else "# Experiment Protocol\n\nMissing experiment protocol. Run `gapforge experiment-protocol`.\n",
        "expected_results.md": render_expected_results(context.protocol, context.experiment),
        "limitations.md": render_limitations(direction, context.gap, context.dossier, missing),
        "reviewer_objections.md": context.reviewer_objections_markdown,
        "review_panel.md": context.review_panel_markdown,
        "rebuttal_plan.md": context.rebuttal_plan,
        "bibliography.bib": render_bibtex(context.papers),
        "claim_ledger.md": context.claims_markdown,
        "evidence_index.md": _render_evidence_index(context),
    }
    paths = []
    for filename in EXPECTED_FILES:
        path = package_dir / filename
        path.write_text(contents[filename], encoding="utf-8")
        paths.append(path)
    return paths


def _render_readme(direction: ResearchDirection, missing: list[str]) -> str:
    lines = [
        f"# Paper Package: {direction.title}",
        "",
        "This package is a writing starter kit. It is not a completed paper and does not claim completed experimental results.",
        "",
        f"- Direction ID: `{direction.id}`",
        f"- Readiness: {direction.maturity}",
        f"- Readiness score: {direction.readiness_score:.2f}",
        "",
        "## Missing Requirements",
        "",
    ]
    lines.extend([f"- {item}" for item in missing] or ["- none"])
    lines.extend(["", "## Files", ""])
    lines.extend([f"- `{filename}`" for filename in EXPECTED_FILES])
    return "\n".join(lines).rstrip() + "\n"


def _render_evidence_index(context: _ProjectExportContext) -> str:
    lines = ["# Evidence Index", ""]
    if context.matrix is not None:
        lines.extend(["## Related Work Evidence", ""])
        for entry in context.matrix.entries:
            lines.append(f"- `{entry.paper_id}` {entry.relationship}: spans={', '.join(entry.evidence_span_ids) or 'none'}")
    lines.extend(["", "## Evidence Spans", ""])
    lines.extend(
        [
            f"- `{span.id}` paper=`{span.paper_id}` type={span.evidence_type} locator={span.locator or 'unknown'}: {span.quote}"
            for span in context.evidence_spans
        ]
        or ["- none"]
    )
    return "\n".join(lines).rstrip() + "\n"


def _missing_requirements(direction: ResearchDirection, context: _ProjectExportContext) -> list[str]:
    missing = []
    if direction.maturity not in {"experiment_ready", "manuscript_ready"}:
        missing.append(f"Direction is {direction.maturity}, not experiment_ready or manuscript_ready.")
    if context.matrix is None:
        missing.append("Related-work matrix is missing.")
    if context.protocol is None:
        missing.append("Experiment protocol is missing.")
    if context.dossier is None:
        missing.append("Novelty dossier is missing.")
    elif context.dossier.missing_searches:
        missing.append("Novelty dossier has missing searches: " + "; ".join(context.dossier.missing_searches))
    if context.review_panel is None:
        missing.append("Review panel is missing.")
    elif context.review_panel.decision_risk in {"reject_likely", "high"}:
        missing.append(f"Review panel decision risk is {context.review_panel.decision_risk}.")
    if context.experiment is None:
        missing.append("Experiment plan is missing.")
    if direction.blocking_issues:
        missing.extend(direction.blocking_issues)
    return _dedupe(missing)


def _require_direction(program: ResearchProgramState, direction_id: str) -> ResearchDirection:
    direction = next((item for item in program.research_directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _require_gap(state: ResearchRunState, gap_id: str) -> Gap:
    gap = next((item for item in state.gaps if item.id == gap_id), None)
    if gap is None:
        raise KeyError(f"Unknown gap: {gap_id}")
    return gap


def _first_gap(states: list[ResearchRunState], gap_ids: list[str]) -> Gap | None:
    return next((gap for state in states for gap in state.gaps if gap.id in gap_ids), None)


def _first_experiment(states: list[ResearchRunState], experiment_ids: list[str], gap_ids: list[str]) -> ExperimentPlan | None:
    return next(
        (
            experiment
            for state in states
            for experiment in state.experiments
            if experiment.id in experiment_ids or set(experiment.linked_gap_ids).intersection(gap_ids)
        ),
        None,
    )


def _first_protocol(
    protocols: list[ExperimentProtocol], direction: ResearchDirection, experiment: ExperimentPlan | None
) -> ExperimentProtocol | None:
    return next(
        (
            protocol
            for protocol in protocols
            if protocol.direction_id == direction.id
            or (experiment is not None and protocol.linked_experiment_plan_id == experiment.id)
            or protocol.direction_id in direction.linked_gap_ids
        ),
        None,
    )


def _first_matrix(matrices: list[RelatedWorkMatrix], direction: ResearchDirection) -> RelatedWorkMatrix | None:
    return next(
        (matrix for matrix in matrices if matrix.direction_id == direction.id or matrix.direction_id in direction.linked_gap_ids), None
    )


def _first_dossier(states: list[ResearchRunState], direction: ResearchDirection) -> NoveltyDossier | None:
    return next(
        (
            dossier
            for state in states
            for dossier in state.novelty_dossiers
            if dossier.target_id in direction.linked_gap_ids or dossier.target_id in direction.linked_novelty_dossier_ids
        ),
        None,
    )


def _linked_objections(states: list[ResearchRunState], experiment: ExperimentPlan | None) -> list:
    if experiment is None:
        return []
    return [objection for state in states for objection in state.reviewer_objections if objection.experiment_id == experiment.id]


def _first_review_panel(panels: list[ReviewPanel], direction: ResearchDirection) -> ReviewPanel | None:
    return next((panel for panel in panels if panel.experiment_or_direction_id == direction.id), None)


def _relevant_papers(
    states: list[ResearchRunState],
    direction: ResearchDirection,
    matrix: RelatedWorkMatrix | None,
    dossier: NoveltyDossier | None,
) -> list[Paper]:
    ids = set(direction.supporting_paper_ids + direction.counterevidence_paper_ids)
    if matrix is not None:
        ids.update(entry.paper_id for entry in matrix.entries)
    if dossier is not None:
        ids.update(dossier.top_prior_work)
        ids.update(dossier.candidates_considered)
        ids.update(str(row.get("paper_id", "")) for row in dossier.comparison_table)
    by_id = {paper.id: paper for state in states for paper in state.papers}
    return [paper for paper_id, paper in by_id.items() if paper_id in ids]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
