"""Transparent tournament scoring for v2 idea selection."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.agenda import ResearchAgendaManager, tournament_blocker_summary
from gapforge.ideas.generator import is_generic_idea_title
from gapforge.ideas.models import IdeaCandidate, IdeaScoreRecord, IdeaTournament, ResearchAgenda
from gapforge.ideas.store import IdeaStore
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso

RESULT_CLAIM_MARKERS = (
    "we found",
    "we show",
    "results show",
    "outperforms",
    "outperformed",
    "achieves",
    "achieved",
    "improves by",
    "significant improvement",
)
FATAL_NOVELTY_MARKERS = (
    "fatal prior work",
    "already done",
    "already solves",
    "duplicate",
    "not novel",
    "subsumes",
)


class IdeaTournamentRunner:
    """Score candidates and select the strongest viable idea or an agenda fallback."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.agendas = ResearchAgendaManager(config)

    def run(self, project_id: str, *, top_k: int = 5) -> IdeaTournament:
        state = self.store.load_state(project_id)
        candidate_ids = _candidate_ids(state.candidates, top_k=top_k)
        known_paper_ids = self._known_paper_ids(project_id)
        score_records = [
            self._score_candidate(candidate, state, known_paper_ids) for candidate in state.candidates if candidate.id in set(candidate_ids)
        ]
        viable = [record for record in score_records if not record.blockers]
        if viable:
            selected = max(viable, key=lambda record: (record.total_score, record.idea_id))
            selected_id = selected.idea_id
            agenda_id = ""
            selection_reason = _selection_reason(selected)
        else:
            selected_id = ""
            agenda = self._create_agenda(project_id, score_records)
            agenda_id = agenda.id
            selection_reason = "No viable idea passed tournament blockers; created research agenda fallback."
        rejected_ids = [record.idea_id for record in score_records if record.blockers]
        tournament = IdeaTournament(
            id=_tournament_id(project_id, candidate_ids, selected_id or agenda_id),
            project_id=project_id,
            candidate_ids=candidate_ids,
            score_records=score_records,
            selected_candidate_id=selected_id,
            rejected_candidate_ids=rejected_ids,
            agenda_id=agenda_id,
            selection_reason=selection_reason,
            provenance=Provenance(
                created_by_skill="idea-tournament",
                source_ids=[project_id, *candidate_ids, selected_id, agenda_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Scored v2 idea candidates and selected one viable candidate or an agenda fallback.",
            ),
        )
        self._apply_tournament(tournament)
        self.write_report(project_id)
        return tournament

    def selected_idea(self, project_id: str) -> IdeaCandidate | None:
        state = self.store.load_state(project_id)
        selected_id = state.idea_bank.selected_candidate_id if state.idea_bank else ""
        if not selected_id and state.tournaments:
            selected_id = state.tournaments[-1].selected_candidate_id
        return next((candidate for candidate in state.candidates if candidate.id == selected_id), None)

    def render_report(self, project_id: str) -> str:
        state = self.store.load_state(project_id)
        latest = state.tournaments[-1] if state.tournaments else None
        lines = [
            "# Idea Tournament Report",
            "",
            "Tournament selection is transparent and blocker-gated. Disqualified ideas cannot win regardless of score.",
            "",
        ]
        if latest is None:
            lines.append("- none")
            return "\n".join(lines).rstrip() + "\n"
        lines.extend(
            [
                f"- Tournament ID: `{latest.id}`",
                f"- Selected candidate: `{latest.selected_candidate_id or 'none'}`",
                f"- Agenda ID: `{latest.agenda_id or 'none'}`",
                f"- Rejected candidates: {', '.join(latest.rejected_candidate_ids) or 'none'}",
                f"- Selection reason: {latest.selection_reason}",
                "",
                "## Scores",
                "",
            ]
        )
        for record in sorted(latest.score_records, key=lambda item: item.total_score, reverse=True):
            lines.extend(
                [
                    f"### `{record.idea_id}`",
                    "",
                    f"- Total: {record.total_score:.3f}",
                    f"- Evidence: {record.evidence_score:.2f}",
                    f"- Novelty: {record.novelty_score:.2f}",
                    f"- Experimentability: {record.experimentability_score:.2f}",
                    f"- Tractability: {record.tractability_score:.2f}",
                    f"- Impact: {record.impact_score:.2f}",
                    f"- Reviewer-risk score: {record.reviewer_risk_score:.2f}",
                    f"- Time-to-demo: {record.time_to_demo_score:.2f}",
                    f"- Benchmark availability: {record.benchmark_score:.2f}",
                    f"- Baseline availability: {record.baseline_score:.2f}",
                    f"- Cross-domain leverage: {record.cross_domain_score:.2f}",
                    f"- Human preference: {record.human_preference_score:.2f}",
                    f"- Blockers: {'; '.join(record.blockers) or 'none'}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        program = self.project_manager.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_tournament.md").write_text(report, encoding="utf-8")
        return report

    def _score_candidate(self, candidate: IdeaCandidate, state, known_paper_ids: set[str]) -> IdeaScoreRecord:
        blockers = _blockers(candidate, state, known_paper_ids)
        novelty_score = _novelty_score(candidate, state)
        reviewer_score = _clamp(1.0 - candidate.reviewer_risk_score)
        record = IdeaScoreRecord(
            idea_id=candidate.id,
            evidence_score=_evidence_score(candidate, state),
            novelty_score=novelty_score,
            experimentability_score=_experimentability_score(candidate),
            tractability_score=_clamp(candidate.tractability_score),
            impact_score=_clamp(candidate.impact_score),
            reviewer_risk_score=reviewer_score,
            time_to_demo_score=_time_to_demo_score(candidate),
            benchmark_score=_benchmark_score(candidate),
            baseline_score=_baseline_score(candidate),
            cross_domain_score=_cross_domain_score(candidate, state),
            human_preference_score=_human_preference_score(candidate, state),
            blockers=blockers,
            provenance=Provenance(
                created_by_skill="idea-tournament",
                source_ids=[candidate.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Scored idea candidate across v2 tournament dimensions.",
            ),
        )
        record.total_score = 0.0 if blockers else _total_score(record)
        return record

    def _known_paper_ids(self, project_id: str) -> set[str]:
        program = self.project_manager.sync_project_memory(project_id)
        known = {record.paper_id for record in program.corpus_papers}
        for record in program.corpus_papers:
            known.update(record.source_paper_ids)
        for run_id in program.run_ids:
            try:
                run = self.state_manager.load_run(run_id)
            except FileNotFoundError:
                continue
            known.update(paper.id for paper in run.papers)
        state = self.store.load_state(project_id)
        known.update(link.paper_id for link in state.evidence_links if link.paper_id)
        return {paper_id for paper_id in known if paper_id}

    def _create_agenda(self, project_id: str, score_records: list[IdeaScoreRecord]) -> ResearchAgenda:
        return self.agendas.generate(
            project_id,
            blocker_summary=tournament_blocker_summary(score_records),
            source_ids=[record.idea_id for record in score_records],
        )

    def _apply_tournament(self, tournament: IdeaTournament) -> None:
        state = self.store.load_state(tournament.project_id)
        if state.idea_bank is not None:
            state.idea_bank.selected_candidate_id = tournament.selected_candidate_id
            state.idea_bank.agenda_id = tournament.agenda_id or state.idea_bank.agenda_id
            state.idea_bank.rejected_candidate_ids = _dedupe([*state.idea_bank.rejected_candidate_ids, *tournament.rejected_candidate_ids])
            state.idea_bank.updated_at = utc_now_iso()
        rejected = set(tournament.rejected_candidate_ids)
        for candidate in state.candidates:
            if candidate.id in rejected:
                candidate.maturity = "rejected"
                candidate.rejection_reason = _rejection_reason(candidate.id, tournament.score_records)
        state.tournaments.append(tournament)
        self.store._save_state(tournament.project_id, state)
        if tournament.selected_candidate_id:
            selected = next((candidate for candidate in state.candidates if candidate.id == tournament.selected_candidate_id), None)
            if selected is not None and not selected.human_feedback_ids:
                self.store.add_review(
                    idea_id=selected.id,
                    reviewer="human-review-required",
                    status="uncertain",
                    novelty_judgment="Tournament selected this candidate, but final acceptance requires human review.",
                    feasibility_judgment="Confirm experiment, baselines, and time-to-demo before acceptance.",
                    impact_judgment="Confirm the selected idea is worth advancing.",
                    required_fixes=["Human review must approve before final acceptance."],
                    notes="Idea tournament selection is not final acceptance.",
                )


def _candidate_ids(candidates: list[IdeaCandidate], *, top_k: int) -> list[str]:
    active = [candidate for candidate in candidates if candidate.maturity not in {"agenda_item", "manuscript_ready"}]
    ordered = sorted(
        active,
        key=lambda candidate: (
            candidate.idea_yield_score,
            candidate.evidence_score,
            candidate.impact_score,
            candidate.tractability_score,
            candidate.title,
        ),
        reverse=True,
    )
    return [candidate.id for candidate in ordered[: max(1, top_k)]]


def _blockers(candidate: IdeaCandidate, state, known_paper_ids: set[str]) -> list[str]:
    blockers: list[str] = []
    if is_generic_idea_title(candidate.title):
        blockers.append("generic idea title")
    if candidate.maturity == "rejected":
        blockers.append(candidate.rejection_reason or "candidate is already rejected")
    if any(feedback.idea_id == candidate.id and feedback.action == "reject" for feedback in state.feedback_records):
        blockers.append("human feedback rejected this idea")
    if _has_fake_results(candidate):
        blockers.append("candidate claims results before experiments exist")
    unresolved = sorted(_claimed_paper_ids(candidate) - known_paper_ids)
    if unresolved:
        blockers.append(f"unresolved or fake citation ids: {', '.join(unresolved)}")
    latest_novelty = _latest_novelty(candidate.id, state)
    if candidate.novelty_status == "likely_duplicate" or (latest_novelty is not None and latest_novelty.verdict == "reject"):
        blockers.append("fatal novelty blocker")
    fatal_text = " ".join([candidate.rejection_reason, candidate.likely_failure_mode, candidate.summary]).lower()
    if any(marker in fatal_text for marker in FATAL_NOVELTY_MARKERS):
        blockers.append("fatal prior-work or reviewer blocker")
    if candidate.novelty_status == "strong" and not _strong_novelty_supported(candidate, state):
        blockers.append("unsupported strong novelty claim")
    if _has_accept_feedback(candidate.id, state) and not _acceptance_gates_satisfied(candidate, state):
        blockers.append("human acceptance lacks evidence or novelty gates")
    return _dedupe(blockers)


def _evidence_score(candidate: IdeaCandidate, state) -> float:
    links = [link for link in state.evidence_links if link.idea_id == candidate.id and link.link_type == "supports"]
    return _clamp(candidate.evidence_score + 0.1 * len(links) + 0.08 * len(candidate.supporting_paper_ids))


def _novelty_score(candidate: IdeaCandidate, state) -> float:
    latest = _latest_novelty(candidate.id, state)
    if latest is not None:
        if latest.verdict == "pursue":
            return 0.9 if latest.novelty_strength == "strong" else 0.72
        if latest.verdict == "revise":
            return 0.35
        if latest.verdict == "reject":
            return 0.0
        return 0.2
    return {
        "strong": 0.85,
        "plausible": 0.7,
        "unchecked": 0.25,
        "unknown": 0.2,
        "weak": 0.12,
        "likely_duplicate": 0.0,
    }.get(candidate.novelty_status, 0.2)


def _experimentability_score(candidate: IdeaCandidate) -> float:
    score = 0.0
    if candidate.proposed_experiment.strip():
        score += 0.35
    if candidate.expected_metrics:
        score += 0.3
    if candidate.expected_baselines:
        score += 0.2
    if candidate.contribution_type in {"benchmark", "measurement", "evaluation_protocol", "negative_result", "dataset", "tooling"}:
        score += 0.15
    return _clamp(score)


def _time_to_demo_score(candidate: IdeaCandidate) -> float:
    base = {
        "benchmark": 0.75,
        "measurement": 0.8,
        "evaluation_protocol": 0.75,
        "negative_result": 0.7,
        "tooling": 0.7,
        "dataset": 0.55,
        "replication": 0.65,
        "method": 0.45,
        "theory": 0.35,
        "survey": 0.5,
        "system": 0.45,
        "hybrid": 0.45,
    }.get(candidate.contribution_type, 0.45)
    if candidate.expected_baselines and candidate.expected_metrics:
        base += 0.1
    return _clamp(base)


def _benchmark_score(candidate: IdeaCandidate) -> float:
    text = " ".join([candidate.title, candidate.summary, candidate.proposed_experiment, " ".join(candidate.expected_baselines)]).lower()
    score = 0.7 if candidate.contribution_type == "benchmark" else 0.0
    if "benchmark" in text or "dataset" in text:
        score += 0.25
    return _clamp(score)


def _baseline_score(candidate: IdeaCandidate) -> float:
    return _clamp(0.25 * len(candidate.expected_baselines))


def _cross_domain_score(candidate: IdeaCandidate, state) -> float:
    source_text = " ".join([candidate.source_topic_id, candidate.provenance.created_by_skill, *candidate.provenance.source_ids]).lower()
    if "cross" in source_text or "transfer" in source_text:
        return 0.8
    if any(transfer.target_idea_id == candidate.id for transfer in state.transfer_candidates):
        return 0.75
    return 0.25


def _human_preference_score(candidate: IdeaCandidate, state) -> float:
    profile_score = _profile_preference_score(candidate, state)
    feedback_score = _feedback_preference_score(candidate.id, state)
    if feedback_score is not None:
        return _clamp(0.65 * feedback_score + 0.35 * profile_score)
    return profile_score


def _feedback_preference_score(idea_id: str, state) -> float | None:
    feedback = [record for record in state.feedback_records if record.idea_id == idea_id]
    if not feedback:
        return None
    score = 0.35
    for record in feedback:
        if record.action == "accept":
            score += 0.55
        elif record.action == "upvote":
            score += 0.25
        elif record.action in {"request_mutation", "request_search"}:
            score += 0.05
        elif record.action == "downvote":
            score -= 0.25
        elif record.action == "reject":
            score = 0.0
    return _clamp(score)


def _profile_preference_score(candidate: IdeaCandidate, state) -> float:
    profiles = state.preference_profiles
    if not profiles:
        return _review_preference_score(candidate, state)
    profile = profiles[-1]
    text = " ".join([candidate.title, candidate.summary, candidate.source_topic_id]).lower()
    score = 0.35
    if candidate.contribution_type in profile.preferred_contribution_types:
        score += 0.35
    if any(domain.lower() in text for domain in profile.preferred_domains):
        score += 0.2
    if any(topic.lower() in text for topic in profile.avoid_topics):
        score -= 0.45
    if profile.risk_tolerance == "low" and candidate.reviewer_risk_score > 0.6:
        score -= 0.15
    if profile.time_budget in {"short", "days", "week"} and _time_to_demo_score(candidate) >= 0.7:
        score += 0.1
    return _clamp(score)


def _review_preference_score(candidate: IdeaCandidate, state) -> float:
    reviews = [review for review in state.reviews if review.idea_id == candidate.id]
    if not reviews:
        return 0.35
    latest = reviews[-1]
    return {"accepted": 1.0, "revise": 0.55, "uncertain": 0.45, "rejected": 0.0}.get(latest.status, 0.35)


def _total_score(record: IdeaScoreRecord) -> float:
    return round(
        0.16 * record.evidence_score
        + 0.16 * record.novelty_score
        + 0.12 * record.experimentability_score
        + 0.1 * record.tractability_score
        + 0.12 * record.impact_score
        + 0.1 * record.reviewer_risk_score
        + 0.07 * record.time_to_demo_score
        + 0.05 * record.benchmark_score
        + 0.05 * record.baseline_score
        + 0.04 * record.cross_domain_score
        + 0.03 * record.human_preference_score,
        4,
    )


def _latest_novelty(idea_id: str, state):
    assessments = [assessment for assessment in state.novelty_assessments if assessment.idea_id == idea_id]
    return assessments[-1] if assessments else None


def _has_accept_feedback(idea_id: str, state) -> bool:
    return any(feedback.idea_id == idea_id and feedback.action == "accept" for feedback in state.feedback_records)


def _acceptance_gates_satisfied(candidate: IdeaCandidate, state) -> bool:
    latest = _latest_novelty(candidate.id, state)
    novelty_ok = candidate.novelty_status in {"plausible", "strong"} or (
        latest is not None and latest.verdict == "pursue" and not latest.missing_searches
    )
    evidence_ok = bool(candidate.closest_prior_work_ids or candidate.supporting_paper_ids or candidate.evidence_span_ids)
    if latest is not None:
        evidence_ok = evidence_ok or bool(latest.closest_prior_work_ids)
    return novelty_ok and evidence_ok


def _strong_novelty_supported(candidate: IdeaCandidate, state) -> bool:
    latest = _latest_novelty(candidate.id, state)
    if latest is not None:
        return latest.verdict == "pursue" and latest.novelty_strength == "strong" and not latest.missing_searches
    return bool(candidate.closest_prior_work_ids)


def _claimed_paper_ids(candidate: IdeaCandidate) -> set[str]:
    return {
        paper_id
        for paper_id in [
            *candidate.closest_prior_work_ids,
            *candidate.supporting_paper_ids,
            *candidate.counterevidence_paper_ids,
        ]
        if paper_id
    }


def _has_fake_results(candidate: IdeaCandidate) -> bool:
    text = " ".join([candidate.title, candidate.summary, candidate.core_claim, candidate.proposed_experiment]).lower()
    return any(marker in text for marker in RESULT_CLAIM_MARKERS)


def _selection_reason(record: IdeaScoreRecord) -> str:
    return f"Selected `{record.idea_id}` with total score {record.total_score:.3f}; human review is required before final acceptance."


def _rejection_reason(idea_id: str, records: list[IdeaScoreRecord]) -> str:
    record = next((item for item in records if item.idea_id == idea_id), None)
    if record is None:
        return "Idea tournament rejected this candidate."
    return f"Idea tournament disqualified candidate: {'; '.join(record.blockers) or 'not viable'}."


def _tournament_id(project_id: str, candidate_ids: list[str], selected_or_agenda: str) -> str:
    digest = hashlib.sha1("::".join([project_id, *candidate_ids, selected_or_agenda, utc_now_compact()]).encode()).hexdigest()[:10]
    return f"idea-tournament-{digest}"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
