"""Research idea selection gate for v0.9 pilots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.models import IdeaGateAssessment, Provenance, ResearchDirection, ResearchProgramState, to_plain
from gapforge.pilots.specs import LOW_FPR_COLLUSION
from gapforge.pilots.status import PilotStore
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

GENERIC_TERMS = {
    "framework",
    "approach",
    "method",
    "system",
    "pipeline",
    "benchmark",
    "study",
    "analysis",
    "evaluation",
}


@dataclass(slots=True)
class DirectionScore:
    direction: ResearchDirection
    blockers: list[str]
    evidence_score: int
    novelty_score: int
    tractability_score: int
    experimentability_score: int
    reviewer_risk_score: int


class IdeaGate:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def assess_pilot(self, pilot_id: str) -> IdeaGateAssessment:
        record = PilotStore(self.config).load_record(pilot_id)
        if not record.project_id:
            assessment = _refusal(record.pilot_id, [], ["Pilot has no project record; no direction can be selected."])
            self.save_assessment(record.id, assessment)
            return assessment
        assessment = self.assess_project(record.project_id, pilot_id=record.id)
        record.artifact_paths["idea_gate_assessment"] = str(self.save_assessment(record.id, assessment))
        if assessment.acceptance_status == "accepted":
            record.artifact_paths["accepted_direction_id"] = assessment.selected_direction_id
        else:
            record.blockers.extend(f"research_refusal: {blocker}" for blocker in assessment.blockers if blocker not in record.blockers)
        PilotStore(self.config).save_record(record)
        return assessment

    def assess_campaign(self, campaign_id: str) -> IdeaGateAssessment:
        campaign = CampaignManager(self.config).load_campaign_state(campaign_id).campaign
        return self.assess_project(campaign.project_id, pilot_id=campaign_id)

    def assess_project(self, project_id: str, *, pilot_id: str) -> IdeaGateAssessment:
        program = ProjectMemoryManager(self.config).load_project(project_id)
        candidate_ids = [direction.id for direction in program.research_directions]
        if not candidate_ids:
            return _refusal(pilot_id, [], ["No candidate research directions exist."])
        scored = [_score_direction(program, direction) for direction in program.research_directions]
        passing = [item for item in scored if not item.blockers]
        if not passing:
            blockers = [f"{item.direction.id}: {', '.join(item.blockers)}" for item in scored]
            return _refusal(pilot_id, candidate_ids, blockers)
        passing.sort(
            key=lambda item: (
                item.evidence_score
                + item.novelty_score
                + item.tractability_score
                + item.experimentability_score
                - item.reviewer_risk_score,
                item.direction.readiness_score,
            ),
            reverse=True,
        )
        selected = passing[0]
        rejected = [direction_id for direction_id in candidate_ids if direction_id != selected.direction.id]
        return IdeaGateAssessment(
            pilot_id=pilot_id,
            candidate_direction_ids=candidate_ids,
            selected_direction_id=selected.direction.id,
            rejected_direction_ids=rejected,
            selection_reason=(
                "Selected the only passing primary direction after evidence, novelty, experimentability, reviewer-risk, "
                "and human-review gates."
            ),
            evidence_score=selected.evidence_score,
            novelty_score=selected.novelty_score,
            tractability_score=selected.tractability_score,
            experimentability_score=selected.experimentability_score,
            reviewer_risk_score=selected.reviewer_risk_score,
            acceptance_status="accepted",
            blockers=[],
            provenance=_provenance(pilot_id, candidate_ids, "Accepted at most one primary direction."),
        )

    def save_assessment(self, pilot_id: str, assessment: IdeaGateAssessment) -> Path:
        path = self.config.data_dir / "pilots" / pilot_id / "idea_gate_assessment.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")
        md_path = path.with_suffix(".md")
        md_path.write_text(render_idea_gate(assessment), encoding="utf-8")
        return path

    def load_assessment(self, pilot_id: str) -> IdeaGateAssessment:
        path = self.config.data_dir / "pilots" / pilot_id / "idea_gate_assessment.json"
        if not path.exists():
            raise FileNotFoundError(f"No idea gate assessment found for {pilot_id}")
        from gapforge.models import from_dict

        return from_dict(IdeaGateAssessment, json.loads(path.read_text(encoding="utf-8")))


def render_idea_gate(assessment: IdeaGateAssessment, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(to_plain(assessment), indent=2) + "\n"
    lines = [
        f"# Idea Gate: {assessment.pilot_id}",
        "",
        f"- Status: `{assessment.acceptance_status}`",
        f"- Selected direction: `{assessment.selected_direction_id or 'none'}`",
        f"- Candidate directions: {', '.join(assessment.candidate_direction_ids) or 'none'}",
        f"- Rejected directions: {', '.join(assessment.rejected_direction_ids) or 'none'}",
        f"- Evidence score: {assessment.evidence_score}",
        f"- Novelty score: {assessment.novelty_score}",
        f"- Tractability score: {assessment.tractability_score}",
        f"- Experimentability score: {assessment.experimentability_score}",
        f"- Reviewer risk score: {assessment.reviewer_risk_score}",
        "",
        "## Selection Reason",
        "",
        assessment.selection_reason or "No direction selected.",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {blocker}" for blocker in assessment.blockers] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _score_direction(program: ResearchProgramState, direction: ResearchDirection) -> DirectionScore:
    blockers: list[str] = []
    if _is_generic(direction):
        blockers.append("generic idea")
    if not direction.linked_gap_ids or not direction.supporting_paper_ids:
        blockers.append("missing evidence-backed gap")
    if not direction.linked_novelty_dossier_ids:
        blockers.append("missing novelty dossier")
    matrix = next((item for item in program.related_work_matrices if item.direction_id == direction.id), None)
    if matrix is None:
        blockers.append("missing related-work matrix")
    elif not matrix.must_read_paper_ids and not matrix.entries:
        blockers.append("missing closest prior work")
    protocol = next((item for item in program.experiment_protocols if item.direction_id == direction.id), None)
    if protocol is None:
        blockers.append("missing measurable experiment")
    elif not protocol.metrics or not (protocol.datasets or protocol.evaluation_script_outline):
        blockers.append("experiment is not measurable")
    panel = next((item for item in program.review_panels if item.experiment_or_direction_id == direction.id), None)
    if panel is None:
        blockers.append("missing reviewer panel")
    if not _has_human_acceptance(program, direction.id):
        blockers.append("missing human review acceptance")
    if _has_fake_issue(direction):
        blockers.append("unresolved fake citation/result issue")

    evidence_score = min(5, len(direction.supporting_paper_ids) + len(direction.linked_gap_ids))
    novelty_score = 5 if direction.linked_novelty_dossier_ids else 0
    tractability_score = 5 if protocol and not direction.blocking_issues else 1
    experimentability_score = 5 if protocol and protocol.metrics and (protocol.datasets or protocol.evaluation_script_outline) else 0
    reviewer_risk_score = len(panel.required_changes) if panel else 5
    return DirectionScore(
        direction=direction,
        blockers=blockers,
        evidence_score=evidence_score,
        novelty_score=novelty_score,
        tractability_score=tractability_score,
        experimentability_score=experimentability_score,
        reviewer_risk_score=reviewer_risk_score,
    )


def _refusal(pilot_id: str, candidate_ids: list[str], blockers: list[str]) -> IdeaGateAssessment:
    return IdeaGateAssessment(
        pilot_id=pilot_id,
        candidate_direction_ids=candidate_ids,
        selected_direction_id="",
        rejected_direction_ids=candidate_ids,
        selection_reason="No candidate direction passed the idea gate; the pilot should record a correct refusal.",
        acceptance_status="refusal",
        blockers=blockers,
        provenance=_provenance(pilot_id, candidate_ids, "Rejected all candidate directions and preserved refusal blockers."),
    )


def _is_generic(direction: ResearchDirection) -> bool:
    text = f"{direction.title} {direction.summary}".strip().lower()
    words = {word.strip(".,:;()[]") for word in text.split()}
    if len(words) <= 5 and words & GENERIC_TERMS:
        return True
    generic_phrases = ["better framework", "novel approach", "improve detection", "use llms to detect", "general method"]
    return any(phrase in text for phrase in generic_phrases)


def _has_human_acceptance(program: ResearchProgramState, direction_id: str) -> bool:
    return any(
        direction_id in record.linked_object_ids and record.status in {"accepted", "active"} and "accept" in record.text.lower()
        for record in program.memory_records
    )


def _has_fake_issue(direction: ResearchDirection) -> bool:
    text = " ".join([*direction.blocking_issues, *direction.next_actions]).lower()
    return "fake citation" in text or "fake result" in text


def _provenance(pilot_id: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="idea-gate",
        source_ids=[pilot_id, *source_ids],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )


def latest_low_fpr_pilot_id() -> str:
    return LOW_FPR_COLLUSION
