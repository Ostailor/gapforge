"""Project-scoped storage for first-class v2 idea discovery objects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import (
    ConstructiveGapCandidate,
    IdeaBank,
    IdeaCandidate,
    IdeaEvidenceLink,
    IdeaFeedbackRecord,
    IdeaMutationRecord,
    IdeaNoveltyAssessment,
    IdeaPreferenceProfile,
    IdeaReviewRecord,
    IdeaSearchDecision,
    IdeaTournament,
    IdeaTransferCandidate,
    ResearchAgenda,
    validate_agenda_step_type,
    validate_contribution_type,
    validate_idea_feedback_action,
    validate_idea_novelty_verdict,
    validate_idea_search_decision_type,
    validate_link_type,
    validate_maturity,
    validate_mutation_strategy,
    validate_novelty_status,
    validate_review_status,
)
from gapforge.ideas.reports import render_idea_bank_markdown, render_idea_report_markdown
from gapforge.ideas.state import IdeaDiscoveryState
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso


class IdeaStore:
    """Create, persist, and report first-class idea discovery state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)

    def create_bank(self, *, project_id: str, root_topic: str) -> IdeaBank:
        ideas_dir = self._ideas_dir(project_id)
        now = utc_now_iso()
        existing = self.load_state(project_id).idea_bank
        bank = IdeaBank(
            id=existing.id if existing is not None else _stable_id("idea-bank", project_id, root_topic),
            project_id=project_id,
            root_topic=root_topic,
            candidate_ids=existing.candidate_ids if existing is not None else [],
            rejected_candidate_ids=existing.rejected_candidate_ids if existing is not None else [],
            selected_candidate_id=existing.selected_candidate_id if existing is not None else "",
            agenda_id=existing.agenda_id if existing is not None else "",
            created_at=existing.created_at if existing is not None else now,
            updated_at=now,
            provenance=Provenance(
                created_by_skill="idea-bank",
                source_ids=[project_id],
                timestamp=now,
                reasoning_summary=(
                    "Created first-class idea bank state. Idea candidates are auditable search objects, not paper-readiness claims."
                ),
            ),
        )
        self._write_json(ideas_dir / "idea_bank.json", bank)
        self._write_if_missing(ideas_dir / "candidates.json", [])
        self._write_if_missing(ideas_dir / "preference_profiles.json", [])
        self._write_if_missing(ideas_dir / "evidence_links.json", [])
        self._write_if_missing(ideas_dir / "feedback_records.json", [])
        self._write_if_missing(ideas_dir / "novelty_assessments.json", [])
        self._write_if_missing(ideas_dir / "reviews.json", [])
        self._write_if_missing(ideas_dir / "mutations.json", [])
        self._write_if_missing(ideas_dir / "constructive_gaps.json", [])
        self._write_if_missing(ideas_dir / "transfer_candidates.json", [])
        self._write_if_missing(ideas_dir / "search_decisions.json", [])
        self._write_if_missing(ideas_dir / "tournaments.json", [])
        self._write_if_missing(ideas_dir / "research_agendas.json", [])
        self._write_reports(project_id)
        # Keep the project report aware that a v2 idea workspace exists without embedding idea state in project memory.
        self.project_manager.write_project_report(self.project_manager.load_project(project_id))
        return bank

    def load_state(self, project_id: str) -> IdeaDiscoveryState:
        ideas_dir = self._ideas_dir(project_id)
        bank_path = ideas_dir / "idea_bank.json"
        bank = from_dict(IdeaBank, json.loads(bank_path.read_text(encoding="utf-8"))) if bank_path.exists() else None
        return IdeaDiscoveryState(
            idea_bank=bank,
            candidates=_load_list(ideas_dir / "candidates.json", IdeaCandidate),
            preference_profiles=_load_list(ideas_dir / "preference_profiles.json", IdeaPreferenceProfile),
            evidence_links=_load_list(ideas_dir / "evidence_links.json", IdeaEvidenceLink),
            feedback_records=_load_list(ideas_dir / "feedback_records.json", IdeaFeedbackRecord),
            novelty_assessments=_load_list(ideas_dir / "novelty_assessments.json", IdeaNoveltyAssessment),
            reviews=_load_list(ideas_dir / "reviews.json", IdeaReviewRecord),
            mutations=_load_list(ideas_dir / "mutations.json", IdeaMutationRecord),
            constructive_gaps=_load_list(ideas_dir / "constructive_gaps.json", ConstructiveGapCandidate),
            transfer_candidates=_load_list(ideas_dir / "transfer_candidates.json", IdeaTransferCandidate),
            search_decisions=_load_list(ideas_dir / "search_decisions.json", IdeaSearchDecision),
            tournaments=_load_list(ideas_dir / "tournaments.json", IdeaTournament),
            agendas=_load_list(ideas_dir / "research_agendas.json", ResearchAgenda),
        )

    def load_by_idea_id(self, idea_id: str) -> tuple[IdeaDiscoveryState, IdeaCandidate]:
        projects = self.project_manager.list_projects()
        active_project_id = self.project_manager.active_project_id()
        if active_project_id:
            projects = sorted(projects, key=lambda project: project.id != active_project_id)
        for project in projects:
            state = self.load_state(project.id)
            candidate = next((item for item in state.candidates if item.id == idea_id), None)
            if candidate is not None:
                return state, candidate
        raise FileNotFoundError(f"No idea candidate found for {idea_id}")

    def list_candidates(self, project_id: str) -> list[IdeaCandidate]:
        return self.load_state(project_id).candidates

    def add_candidate(
        self,
        *,
        project_id: str,
        source_topic_id: str,
        title: str,
        summary: str,
        contribution_type: str = "hybrid",
        core_claim: str = "",
        proposed_experiment: str = "",
        expected_baselines: list[str] | None = None,
        expected_metrics: list[str] | None = None,
        closest_prior_work_ids: list[str] | None = None,
        evidence_span_ids: list[str] | None = None,
        supporting_paper_ids: list[str] | None = None,
        counterevidence_paper_ids: list[str] | None = None,
        novelty_status: str = "unchecked",
        tractability_score: float = 0.0,
        impact_score: float = 0.0,
        evidence_score: float = 0.0,
        reviewer_risk_score: float = 0.0,
        idea_yield_score: float = 0.0,
        maturity: str = "candidate",
        likely_failure_mode: str = "",
        provenance: Provenance | None = None,
    ) -> IdeaCandidate:
        state = self._require_bank(project_id)
        now = utc_now_iso()
        candidate = IdeaCandidate(
            id=_unique_candidate_id(state.candidates, title),
            project_id=project_id,
            source_topic_id=source_topic_id,
            title=title,
            summary=summary,
            contribution_type=validate_contribution_type(contribution_type),
            core_claim=core_claim,
            proposed_experiment=proposed_experiment,
            expected_baselines=_unique(expected_baselines or []),
            expected_metrics=_unique(expected_metrics or []),
            closest_prior_work_ids=_unique(closest_prior_work_ids or []),
            evidence_span_ids=_unique(evidence_span_ids or []),
            supporting_paper_ids=_unique(supporting_paper_ids or []),
            counterevidence_paper_ids=_unique(counterevidence_paper_ids or []),
            novelty_status=validate_novelty_status(novelty_status),
            tractability_score=tractability_score,
            impact_score=impact_score,
            evidence_score=evidence_score,
            reviewer_risk_score=reviewer_risk_score,
            idea_yield_score=idea_yield_score,
            maturity=validate_maturity(maturity),
            likely_failure_mode=likely_failure_mode,
            provenance=provenance
            or Provenance(
                created_by_skill="idea-candidate",
                source_ids=[project_id, source_topic_id],
                timestamp=now,
                reasoning_summary="Added an auditable idea candidate. Candidate maturity is separate from paper readiness.",
            ),
        )
        state.candidates.append(candidate)
        assert state.idea_bank is not None
        state.idea_bank.candidate_ids = _unique([*state.idea_bank.candidate_ids, candidate.id])
        state.idea_bank.updated_at = now
        self._save_state(project_id, state)
        return candidate

    def reject_candidate(self, idea_id: str, reason: str) -> IdeaCandidate:
        state, candidate = self.load_by_idea_id(idea_id)
        candidate.maturity = "rejected"
        candidate.rejection_reason = reason
        if state.idea_bank is not None:
            state.idea_bank.rejected_candidate_ids = _unique([*state.idea_bank.rejected_candidate_ids, candidate.id])
            state.idea_bank.candidate_ids = _unique(state.idea_bank.candidate_ids)
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(candidate.project_id, state)
        return candidate

    def link_evidence(
        self,
        *,
        idea_id: str,
        link_type: str,
        paper_id: str = "",
        evidence_span_id: str = "",
        claim_id: str = "",
        note: str = "",
        confidence: str = "medium",
    ) -> IdeaEvidenceLink:
        state, candidate = self.load_by_idea_id(idea_id)
        now = utc_now_iso()
        link = IdeaEvidenceLink(
            id=_unique_link_id(state.evidence_links, idea_id, link_type, paper_id or evidence_span_id or claim_id or note),
            idea_id=idea_id,
            link_type=validate_link_type(link_type),
            paper_id=paper_id,
            evidence_span_id=evidence_span_id,
            claim_id=claim_id,
            note=note,
            confidence=confidence,
            provenance=Provenance(
                created_by_skill="idea-evidence-link",
                source_ids=[idea_id, paper_id, evidence_span_id, claim_id],
                timestamp=now,
                reasoning_summary="Linked idea candidate to supporting, countering, contextual, or missing evidence.",
            ),
        )
        state.evidence_links.append(link)
        if paper_id and link.link_type == "supports":
            candidate.supporting_paper_ids = _unique([*candidate.supporting_paper_ids, paper_id])
        if paper_id and link.link_type == "counters":
            candidate.counterevidence_paper_ids = _unique([*candidate.counterevidence_paper_ids, paper_id])
        if paper_id and link.link_type == "closest_prior_work":
            candidate.closest_prior_work_ids = _unique([*candidate.closest_prior_work_ids, paper_id])
        if evidence_span_id:
            candidate.evidence_span_ids = _unique([*candidate.evidence_span_ids, evidence_span_id])
        self._save_state(candidate.project_id, state)
        return link

    def add_review(
        self,
        *,
        idea_id: str,
        reviewer: str,
        status: str = "uncertain",
        novelty_judgment: str = "",
        feasibility_judgment: str = "",
        impact_judgment: str = "",
        required_fixes: list[str] | None = None,
        notes: str = "",
    ) -> IdeaReviewRecord:
        state, candidate = self.load_by_idea_id(idea_id)
        now = utc_now_iso()
        review = IdeaReviewRecord(
            id=_unique_review_id(state.reviews, idea_id, reviewer),
            idea_id=idea_id,
            reviewer=reviewer,
            status=validate_review_status(status),
            novelty_judgment=novelty_judgment,
            feasibility_judgment=feasibility_judgment,
            impact_judgment=impact_judgment,
            required_fixes=required_fixes or [],
            notes=notes,
            provenance=Provenance(
                created_by_skill="idea-human-review",
                source_ids=[idea_id],
                timestamp=now,
                reasoning_summary="Recorded human review for an idea candidate. Review can steer search but cannot waive evidence gates.",
            ),
        )
        state.reviews.append(review)
        candidate.human_feedback_ids = _unique([*candidate.human_feedback_ids, review.id])
        if review.status == "rejected" and candidate.maturity != "rejected":
            candidate.maturity = "rejected"
            candidate.rejection_reason = notes or "Human review rejected the idea candidate."
            if state.idea_bank is not None:
                state.idea_bank.rejected_candidate_ids = _unique([*state.idea_bank.rejected_candidate_ids, candidate.id])
        if state.idea_bank is not None:
            state.idea_bank.updated_at = now
        self._save_state(candidate.project_id, state)
        return review

    def add_mutation_record(
        self,
        *,
        source_idea_id: str,
        mutated_idea_id: str,
        strategy: str,
        what_changed: str,
        why_it_may_help: str,
        inherited_risks: list[str] | None = None,
        required_new_searches: list[str] | None = None,
        provenance: Provenance | None = None,
    ) -> IdeaMutationRecord:
        state, source = self.load_by_idea_id(source_idea_id)
        if not any(candidate.id == mutated_idea_id for candidate in state.candidates):
            raise FileNotFoundError(f"No mutated idea candidate found for {mutated_idea_id}")
        now = utc_now_iso()
        record = IdeaMutationRecord(
            id=_unique_mutation_id(state.mutations, source_idea_id, mutated_idea_id, strategy),
            source_idea_id=source_idea_id,
            mutated_idea_id=mutated_idea_id,
            strategy=validate_mutation_strategy(strategy),
            what_changed=what_changed,
            why_it_may_help=why_it_may_help,
            inherited_risks=_unique(inherited_risks or []),
            required_new_searches=_unique(required_new_searches or []),
            provenance=provenance
            or Provenance(
                created_by_skill="idea-mutation",
                source_ids=[source_idea_id, mutated_idea_id],
                timestamp=now,
                reasoning_summary=(
                    "Recorded an auditable idea mutation. Mutation reframes search state and does not erase novelty or evidence risks."
                ),
            ),
        )
        state.mutations.append(record)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = now
        self._save_state(source.project_id, state)
        return record

    def add_search_decision(self, decision: IdeaSearchDecision) -> IdeaSearchDecision:
        state = self.load_state(decision.project_id)
        decision.decision_type = validate_idea_search_decision_type(decision.decision_type)
        state.search_decisions.append(decision)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(decision.project_id, state)
        return decision

    def add_novelty_assessment(self, assessment: IdeaNoveltyAssessment) -> IdeaNoveltyAssessment:
        state, candidate = self.load_by_idea_id(assessment.idea_id)
        assessment.verdict = validate_idea_novelty_verdict(assessment.verdict)
        state.novelty_assessments.append(assessment)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(candidate.project_id, state)
        return assessment

    def add_preference_profile(self, profile: IdeaPreferenceProfile) -> IdeaPreferenceProfile:
        state = self.load_state(profile.project_id)
        state.preference_profiles = [item for item in state.preference_profiles if item.id != profile.id]
        state.preference_profiles.append(profile)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(profile.project_id, state)
        return profile

    def add_feedback_record(self, feedback: IdeaFeedbackRecord) -> IdeaFeedbackRecord:
        state, candidate = self.load_by_idea_id(feedback.idea_id)
        feedback.action = validate_idea_feedback_action(feedback.action)
        state.feedback_records.append(feedback)
        candidate.human_feedback_ids = _unique([*candidate.human_feedback_ids, feedback.id])
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(candidate.project_id, state)
        return feedback

    def add_tournament(self, tournament: IdeaTournament) -> IdeaTournament:
        state = self.load_state(tournament.project_id)
        state.tournaments.append(tournament)
        if state.idea_bank is not None:
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(tournament.project_id, state)
        return tournament

    def add_research_agenda(self, agenda: ResearchAgenda) -> ResearchAgenda:
        state = self.load_state(agenda.project_id)
        for step in agenda.agenda_steps:
            step.step_type = validate_agenda_step_type(step.step_type)
        state.agendas = [item for item in state.agendas if item.id != agenda.id]
        state.agendas.append(agenda)
        if state.idea_bank is not None:
            state.idea_bank.agenda_id = agenda.id
            state.idea_bank.updated_at = utc_now_iso()
        self._save_state(agenda.project_id, state)
        return agenda

    def render_bank(self, project_id: str) -> str:
        return render_idea_bank_markdown(self.load_state(project_id))

    def write_bank_report(self, project_id: str) -> str:
        state = self.load_state(project_id)
        report = render_idea_bank_markdown(state)
        reports_dir = self._ideas_dir(project_id) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_bank.md").write_text(report, encoding="utf-8")
        return report

    def render_idea_report(self, idea_id: str) -> str:
        state, candidate = self.load_by_idea_id(idea_id)
        return render_idea_report_markdown(
            candidate,
            bank=state.idea_bank,
            evidence_links=[item for item in state.evidence_links if item.idea_id == idea_id],
            novelty_assessments=[item for item in state.novelty_assessments if item.idea_id == idea_id],
            reviews=[item for item in state.reviews if item.idea_id == idea_id],
        )

    def write_idea_report(self, idea_id: str) -> str:
        state, candidate = self.load_by_idea_id(idea_id)
        report = self.render_idea_report(idea_id)
        reports_dir = self._ideas_dir(candidate.project_id) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{candidate.id}.md").write_text(report, encoding="utf-8")
        (reports_dir / f"{candidate.id}.json").write_text(
            json.dumps(
                {
                    "candidate": to_plain(candidate),
                    "evidence_links": to_plain([item for item in state.evidence_links if item.idea_id == idea_id]),
                    "novelty_assessments": to_plain([item for item in state.novelty_assessments if item.idea_id == idea_id]),
                    "reviews": to_plain([item for item in state.reviews if item.idea_id == idea_id]),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return report

    def _require_bank(self, project_id: str) -> IdeaDiscoveryState:
        state = self.load_state(project_id)
        if state.idea_bank is None:
            raise FileNotFoundError(f"No idea bank found for project {project_id}. Run idea-bank-create first.")
        return state

    def _save_state(self, project_id: str, state: IdeaDiscoveryState) -> None:
        ideas_dir = self._ideas_dir(project_id)
        if state.idea_bank is not None:
            self._write_json(ideas_dir / "idea_bank.json", state.idea_bank)
        self._write_json(ideas_dir / "candidates.json", state.candidates)
        self._write_json(ideas_dir / "preference_profiles.json", state.preference_profiles)
        self._write_json(ideas_dir / "evidence_links.json", state.evidence_links)
        self._write_json(ideas_dir / "feedback_records.json", state.feedback_records)
        self._write_json(ideas_dir / "novelty_assessments.json", state.novelty_assessments)
        self._write_json(ideas_dir / "reviews.json", state.reviews)
        self._write_json(ideas_dir / "mutations.json", state.mutations)
        self._write_json(ideas_dir / "constructive_gaps.json", state.constructive_gaps)
        self._write_json(ideas_dir / "transfer_candidates.json", state.transfer_candidates)
        self._write_json(ideas_dir / "search_decisions.json", state.search_decisions)
        self._write_json(ideas_dir / "tournaments.json", state.tournaments)
        self._write_json(ideas_dir / "research_agendas.json", state.agendas)
        self._write_reports(project_id)

    def _write_reports(self, project_id: str) -> None:
        state = self.load_state(project_id)
        reports_dir = self._ideas_dir(project_id) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_bank.md").write_text(render_idea_bank_markdown(state), encoding="utf-8")
        for candidate in state.candidates:
            report = render_idea_report_markdown(
                candidate,
                bank=state.idea_bank,
                evidence_links=[item for item in state.evidence_links if item.idea_id == candidate.id],
                novelty_assessments=[item for item in state.novelty_assessments if item.idea_id == candidate.id],
                reviews=[item for item in state.reviews if item.idea_id == candidate.id],
            )
            (reports_dir / f"{candidate.id}.md").write_text(report, encoding="utf-8")

    def _project_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        return Path(program.project.root_dir)

    def _ideas_dir(self, project_id: str) -> Path:
        ideas_dir = self._project_dir(project_id) / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        (ideas_dir / "reports").mkdir(parents=True, exist_ok=True)
        return ideas_dir

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")

    def _write_if_missing(self, path: Path, value: object) -> None:
        if not path.exists():
            self._write_json(path, value)


T = TypeVar("T")


def _load_list(path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(model, item) for item in raw]


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]
    readable = slugify(parts[-1])[:48] or "untitled"
    return f"{prefix}-{readable}-{digest}"


def _unique_candidate_id(candidates: list[IdeaCandidate], title: str) -> str:
    existing = {item.id for item in candidates}
    base = f"idea-{slugify(title)}"
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique_link_id(links: list[IdeaEvidenceLink], idea_id: str, link_type: str, target: str) -> str:
    existing = {item.id for item in links}
    base = _stable_id("idea-link", idea_id, link_type, target or "missing")
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique_review_id(reviews: list[IdeaReviewRecord], idea_id: str, reviewer: str) -> str:
    existing = {item.id for item in reviews}
    base = _stable_id("idea-review", idea_id, reviewer or "human")
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique_mutation_id(mutations: list[IdeaMutationRecord], source_idea_id: str, mutated_idea_id: str, strategy: str) -> str:
    existing = {item.id for item in mutations}
    base = _stable_id("idea-mutation", source_idea_id, mutated_idea_id, strategy)
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
