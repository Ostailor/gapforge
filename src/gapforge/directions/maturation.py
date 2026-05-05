"""Project-level research direction maturation workflow."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.directions.cards import render_direction_card, write_direction_card
from gapforge.directions.scoring import readiness_score
from gapforge.models import (
    ExperimentPlan,
    Gap,
    GapEvidenceMatrix,
    HumanReviewRecord,
    NoveltyAssessment,
    NoveltyDossier,
    ProjectMemoryRecord,
    Provenance,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ReviewerObjection,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso


@dataclass(slots=True)
class DirectionContext:
    runs: list[ResearchRunState]
    gaps: dict[str, Gap]
    matrices: dict[str, GapEvidenceMatrix]
    experiments_by_gap: dict[str, list[ExperimentPlan]]
    novelty_by_gap: dict[str, NoveltyAssessment]
    dossiers_by_gap: dict[str, NoveltyDossier]
    related_work_by_direction: dict[str, RelatedWorkMatrix]
    related_work_by_gap: dict[str, RelatedWorkMatrix]
    objections_by_experiment: dict[str, list[ReviewerObjection]]
    human_reviews: list[HumanReviewRecord]


class DirectionMaturationManager:
    """Create, mature, reject, and render project-level research directions."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)

    def create_direction(self, project_id: str, gap_id: str) -> ResearchDirection:
        program = self.project_manager.load_project(project_id)
        context = self._context(program)
        gap = context.gaps.get(gap_id)
        if gap is None:
            raise KeyError(f"Unknown attached-run gap: {gap_id}")
        direction_id = _direction_id(project_id, gap_id)
        direction = _find_direction(program, direction_id)
        if direction is None:
            direction = ResearchDirection(
                id=direction_id,
                project_id=project_id,
                title=gap.title or gap.description[:80] or gap.id,
                summary=gap.description,
                linked_gap_ids=[gap.id],
                supporting_paper_ids=_unique([*gap.supporting_paper_ids, *gap.linked_paper_ids]),
                maturity="seed",
                readiness_score=readiness_score("seed", []),
                next_actions=["Mature direction against evidence, novelty, experiment, reviewer, and human-review gates."],
                provenance=_provenance("create-direction", [gap.id], "Research direction created from a gap."),
            )
            program.research_directions.append(direction)
        self._save(program, context)
        return direction

    def mature_direction(self, project_id: str, direction_id: str) -> ResearchDirection:
        program = self.project_manager.load_project(project_id)
        context = self._context(program)
        direction = _require_direction(program, direction_id)
        maturity, blockers, actions = self._evaluate(direction, context, program)
        direction.maturity = maturity
        direction.readiness_score = readiness_score(maturity, blockers)
        direction.blocking_issues = blockers
        direction.next_actions = actions
        self._update_links(direction, context)
        self._save(program, context)
        return direction

    def reject_direction(self, project_id: str, direction_id: str, reason: str) -> ResearchDirection:
        program = self.project_manager.load_project(project_id)
        context = self._context(program)
        direction = _require_direction(program, direction_id)
        direction.maturity = "rejected"
        direction.readiness_score = 0.0
        direction.blocking_issues = _unique([*direction.blocking_issues, reason])
        direction.next_actions = ["Keep rejected direction in project memory to prevent accidental rediscovery."]
        program.memory_records.append(
            ProjectMemoryRecord(
                id=f"memory-decision-{_stable_id(project_id, direction_id, str(len(program.memory_records)))}",
                project_id=project_id,
                record_type="decision",
                text=f"reject direction:{direction_id} | {reason}",
                linked_object_ids=[direction_id],
                status="rejected",
                confidence="high",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
                provenance=_provenance("reject-direction", [direction_id], "Human/project decision rejected a research direction."),
            )
        )
        self._save(program, context)
        return direction

    def render_card(self, project_id: str, direction_id: str) -> str:
        program = self.project_manager.load_project(project_id)
        context = self._context(program)
        direction = _require_direction(program, direction_id)
        return render_direction_card(
            direction,
            evidence_locators=_evidence_locators(direction, context),
            novelty_summary=_novelty_summary(direction, context),
            reviewer_summary=_reviewer_summary(direction, context),
        )

    def write_card(self, project_id: str, direction_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        context = self._context(program)
        direction = _require_direction(program, direction_id)
        return write_direction_card(
            Path(program.project.root_dir),
            direction,
            evidence_locators=_evidence_locators(direction, context),
            novelty_summary=_novelty_summary(direction, context),
            reviewer_summary=_reviewer_summary(direction, context),
        )

    def write_reports(self, program: ResearchProgramState, context: DirectionContext | None = None) -> None:
        context = context or self._context(program)
        root = Path(program.project.root_dir)
        for direction in program.research_directions:
            write_direction_card(
                root,
                direction,
                evidence_locators=_evidence_locators(direction, context),
                novelty_summary=_novelty_summary(direction, context),
                reviewer_summary=_reviewer_summary(direction, context),
            )
        _write_maturity_report(root, program.research_directions)

    def _evaluate(
        self,
        direction: ResearchDirection,
        context: DirectionContext,
        program: ResearchProgramState,
    ) -> tuple[str, list[str], list[str]]:
        if _is_rejected(direction, context, program):
            return (
                "rejected",
                ["Direction rejected by novelty, human review, reviewer fatal issue, or supersession."],
                ["Do not advance this direction unless a human explicitly revises it."],
            )
        if not direction.linked_gap_ids:
            return "seed", ["No linked gap."], ["Link the direction to a gap."]
        linked_gaps = [context.gaps[gap_id] for gap_id in direction.linked_gap_ids if gap_id in context.gaps]
        if not linked_gaps:
            return "seed", ["Linked gap is not available in attached runs."], ["Attach or sync the run containing the gap."]

        candidate_blockers = _candidate_blockers(linked_gaps, direction)
        if candidate_blockers:
            return "seed", candidate_blockers, _actions_for(candidate_blockers)

        validated_blockers = _validated_gap_blockers(direction, context)
        if validated_blockers:
            return "candidate", validated_blockers, _actions_for(validated_blockers)

        experiment_blockers = _experiment_ready_blockers(direction, context)
        if experiment_blockers:
            return "validated_gap", experiment_blockers, _actions_for(experiment_blockers)

        manuscript_blockers = _manuscript_ready_blockers(direction, context, program)
        if manuscript_blockers:
            return "experiment_ready", manuscript_blockers, _actions_for(manuscript_blockers)

        return "manuscript_ready", [], ["Prepare manuscript skeleton and export evidence-linked claim table."]

    def _update_links(self, direction: ResearchDirection, context: DirectionContext) -> None:
        for gap_id in direction.linked_gap_ids:
            gap = context.gaps.get(gap_id)
            if gap is not None:
                direction.supporting_paper_ids = _unique(
                    [*direction.supporting_paper_ids, *gap.supporting_paper_ids, *gap.linked_paper_ids]
                )
            experiments = context.experiments_by_gap.get(gap_id, [])
            direction.linked_experiment_ids = _unique([*direction.linked_experiment_ids, *[experiment.id for experiment in experiments]])
            dossier = context.dossiers_by_gap.get(gap_id)
            if dossier is not None:
                direction.linked_novelty_dossier_ids = _unique([*direction.linked_novelty_dossier_ids, dossier.target_id])
            matrix = context.matrices.get(gap_id)
            if matrix is not None:
                direction.counterevidence_paper_ids = _unique([*direction.counterevidence_paper_ids, *matrix.papers_countering])

    def _context(self, program: ResearchProgramState) -> DirectionContext:
        runs = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        gaps = {gap.id: gap for state in runs for gap in state.gaps}
        matrices = {matrix.gap_id: matrix for state in runs for matrix in state.gap_evidence_matrices}
        experiments_by_gap: dict[str, list[ExperimentPlan]] = {}
        for state in runs:
            for experiment in state.experiments:
                for gap_id in experiment.linked_gap_ids:
                    experiments_by_gap.setdefault(gap_id, []).append(experiment)
        return DirectionContext(
            runs=runs,
            gaps=gaps,
            matrices=matrices,
            experiments_by_gap=experiments_by_gap,
            novelty_by_gap={item.target_gap_or_hypothesis_id: item for state in runs for item in state.novelty_assessments},
            dossiers_by_gap={item.target_id: item for state in runs for item in state.novelty_dossiers},
            related_work_by_direction={item.direction_id: item for item in program.related_work_matrices},
            related_work_by_gap={item.direction_id: item for state in runs for item in state.related_work_matrices},
            objections_by_experiment=_objections_by_experiment(runs),
            human_reviews=[review for state in runs for review in state.human_reviews],
        )

    def _save(self, program: ResearchProgramState, context: DirectionContext) -> None:
        self.write_reports(program, context)
        self.project_manager.save_project(program)


def _candidate_blockers(gaps: list[Gap], direction: ResearchDirection) -> list[str]:
    blockers = []
    if not direction.supporting_paper_ids and not any(gap.supporting_paper_ids or gap.linked_paper_ids for gap in gaps):
        blockers.append("Candidate gate requires supporting papers.")
    if not any(gap.risk_that_gap_is_fake for gap in gaps):
        blockers.append("Candidate gate requires risk-that-gap-is-fake.")
    return blockers


def _validated_gap_blockers(direction: ResearchDirection, context: DirectionContext) -> list[str]:
    blockers = []
    if not any(gap_id in context.matrices for gap_id in direction.linked_gap_ids):
        blockers.append("Validated-gap gate requires a GapEvidenceMatrix.")
    if not _has_counterevidence_search(direction, context):
        blockers.append("Validated-gap gate requires counterevidence or novelty/citation search.")
    if not (_coverage_at_least_medium(context) or _has_coverage_waiver(direction, context)):
        blockers.append("Validated-gap gate requires medium source coverage or explicit human waiver.")
    return blockers


def _experiment_ready_blockers(direction: ResearchDirection, context: DirectionContext) -> list[str]:
    blockers = []
    if not any(_non_rejected_dossier(context.dossiers_by_gap.get(gap_id)) for gap_id in direction.linked_gap_ids):
        blockers.append("Experiment-ready gate requires a non-rejected novelty dossier.")
    experiments = _linked_experiments(direction, context)
    if not experiments:
        blockers.append("Experiment-ready gate requires an experiment plan.")
    elif not any(
        experiment.baselines and experiment.metrics and experiment.what_result_would_falsify_the_idea for experiment in experiments
    ):
        blockers.append("Experiment-ready gate requires baselines, metrics, and falsification condition.")
    return blockers


def _manuscript_ready_blockers(
    direction: ResearchDirection,
    context: DirectionContext,
    program: ResearchProgramState,
) -> list[str]:
    blockers = []
    experiments = _linked_experiments(direction, context)
    fatal = [
        objection
        for experiment in experiments
        for objection in context.objections_by_experiment.get(experiment.id, [])
        if objection.severity == "fatal" and objection.blocks_submission
    ]
    if fatal:
        blockers.append("Manuscript-ready gate requires no fatal blocking reviewer issues.")
    if not _has_related_work_matrix(direction, context):
        blockers.append("Manuscript-ready gate requires a related-work comparison matrix.")
    if program.claim_graph is not None and program.claim_graph.unresolved_contradictions:
        blockers.append("Manuscript-ready gate requires no unresolved claim graph contradictions.")
    if not _has_human_approval(direction, context, program):
        blockers.append("Manuscript-ready gate requires human approval.")
    return blockers


def _is_rejected(direction: ResearchDirection, context: DirectionContext, program: ResearchProgramState) -> bool:
    for gap_id in direction.linked_gap_ids:
        matrix = context.related_work_by_direction.get(direction.id) or context.related_work_by_gap.get(gap_id)
        if matrix is not None and any(entry.relationship == "directly_solves" for entry in matrix.entries):
            return True
        gap = context.gaps.get(gap_id)
        assessment = context.novelty_by_gap.get(gap_id)
        dossier = context.dossiers_by_gap.get(gap_id)
        if gap is not None and gap.novelty_status == "likely_not_new":
            return True
        if assessment is not None and assessment.verdict == "reject":
            return True
        if dossier is not None and dossier.verdict == "reject":
            return True
    linked_experiment_ids = {experiment.id for experiment in _linked_experiments(direction, context)}
    if any(
        review.action == "reject" and review.object_id in {*direction.linked_gap_ids, *linked_experiment_ids}
        for review in context.human_reviews
    ):
        return True
    if any(record.status in {"rejected", "superseded"} and direction.id in record.linked_object_ids for record in program.memory_records):
        return True
    return any(
        objection.severity == "fatal" and objection.blocks_submission
        for experiment_id in linked_experiment_ids
        for objection in context.objections_by_experiment.get(experiment_id, [])
    )


def _linked_experiments(direction: ResearchDirection, context: DirectionContext) -> list[ExperimentPlan]:
    experiments: list[ExperimentPlan] = []
    for gap_id in direction.linked_gap_ids:
        experiments.extend(context.experiments_by_gap.get(gap_id, []))
    return experiments


def _has_counterevidence_search(direction: ResearchDirection, context: DirectionContext) -> bool:
    for gap_id in direction.linked_gap_ids:
        matrix = context.matrices.get(gap_id)
        if matrix is not None and (matrix.papers_countering or any(row.supports_or_counters == "counters" for row in matrix.evidence_rows)):
            return True
        assessment = context.novelty_by_gap.get(gap_id)
        if assessment is not None and assessment.search_queries_used:
            return True
    return any(
        record.purpose in {"novelty", "citation_expansion", "related_work"} for state in context.runs for record in state.search_queries
    )


def _coverage_at_least_medium(context: DirectionContext) -> bool:
    return any(state.source_coverage is not None and state.source_coverage.confidence in {"medium", "high"} for state in context.runs)


def _has_coverage_waiver(direction: ResearchDirection, context: DirectionContext) -> bool:
    ids = set(direction.linked_gap_ids + direction.linked_experiment_ids + [direction.id])
    return any(
        review.object_id in ids and "waiv" in review.note.lower() and "coverage" in review.note.lower() for review in context.human_reviews
    )


def _non_rejected_dossier(dossier: NoveltyDossier | None) -> bool:
    return dossier is not None and dossier.verdict in {"pursue", "revise", "unknown"}


def _has_related_work_matrix(direction: ResearchDirection, context: DirectionContext) -> bool:
    if direction.id in context.related_work_by_direction:
        return bool(context.related_work_by_direction[direction.id].entries)
    return any(gap_id in context.related_work_by_gap and context.related_work_by_gap[gap_id].entries for gap_id in direction.linked_gap_ids)


def _has_human_approval(direction: ResearchDirection, context: DirectionContext, program: ResearchProgramState) -> bool:
    ids = set(direction.linked_gap_ids + direction.linked_experiment_ids + [direction.id])
    if any(review.action == "approve" and review.object_id in ids for review in context.human_reviews):
        return True
    return any(
        record.record_type == "decision"
        and record.status == "active"
        and direction.id in record.linked_object_ids
        and "approve" in record.text.lower()
        for record in program.memory_records
    )


def _evidence_locators(direction: ResearchDirection, context: DirectionContext) -> list[str]:
    locators: list[str] = []
    for gap_id in direction.linked_gap_ids:
        matrix = context.matrices.get(gap_id)
        if matrix is not None:
            locators.extend(row.locator for row in matrix.evidence_rows if row.locator)
        dossier = context.dossiers_by_gap.get(gap_id)
        if dossier is not None:
            locators.extend(span.locator for span in dossier.evidence_spans if span.locator)
    return _unique(locators)


def _novelty_summary(direction: ResearchDirection, context: DirectionContext) -> str:
    parts = []
    for gap_id in direction.linked_gap_ids:
        dossier = context.dossiers_by_gap.get(gap_id)
        if dossier is not None:
            parts.append(f"{gap_id}: verdict={dossier.verdict}, strength={dossier.novelty_strength}.")
    return " ".join(parts)


def _reviewer_summary(direction: ResearchDirection, context: DirectionContext) -> str:
    experiments = _linked_experiments(direction, context)
    objections = [item for experiment in experiments for item in context.objections_by_experiment.get(experiment.id, [])]
    if not objections:
        return "No reviewer simulation objections linked."
    fatal = sum(1 for item in objections if item.severity == "fatal")
    major = sum(1 for item in objections if item.severity == "major")
    return f"Reviewer simulation linked {len(objections)} objection(s): fatal={fatal}, major={major}."


def _objections_by_experiment(runs: list[ResearchRunState]) -> dict[str, list[ReviewerObjection]]:
    grouped: dict[str, list[ReviewerObjection]] = {}
    for state in runs:
        for objection in state.reviewer_objections:
            if objection.experiment_id:
                grouped.setdefault(objection.experiment_id, []).append(objection)
    return grouped


def _write_maturity_report(project_dir: Path, directions: list[ResearchDirection]) -> Path:
    path = project_dir / "direction_maturity_report.md"
    lines = ["# Direction Maturity Report", ""]
    for direction in sorted(directions, key=lambda item: (-item.readiness_score, item.title)):
        lines.extend(
            [
                f"## {direction.title}",
                "",
                f"- Direction ID: `{direction.id}`",
                f"- Maturity: {direction.maturity}",
                f"- Readiness score: {direction.readiness_score:.2f}",
                f"- Blocking issues: {'; '.join(direction.blocking_issues) or 'none'}",
                f"- Next actions: {'; '.join(direction.next_actions) or 'none'}",
                "",
            ]
        )
    if not directions:
        lines.append("No research directions recorded.")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _require_direction(program: ResearchProgramState, direction_id: str) -> ResearchDirection:
    direction = _find_direction(program, direction_id)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _find_direction(program: ResearchProgramState, direction_id: str) -> ResearchDirection | None:
    return next((direction for direction in program.research_directions if direction.id == direction_id), None)


def _direction_id(project_id: str, gap_id: str) -> str:
    return f"direction-{_stable_id(project_id, gap_id)}"


def _actions_for(blockers: list[str]) -> list[str]:
    actions: list[str] = []
    for blocker in blockers:
        text = blocker.lower()
        if "supporting papers" in text:
            actions.append("Link supporting papers to the gap or direction.")
        elif "risk" in text:
            actions.append("Record risk-that-gap-is-fake before promoting the direction.")
        elif "gapevidencematrix" in text:
            actions.append("Run gap mining to build a GapEvidenceMatrix.")
        elif "counterevidence" in text:
            actions.append("Run novelty/citation expansion or add counterevidence rows.")
        elif "source coverage" in text:
            actions.append("Improve source coverage or record an explicit human coverage waiver.")
        elif "novelty" in text:
            actions.append("Run novelty dossier and closest-prior-work checks.")
        elif "experiment" in text:
            actions.append("Design an experiment with baselines, metrics, and falsification.")
        elif "reviewer" in text:
            actions.append("Resolve fatal reviewer blockers.")
        elif "claim graph" in text:
            actions.append("Resolve claim graph contradictions.")
        elif "human approval" in text:
            actions.append("Record human approval before manuscript readiness.")
    return _unique(actions) or ["Address the listed blocking issues."]


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]


def _provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(created_by_skill=skill, source_ids=source_ids, timestamp=utc_now_iso(), reasoning_summary=summary)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
