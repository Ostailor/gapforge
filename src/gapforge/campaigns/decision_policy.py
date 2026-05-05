"""Decision policy for v0.4 agentic campaign loops."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gapforge.campaigns import CampaignState
from gapforge.campaigns.budgets import CampaignBudgetStatus, agent_task_budget_available
from gapforge.models import ResearchDirection, ResearchProgramState, ResearchRunState
from gapforge.review.queue import open_review_items


@dataclass(frozen=True, slots=True)
class CampaignAssessment:
    campaign_state: CampaignState
    program: ResearchProgramState
    runs: list[ResearchRunState] = field(default_factory=list)
    budget_status: CampaignBudgetStatus | None = None
    retrieval_index_exists: bool = False
    source_coverage_confidence: str = "low"
    papers_seen: int = 0
    papers_with_full_text: int = 0
    paper_notes: int = 0
    gaps: int = 0
    evidence_matrices: int = 0
    novelty_dossiers: int = 0
    unknown_novelty_count: int = 0
    open_review_count: int = 0
    ready_direction: ResearchDirection | None = None
    exportable_direction: ResearchDirection | None = None
    pending_task_id_with_outputs: str = ""


@dataclass(frozen=True, slots=True)
class CampaignAction:
    decision_type: str
    step_type: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    task_type: str = ""
    terminal: bool = False
    status: str = "pending"


class CampaignDecisionPolicy:
    """Deterministic, evidence-first policy for selecting the next campaign action."""

    def decide(self, assessment: CampaignAssessment) -> CampaignAction:
        budget = assessment.budget_status
        if budget is not None and budget.exhausted:
            return CampaignAction(
                decision_type="stop",
                step_type="stop",
                reason="Campaign budget is exhausted.",
                evidence=budget.reasons,
                terminal=True,
                status="complete",
            )
        if assessment.pending_task_id_with_outputs:
            return CampaignAction(
                decision_type="import_outputs",
                step_type="review",
                reason="A campaign task has output files waiting for validation and import.",
                evidence=[assessment.pending_task_id_with_outputs],
                status="running",
            )
        if assessment.open_review_count:
            return CampaignAction(
                decision_type="request_human_review",
                step_type="human_review",
                reason="Open human review queue items block further campaign maturation.",
                evidence=[f"open_review_items={assessment.open_review_count}"],
                terminal=True,
                status="blocked",
            )
        if _source_coverage_poor(assessment):
            return CampaignAction(
                decision_type="search_more",
                step_type="search",
                reason="Source coverage is too weak for mapping, novelty, or experiment decisions.",
                evidence=[
                    f"source_coverage_confidence={assessment.source_coverage_confidence}",
                    f"papers_seen={assessment.papers_seen}",
                ],
                status="running",
            )
        if not assessment.retrieval_index_exists:
            return CampaignAction(
                decision_type="build_index",
                step_type="retrieve",
                reason="No campaign/project retrieval index exists yet.",
                evidence=[f"project_id={assessment.program.project.id}"],
                status="running",
            )
        if _full_text_missing(assessment):
            return CampaignAction(
                decision_type="parse_more",
                step_type="parse",
                reason="Attached runs have papers but little or no parsed full-text coverage.",
                evidence=[f"papers={assessment.papers_seen}", f"full_text_papers={assessment.papers_with_full_text}"],
                status="running",
            )
        if assessment.paper_notes == 0:
            return _agent_or_deterministic(
                assessment,
                deterministic_type="read_more",
                step_type="read",
                task_type="deep_reader_batch",
                reason="Important papers have not been read into structured notes.",
                evidence=[f"paper_notes={assessment.paper_notes}"],
            )
        if assessment.gaps == 0 or _gaps_are_weak(assessment):
            return _agent_or_deterministic(
                assessment,
                deterministic_type="gap_synthesis",
                step_type="gap_mining",
                task_type="gap_synthesis",
                reason="Gaps are missing or too weakly evidenced for research direction decisions.",
                evidence=[f"gaps={assessment.gaps}", f"evidence_matrices={assessment.evidence_matrices}"],
            )
        if assessment.novelty_dossiers == 0 or assessment.unknown_novelty_count:
            return _agent_or_deterministic(
                assessment,
                deterministic_type="check_novelty",
                step_type="novelty",
                task_type="novelty_reviewer",
                reason="Novelty is unchecked or unknown for promising campaign gaps.",
                evidence=[
                    f"novelty_dossiers={assessment.novelty_dossiers}",
                    f"unknown_novelty={assessment.unknown_novelty_count}",
                ],
            )
        if assessment.ready_direction is not None:
            return CampaignAction(
                decision_type="reviewer_panel",
                step_type="review",
                task_type="reviewer_panel",
                reason=f"Direction {assessment.ready_direction.id} is experiment-ready and needs reviewer attack.",
                evidence=[assessment.ready_direction.id],
                status="running",
            )
        if assessment.exportable_direction is not None:
            return CampaignAction(
                decision_type="export_package",
                step_type="export",
                reason=f"Direction {assessment.exportable_direction.id} is manuscript-ready for package export.",
                evidence=[assessment.exportable_direction.id],
                status="running",
            )
        return CampaignAction(
            decision_type="stop",
            step_type="stop",
            reason="No useful direction is ready under current evidence and budget.",
            evidence=["stop_not_ready"],
            terminal=True,
            status="complete",
        )


def build_campaign_assessment(
    campaign_state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    *,
    budget_status: CampaignBudgetStatus | None = None,
) -> CampaignAssessment:
    project_root = Path(program.project.root_dir)
    retrieval_index_exists = (project_root / "retrieval" / "manifest.json").exists()
    coverages = [run.source_coverage for run in runs if run.source_coverage is not None]
    confidence = _best_confidence([coverage.confidence for coverage in coverages])
    papers_seen = sum(len(run.papers) for run in runs)
    full_text = len({section.paper_id for run in runs for section in run.paper_sections if section.text.strip()})
    novelty_dossiers = [dossier for run in runs for dossier in run.novelty_dossiers]
    queue = program.review_queue
    return CampaignAssessment(
        campaign_state=campaign_state,
        program=program,
        runs=runs,
        budget_status=budget_status,
        retrieval_index_exists=retrieval_index_exists,
        source_coverage_confidence=confidence,
        papers_seen=papers_seen,
        papers_with_full_text=full_text,
        paper_notes=sum(len(run.paper_notes) for run in runs),
        gaps=sum(len(run.gaps) for run in runs),
        evidence_matrices=sum(len(run.gap_evidence_matrices) for run in runs),
        novelty_dossiers=len(novelty_dossiers),
        unknown_novelty_count=sum(1 for dossier in novelty_dossiers if dossier.verdict == "unknown"),
        open_review_count=len(open_review_items(queue)),
        ready_direction=_first_direction(program.research_directions, {"experiment_ready"}),
        exportable_direction=_first_direction(program.research_directions, {"manuscript_ready"}),
        pending_task_id_with_outputs=_pending_task_with_outputs(campaign_state, program.project.root_dir),
    )


def _source_coverage_poor(assessment: CampaignAssessment) -> bool:
    return not assessment.runs or assessment.papers_seen == 0 or assessment.source_coverage_confidence == "low"


def _full_text_missing(assessment: CampaignAssessment) -> bool:
    return assessment.papers_seen > 0 and assessment.papers_with_full_text == 0


def _gaps_are_weak(assessment: CampaignAssessment) -> bool:
    return assessment.gaps > 0 and assessment.evidence_matrices == 0


def _agent_or_deterministic(
    assessment: CampaignAssessment,
    *,
    deterministic_type: str,
    step_type: str,
    task_type: str,
    reason: str,
    evidence: list[str],
) -> CampaignAction:
    if assessment.campaign_state.campaign.mode in {"fake_agent", "codex_task_pack", "codex_direct", "manual_handoff"}:
        if not agent_task_budget_available(assessment.campaign_state):
            return CampaignAction(
                decision_type="stop",
                step_type="stop",
                reason="Agent task budget is exhausted.",
                evidence=[f"requested_task={task_type}"],
                terminal=True,
                status="complete",
            )
        return CampaignAction(
            decision_type="ask_codex",
            step_type=step_type,
            task_type=task_type,
            reason=reason,
            evidence=evidence,
            status="running",
        )
    return CampaignAction(
        decision_type=deterministic_type,
        step_type=step_type,
        reason=reason,
        evidence=evidence,
        status="running",
    )


def _first_direction(directions: list[ResearchDirection], maturities: set[str]) -> ResearchDirection | None:
    candidates = [direction for direction in directions if direction.maturity in maturities]
    candidates = [direction for direction in candidates if direction.maturity != "rejected"]
    return sorted(candidates, key=lambda item: item.readiness_score, reverse=True)[0] if candidates else None


def _best_confidence(values: list[str]) -> str:
    if "high" in values:
        return "high"
    if "medium" in values:
        return "medium"
    return "low"


def _pending_task_with_outputs(campaign_state: CampaignState, project_root: str) -> str:
    root = Path(project_root) / "campaigns" / campaign_state.campaign.id / "agent_tasks"
    imported_task_ids = {record.task_id for record in campaign_state.imports if record.status in {"applied", "partial", "valid"}}
    for step in reversed(campaign_state.steps):
        if not step.task_spec_id or step.task_spec_id in imported_task_ids:
            continue
        if step.status not in {"pending", "blocked"}:
            continue
        outputs_dir = root / step.task_spec_id / "outputs"
        if outputs_dir.exists() and any(path.is_file() for path in outputs_dir.iterdir()):
            return step.task_spec_id
    return ""
