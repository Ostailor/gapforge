"""Auditable human feedback for v2 idea discovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaFeedbackRecord, IdeaSearchDecision, validate_idea_feedback_action, validate_mutation_strategy
from gapforge.ideas.store import IdeaStore
from gapforge.models import ProjectMemoryRecord, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_compact, utc_now_iso


class IdeaFeedbackManager:
    """Record human feedback and translate it into auditable search state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)

    def add_feedback(
        self,
        *,
        idea_id: str,
        action: str,
        reviewer: str = "human",
        rationale: str = "",
        preferred_mutations: list[str] | None = None,
        notes: str = "",
    ) -> IdeaFeedbackRecord:
        _, candidate = self.store.load_by_idea_id(idea_id)
        action = validate_idea_feedback_action(action)
        mutations = _dedupe(preferred_mutations or [])
        for mutation in mutations:
            validate_mutation_strategy(mutation)
        feedback = IdeaFeedbackRecord(
            id=_feedback_id(idea_id, action, reviewer),
            idea_id=idea_id,
            reviewer=reviewer,
            action=action,
            rationale=rationale,
            preferred_mutations=mutations,
            notes=notes,
            provenance=Provenance(
                created_by_skill="idea-feedback",
                source_ids=[idea_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Recorded auditable human feedback for idea discovery.",
            ),
        )
        self.store.add_feedback_record(feedback)
        if action == "reject":
            self.store.reject_candidate(idea_id, rationale or notes or "Human feedback rejected the idea.")
            self._persist_rejection_memory(candidate.project_id, feedback)
        elif action == "request_mutation":
            self._record_mutation_decision(candidate.project_id, feedback)
        elif action == "request_search":
            self._record_search_decision(candidate.project_id, feedback)
        elif action == "accept":
            self.store.add_review(
                idea_id=idea_id,
                reviewer=reviewer,
                status="accepted",
                novelty_judgment="Human preference accepts the idea, subject to evidence and novelty gates.",
                feasibility_judgment="Accepted by preference; feasibility remains evidence-gated.",
                impact_judgment="Accepted by preference; impact remains tournament-scored.",
                required_fixes=["Acceptance does not waive evidence, novelty, or human-review gates."],
                notes=rationale or notes,
            )
        self.write_report(candidate.project_id)
        return feedback

    def render_report(self, project_id: str) -> str:
        state = self.store.load_state(project_id)
        lines = [
            "# Idea Feedback Report",
            "",
            "Human feedback shapes search and tournament scoring. It is auditable and cannot override evidence gates.",
            "",
        ]
        if not state.feedback_records:
            lines.append("- none")
            return "\n".join(lines).rstrip() + "\n"
        for feedback in state.feedback_records:
            lines.extend(
                [
                    f"## `{feedback.id}`",
                    "",
                    f"- Idea ID: `{feedback.idea_id}`",
                    f"- Reviewer: {feedback.reviewer}",
                    f"- Action: `{feedback.action}`",
                    f"- Rationale: {feedback.rationale or 'none'}",
                    f"- Preferred mutations: {', '.join(feedback.preferred_mutations) or 'none'}",
                    f"- Notes: {feedback.notes or 'none'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        program = self.project_manager.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_feedback.md").write_text(report, encoding="utf-8")
        return report

    def _persist_rejection_memory(self, project_id: str, feedback: IdeaFeedbackRecord) -> None:
        program = self.project_manager.load_project(project_id)
        record = ProjectMemoryRecord(
            id=f"idea-feedback-rejection-{feedback.idea_id}",
            project_id=project_id,
            record_type="rejected_idea",
            text=f"Human rejected idea `{feedback.idea_id}`: {feedback.rationale or feedback.notes}",
            linked_object_ids=[feedback.idea_id, feedback.id],
            status="rejected",
            confidence="high",
            updated_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="idea-feedback",
                source_ids=[feedback.idea_id, feedback.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Persisted human idea rejection into project memory.",
            ),
        )
        program.memory_records = [item for item in program.memory_records if item.id != record.id]
        program.memory_records.append(record)
        self.project_manager.save_project(program)

    def _record_mutation_decision(self, project_id: str, feedback: IdeaFeedbackRecord) -> None:
        strategy = feedback.preferred_mutations[0] if feedback.preferred_mutations else "reviewer_objection_to_new_idea"
        self.store.add_search_decision(
            IdeaSearchDecision(
                id=_decision_id(project_id, feedback.id, "mutate_ideas"),
                project_id=project_id,
                iteration=len(self.store.load_state(project_id).search_decisions) + 1,
                decision_type="mutate_ideas",
                reason=f"Human feedback requested mutation for `{feedback.idea_id}`.",
                expected_value=f"Try `{strategy}` mutation while preserving prior evidence risks.",
                evidence=[feedback.id, feedback.idea_id, strategy],
                status="pending",
                provenance=Provenance(
                    created_by_skill="idea-feedback",
                    source_ids=[feedback.id, feedback.idea_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Human mutation request became an auditable idea-search decision.",
                ),
            )
        )

    def _record_search_decision(self, project_id: str, feedback: IdeaFeedbackRecord) -> None:
        self.store.add_search_decision(
            IdeaSearchDecision(
                id=_decision_id(project_id, feedback.id, "search_variant"),
                project_id=project_id,
                iteration=len(self.store.load_state(project_id).search_decisions) + 1,
                decision_type="search_variant",
                reason=f"Human feedback requested more search for `{feedback.idea_id}`.",
                expected_value="Collect additional prior-work and counterevidence before selection.",
                evidence=[feedback.id, feedback.idea_id],
                status="pending",
                provenance=Provenance(
                    created_by_skill="idea-feedback",
                    source_ids=[feedback.id, feedback.idea_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Human search request became an auditable idea-search decision.",
                ),
            )
        )


def _feedback_id(idea_id: str, action: str, reviewer: str) -> str:
    digest = hashlib.sha1(f"{idea_id}::{action}::{reviewer}::{utc_now_compact()}".encode()).hexdigest()[:10]
    return f"idea-feedback-{digest}"


def _decision_id(project_id: str, feedback_id: str, decision_type: str) -> str:
    digest = hashlib.sha1(f"{project_id}::{feedback_id}::{decision_type}".encode()).hexdigest()[:10]
    return f"idea-feedback-decision-{digest}"


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result
