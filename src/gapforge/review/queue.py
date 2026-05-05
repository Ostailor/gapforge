"""Human review queue generation and audit helpers."""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    Claim,
    ProjectMemoryRecord,
    Provenance,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    ReviewQueue,
    ReviewQueueItem,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.review.audit import latest_action
from gapforge.state import ResearchStateManager, utc_now_iso

OPEN_STATUSES = {"open"}
TERMINAL_STATUSES = {"completed", "dismissed"}


class ReviewQueueManager:
    """Build and maintain human review queues for runs and projects."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.state_manager = ResearchStateManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def build_for_run(self, run_id: str) -> ReviewQueue:
        state = self.state_manager.load_latest() if run_id == "latest" else self.state_manager.load_run(run_id)
        if state is None:
            raise FileNotFoundError("No run state found.")
        queue = build_run_review_queue(state, existing=state.review_queue)
        state.review_queue = queue
        self.state_manager.save_run(state)
        return queue

    def build_for_project(self, project_id: str) -> ReviewQueue:
        program = self.project_manager.load_project(project_id)
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        queue = build_project_review_queue(program, states, existing=program.review_queue)
        program.review_queue = queue
        self.project_manager.save_project(program)
        for state in states:
            state.review_queue = build_run_review_queue(state, project_id=program.project.id, existing=state.review_queue)
            self.state_manager.save_run(state)
        return queue

    def complete_project_item(self, project_id: str, item_id: str, *, note: str = "", reviewer: str = "human") -> ReviewQueueItem:
        program = self.project_manager.load_project(project_id)
        queue = program.review_queue or self.build_for_project(project_id)
        item = _require_item(queue, item_id)
        item.status = "completed"
        item.assigned_to = reviewer
        item.completed_at = utc_now_iso()
        _append_queue_decision(program, item, "completed", note, reviewer)
        program.review_queue = _refresh_summary(queue)
        self.project_manager.save_project(program)
        return item

    def dismiss_project_item(self, project_id: str, item_id: str, *, reason: str = "", reviewer: str = "human") -> ReviewQueueItem:
        program = self.project_manager.load_project(project_id)
        queue = program.review_queue or self.build_for_project(project_id)
        item = _require_item(queue, item_id)
        item.status = "dismissed"
        item.assigned_to = reviewer
        item.completed_at = utc_now_iso()
        _append_queue_decision(program, item, "dismissed", reason, reviewer)
        program.review_queue = _refresh_summary(queue)
        self.project_manager.save_project(program)
        return item


def build_run_review_queue(
    state: ResearchRunState,
    *,
    project_id: str = "",
    existing: ReviewQueue | None = None,
) -> ReviewQueue:
    """Generate run-level review items and preserve completed/dismissed state."""

    generated = list(_run_review_items(state, project_id or str(state.config.get("project_id", ""))))
    queue = ReviewQueue(
        project_id=project_id or str(state.config.get("project_id", "")),
        items=_merge_queue_items(existing.items if existing else [], generated),
        provenance=_queue_provenance([state.run_id], "Run review queue generated from state risks."),
    )
    return _refresh_summary(queue)


def build_project_review_queue(
    program: ResearchProgramState,
    states: list[ResearchRunState],
    *,
    existing: ReviewQueue | None = None,
) -> ReviewQueue:
    """Generate a project-level queue from project memory plus attached runs."""

    project_id = program.project.id
    generated: list[ReviewQueueItem] = []
    for state in states:
        generated.extend(_run_review_items(state, project_id))
    generated.extend(_project_review_items(program, states))
    queue = ReviewQueue(
        project_id=project_id,
        items=_merge_queue_items(existing.items if existing else [], generated),
        provenance=_queue_provenance([project_id, *program.run_ids], "Project review queue generated from cumulative run risks."),
    )
    return _refresh_summary(queue)


def render_review_queue_markdown(queue: ReviewQueue | None) -> str:
    if queue is None:
        return "# Human Review Queue\n\nNo review queue has been generated yet.\n"
    counts = Counter(item.status for item in queue.items)
    lines = [
        "# Human Review Queue",
        "",
        f"- Project ID: `{queue.project_id or 'run-only'}`",
        f"- Summary: {queue.summary or _summary_from_counts(counts)}",
        f"- Open items: {counts.get('open', 0)}",
        f"- Completed items: {counts.get('completed', 0)}",
        f"- Dismissed items: {counts.get('dismissed', 0)}",
        "",
    ]
    for status in ["open", "completed", "dismissed"]:
        items = [item for item in queue.items if item.status == status]
        lines.extend([f"## {status.title()} Items", ""])
        if not items:
            lines.append("- none")
            lines.append("")
            continue
        for item in sorted(items, key=_item_sort_key):
            lines.extend(
                [
                    f"### {item.id}",
                    "",
                    f"- Object: `{item.object_type}:{item.object_id}`",
                    f"- Run: `{item.run_id or 'project'}`",
                    f"- Priority: {item.priority}",
                    f"- Requested by: {item.requested_by_skill}",
                    f"- Assigned to: {item.assigned_to or 'unassigned'}",
                    f"- Created: {item.created_at or 'unknown'}",
                    f"- Completed: {item.completed_at or 'not completed'}",
                    f"- Reason: {item.reason}",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def open_review_items(queue: ReviewQueue | None) -> list[ReviewQueueItem]:
    if queue is None:
        return []
    return [item for item in queue.items if item.status in OPEN_STATUSES]


def _run_review_items(state: ResearchRunState, project_id: str) -> Iterable[ReviewQueueItem]:
    for claim in state.claims:
        if _claim_needs_review(claim):
            yield _item(
                project_id=project_id,
                run_id=state.run_id,
                object_type="claim",
                object_id=claim.id,
                priority="high",
                requested_by_skill=claim.created_by_skill or claim.provenance.created_by_skill or "claim-ledger",
                reason=f"High-impact claim is {claim.status} with confidence={claim.confidence} and needs human verification.",
                source_ids=[state.run_id, claim.id],
            )
        elif claim.status == "contested":
            yield _item(
                project_id=project_id,
                run_id=state.run_id,
                object_type="claim",
                object_id=claim.id,
                priority="medium",
                requested_by_skill="claim-graph",
                reason="Claim is contested and should be resolved before it influences direction maturity.",
                source_ids=[state.run_id, claim.id],
            )

    promising_gap_ids = {gap.id for gap in state.gaps if gap.confidence in {"medium", "high"} and gap.novelty_status != "likely_not_new"}
    for dossier in state.novelty_dossiers:
        if dossier.verdict == "unknown" and dossier.target_id in promising_gap_ids:
            yield _item(
                project_id=project_id,
                run_id=state.run_id,
                object_type="novelty_dossier",
                object_id=dossier.target_id,
                priority="high",
                requested_by_skill=dossier.provenance.created_by_skill or "novelty-gate",
                reason="Novelty dossier is unknown for a promising gap; human prior-work judgment is needed.",
                source_ids=[state.run_id, dossier.target_id],
            )
        if dossier.verdict == "contested":
            yield _item(
                project_id=project_id,
                run_id=state.run_id,
                object_type="novelty_dossier",
                object_id=dossier.target_id,
                priority="high",
                requested_by_skill="novelty-gate-llm",
                reason="Model-assisted novelty output is contested against deterministic evidence.",
                source_ids=[state.run_id, dossier.target_id],
            )

    for experiment in state.experiments:
        reviewed = latest_action(state, "experiment", experiment.id)
        close_to_ready = experiment.paper_ready or (
            experiment.confidence in {"medium", "high"} and bool(experiment.baselines) and bool(experiment.metrics)
        )
        if close_to_ready and not reviewed:
            yield _item(
                project_id=project_id,
                run_id=state.run_id,
                object_type="experiment",
                object_id=experiment.id,
                priority="medium" if not experiment.paper_ready else "high",
                requested_by_skill="experiment-designer",
                reason="Experiment is close to manuscript-ready and needs human sign-off before promotion.",
                source_ids=[state.run_id, experiment.id],
            )

    assessment = state.coverage_stopping_assessment
    if assessment and (not assessment.enough_for_novelty or not assessment.enough_for_experiment_design):
        yield _item(
            project_id=project_id,
            run_id=state.run_id,
            object_type="source_policy",
            object_id=assessment.profile_id,
            priority="medium",
            requested_by_skill="source-policy",
            reason="Source policy coverage is insufficient; a human waiver or additional search decision is needed.",
            source_ids=[state.run_id, assessment.profile_id],
        )

    if state.config.get("_active_loop_human_review_requested"):
        yield _item(
            project_id=project_id,
            run_id=state.run_id,
            object_type="run",
            object_id=state.run_id,
            priority="medium",
            requested_by_skill="active-loop",
            reason="Active loop explicitly paused for human review.",
            source_ids=[state.run_id],
        )

    if state.config.get("_strict_report_blocked_by_human_decision"):
        yield _item(
            project_id=project_id,
            run_id=state.run_id,
            object_type="run",
            object_id=state.run_id,
            priority="high",
            requested_by_skill="reporting",
            reason="Strict report is blocked until a human decision resolves the remaining review gate.",
            source_ids=[state.run_id],
        )


def _project_review_items(program: ResearchProgramState, states: list[ResearchRunState]) -> Iterable[ReviewQueueItem]:
    if program.claim_graph is not None:
        for index, contradiction in enumerate(program.claim_graph.unresolved_contradictions, start=1):
            yield _item(
                project_id=program.project.id,
                run_id="",
                object_type="claim_contradiction",
                object_id=f"contradiction-{index}",
                priority="high",
                requested_by_skill="claim-graph",
                reason=f"Unresolved claim contradiction: {contradiction}",
                source_ids=[program.project.id],
            )

    known_dossiers = {dossier.target_id: dossier for state in states for dossier in state.novelty_dossiers}
    approved_directions = _approved_project_object_ids(program, "direction")
    for direction in program.research_directions:
        if direction.maturity == "rejected":
            continue
        if _promising_direction_needs_novelty_review(direction, known_dossiers):
            yield _item(
                project_id=program.project.id,
                run_id="",
                object_type="direction",
                object_id=direction.id,
                priority="high",
                requested_by_skill="novelty-gate",
                reason="Promising direction has unknown or missing novelty dossier; human prior-work review is needed.",
                source_ids=[program.project.id, direction.id],
            )
        if direction.maturity in {"experiment_ready", "manuscript_ready"} and direction.id not in approved_directions:
            yield _item(
                project_id=program.project.id,
                run_id="",
                object_type="direction",
                object_id=direction.id,
                priority="high",
                requested_by_skill="direction-maturation",
                reason="Direction is close to manuscript-ready and needs explicit human approval.",
                source_ids=[program.project.id, direction.id],
            )


def _claim_needs_review(claim: Claim) -> bool:
    if claim.confidence != "high":
        return False
    if claim.status in {"unsupported", "uncertain", "contested"}:
        return True
    if claim.needs_verification:
        return True
    if claim.status == "supported" and not claim.supporting_evidence:
        return True
    return False


def _promising_direction_needs_novelty_review(direction: ResearchDirection, known_dossiers: Mapping[str, object]) -> bool:
    if direction.readiness_score < 0.45 and direction.maturity not in {"candidate", "validated_gap", "experiment_ready"}:
        return False
    linked_ids = [*direction.linked_gap_ids, *direction.linked_novelty_dossier_ids]
    if not linked_ids:
        return True
    for linked_id in linked_ids:
        dossier = known_dossiers.get(linked_id)
        if dossier is not None and getattr(dossier, "verdict", "") == "unknown":
            return True
    return not any(linked_id in known_dossiers for linked_id in linked_ids)


def _approved_project_object_ids(program: ResearchProgramState, object_type: str) -> set[str]:
    approved: set[str] = set()
    for record in program.memory_records:
        text = record.text.lower()
        if record.record_type == "decision" and record.status == "active" and text.startswith(f"approve {object_type}:"):
            object_id = record.linked_object_ids[0] if record.linked_object_ids else ""
            if object_id:
                approved.add(object_id)
    return approved


def _item(
    *,
    project_id: str,
    run_id: str,
    object_type: str,
    object_id: str,
    priority: str,
    requested_by_skill: str,
    reason: str,
    source_ids: list[str],
) -> ReviewQueueItem:
    item_id = f"review-item-{_stable_id(project_id, run_id, object_type, object_id, reason)}"
    return ReviewQueueItem(
        id=item_id,
        project_id=project_id,
        run_id=run_id,
        object_type=object_type,
        object_id=object_id,
        priority=priority,
        reason=reason,
        requested_by_skill=requested_by_skill or "review-queue",
        status="open",
        created_at=utc_now_iso(),
        provenance=_queue_provenance(source_ids, "Human review queue item generated from an explicit risk trigger."),
    )


def _merge_queue_items(existing: list[ReviewQueueItem], generated: list[ReviewQueueItem]) -> list[ReviewQueueItem]:
    merged: dict[str, ReviewQueueItem] = {item.id: item for item in existing}
    for item in generated:
        previous = merged.get(item.id)
        if previous is not None:
            item.status = previous.status
            item.assigned_to = previous.assigned_to
            item.completed_at = previous.completed_at
            item.created_at = previous.created_at or item.created_at
        merged[item.id] = item
    for item in existing:
        if item.id not in {generated_item.id for generated_item in generated} and item.status in TERMINAL_STATUSES:
            merged[item.id] = item
    return sorted(merged.values(), key=_item_sort_key)


def _refresh_summary(queue: ReviewQueue) -> ReviewQueue:
    queue.summary = _summary_from_counts(Counter(item.status for item in queue.items))
    return queue


def _summary_from_counts(counts: Counter[str]) -> str:
    return f"{counts.get('open', 0)} open, {counts.get('completed', 0)} completed, {counts.get('dismissed', 0)} dismissed"


def _item_sort_key(item: ReviewQueueItem) -> tuple[int, str, str, str]:
    priority = {"high": 0, "medium": 1, "low": 2}.get(item.priority, 3)
    return (priority, item.status, item.object_type, item.object_id)


def _require_item(queue: ReviewQueue, item_id: str) -> ReviewQueueItem:
    for item in queue.items:
        if item.id == item_id:
            return item
    raise KeyError(f"Unknown review queue item: {item_id}")


def _append_queue_decision(
    program: ResearchProgramState,
    item: ReviewQueueItem,
    action: str,
    note: str,
    reviewer: str,
) -> None:
    text = f"{action} review_queue_item:{item.id}"
    if note:
        text = f"{text} | {note}"
    program.memory_records.append(
        ProjectMemoryRecord(
            id=f"memory-review-queue-{_stable_id(program.project.id, item.id, action, item.completed_at)}",
            project_id=program.project.id,
            record_type="decision",
            text=text,
            linked_run_ids=[item.run_id] if item.run_id else [],
            linked_object_ids=[item.id, item.object_id],
            status="active",
            confidence="high",
            created_at=item.completed_at,
            updated_at=item.completed_at,
            provenance=Provenance(
                created_by_skill="human-review-queue",
                source_ids=[item.id, item.object_id],
                timestamp=item.completed_at,
                reasoning_summary=f"Human {reviewer} marked review queue item {action}.",
            ),
        )
    )


def _queue_provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="review-queue",
        source_ids=[item for item in source_ids if item],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def write_review_queue_markdown(path: Path, queue: ReviewQueue | None) -> None:
    path.write_text(render_review_queue_markdown(queue), encoding="utf-8")
