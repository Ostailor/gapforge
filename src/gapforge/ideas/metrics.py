"""Idea-yield metrics for v2 discovery projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.generator import is_generic_idea_title
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolioGenerator
from gapforge.models import to_plain
from gapforge.project_memory import ProjectMemoryManager

DUPLICATE_MARKERS = (
    "duplicate",
    "fatal prior work",
    "already done",
    "already solves",
    "not novel",
    "subsumes",
)


@dataclass(slots=True)
class IdeaYieldMetrics:
    project_id: str
    topic_variant_count: int = 0
    candidate_count: int = 0
    mutation_count: int = 0
    constructive_gap_count: int = 0
    cross_domain_transfer_count: int = 0
    rejected_duplicate_count: int = 0
    rejected_generic_count: int = 0
    novelty_unknown_count: int = 0
    tournament_survivor_count: int = 0
    human_accepted_idea_count: int = 0
    agenda_generated: bool = False
    idea_yield_rate: float = 0.0
    time_to_selected_idea: float = 0.0
    evidence_per_candidate: float = 0.0
    prior_work_per_candidate: float = 0.0
    selected_idea_id: str = ""
    agenda_id: str = ""


class IdeaYieldMetricCalculator:
    """Compute auditable idea-yield metrics from persisted project state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.portfolios = TopicPortfolioGenerator(config)
        self.projects = ProjectMemoryManager(config)

    def compute(self, project_id: str) -> IdeaYieldMetrics:
        state = self.store.load_state(project_id)
        portfolios = self.portfolios.list_project_portfolios(project_id)
        candidates = state.candidates
        candidate_count = len(candidates)
        selected_idea_id = _selected_idea_id(state)
        accepted_idea_ids = _human_accepted_idea_ids(state)
        latest_tournament = state.tournaments[-1] if state.tournaments else None
        agenda_id = _agenda_id(state)
        metrics = IdeaYieldMetrics(
            project_id=project_id,
            topic_variant_count=sum(len(portfolio.topic_variants) for portfolio in portfolios),
            candidate_count=candidate_count,
            mutation_count=len(state.mutations),
            constructive_gap_count=len(state.constructive_gaps),
            cross_domain_transfer_count=len(state.transfer_candidates),
            rejected_duplicate_count=len([candidate for candidate in candidates if _is_rejected_duplicate(candidate)]),
            rejected_generic_count=len([candidate for candidate in candidates if _is_rejected_generic(candidate)]),
            novelty_unknown_count=len(
                [
                    candidate
                    for candidate in candidates
                    if candidate.novelty_status in {"unchecked", "unknown"} and candidate.maturity != "rejected"
                ]
            ),
            tournament_survivor_count=len([record for record in latest_tournament.score_records if not record.blockers])
            if latest_tournament is not None
            else 0,
            human_accepted_idea_count=len(accepted_idea_ids),
            agenda_generated=bool(agenda_id),
            idea_yield_rate=round(len(accepted_idea_ids) / candidate_count, 4) if candidate_count else 0.0,
            time_to_selected_idea=_time_to_selected_idea(state, selected_idea_id),
            evidence_per_candidate=round(len(state.evidence_links) / candidate_count, 4) if candidate_count else 0.0,
            prior_work_per_candidate=round(
                sum(len(candidate.closest_prior_work_ids) for candidate in candidates) / candidate_count,
                4,
            )
            if candidate_count
            else 0.0,
            selected_idea_id=selected_idea_id,
            agenda_id=agenda_id,
        )
        return metrics

    def render_report(self, project_id: str) -> str:
        return render_idea_yield_report(self.compute(project_id))

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        program = self.projects.load_project(project_id)
        reports_dir = Path(program.project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "idea_yield.md").write_text(report, encoding="utf-8")
        (reports_dir / "idea_yield.json").write_text(json.dumps(to_plain(self.compute(project_id)), indent=2) + "\n", encoding="utf-8")
        return report


def render_idea_yield_report(metrics: IdeaYieldMetrics) -> str:
    lines = [
        "# Idea Yield Metrics",
        "",
        "Idea yield measures whether v2 is actually finding defensible ideas instead of only refusing.",
        "",
        f"- Project ID: `{metrics.project_id}`",
        f"- Selected idea: `{metrics.selected_idea_id or 'none'}`",
        f"- Agenda: `{metrics.agenda_id or 'none'}`",
        "",
        "## Counts",
        "",
        f"- Topic variants: {metrics.topic_variant_count}",
        f"- Candidates: {metrics.candidate_count}",
        f"- Mutations: {metrics.mutation_count}",
        f"- Constructive gaps: {metrics.constructive_gap_count}",
        f"- Cross-domain transfers: {metrics.cross_domain_transfer_count}",
        f"- Rejected duplicates: {metrics.rejected_duplicate_count}",
        f"- Rejected generic ideas: {metrics.rejected_generic_count}",
        f"- Novelty unknown: {metrics.novelty_unknown_count}",
        f"- Tournament survivors: {metrics.tournament_survivor_count}",
        f"- Human-accepted ideas: {metrics.human_accepted_idea_count}",
        f"- Agenda generated: {str(metrics.agenda_generated).lower()}",
        "",
        "## Rates",
        "",
        f"- Idea yield rate: {metrics.idea_yield_rate:.4f}",
        f"- Time to selected idea seconds: {metrics.time_to_selected_idea:.1f}",
        f"- Evidence links per candidate: {metrics.evidence_per_candidate:.4f}",
        f"- Closest prior work IDs per candidate: {metrics.prior_work_per_candidate:.4f}",
        "",
    ]
    if metrics.human_accepted_idea_count == 0:
        lines.append(
            "No human-accepted idea is recorded. v2 release gates should treat this as zero idea yield unless an agenda "
            "fallback is explicitly accepted."
        )
    return "\n".join(lines).rstrip() + "\n"


def _selected_idea_id(state) -> str:
    if state.idea_bank is not None and state.idea_bank.selected_candidate_id:
        return state.idea_bank.selected_candidate_id
    if state.tournaments:
        return state.tournaments[-1].selected_candidate_id
    return ""


def _agenda_id(state) -> str:
    if state.idea_bank is not None and state.idea_bank.agenda_id:
        return state.idea_bank.agenda_id
    if state.tournaments and state.tournaments[-1].agenda_id:
        return state.tournaments[-1].agenda_id
    if state.agendas:
        return state.agendas[-1].id
    return ""


def _human_accepted_idea_ids(state) -> set[str]:
    accepted = {feedback.idea_id for feedback in state.feedback_records if feedback.action == "accept"}
    accepted.update(review.idea_id for review in state.reviews if review.status == "accepted")
    return {idea_id for idea_id in accepted if idea_id}


def _is_rejected_duplicate(candidate) -> bool:
    if candidate.maturity != "rejected":
        return False
    text = f"{candidate.rejection_reason} {candidate.likely_failure_mode} {candidate.summary}".lower()
    return candidate.novelty_status == "likely_duplicate" or any(marker in text for marker in DUPLICATE_MARKERS)


def _is_rejected_generic(candidate) -> bool:
    if candidate.maturity != "rejected":
        return False
    text = f"{candidate.rejection_reason} {candidate.summary}".lower()
    return is_generic_idea_title(candidate.title) or "generic" in text


def _time_to_selected_idea(state, selected_idea_id: str) -> float:
    if state.idea_bank is None or not selected_idea_id:
        return 0.0
    start = _parse_time(state.idea_bank.created_at or state.idea_bank.provenance.timestamp)
    if start is None:
        return 0.0
    end = _selected_time(state, selected_idea_id)
    if end is None:
        return 0.0
    return max(0.0, round((end - start).total_seconds(), 3))


def _selected_time(state, selected_idea_id: str) -> datetime | None:
    times: list[datetime] = []
    for feedback in state.feedback_records:
        if feedback.idea_id == selected_idea_id and feedback.action == "accept":
            parsed = _parse_time(feedback.provenance.timestamp)
            if parsed is not None:
                times.append(parsed)
    for review in state.reviews:
        if review.idea_id == selected_idea_id and review.status == "accepted":
            parsed = _parse_time(review.provenance.timestamp)
            if parsed is not None:
                times.append(parsed)
    for tournament in state.tournaments:
        if tournament.selected_candidate_id == selected_idea_id:
            parsed = _parse_time(tournament.provenance.timestamp)
            if parsed is not None:
                times.append(parsed)
    candidate = next((item for item in state.candidates if item.id == selected_idea_id), None)
    if candidate is not None:
        parsed = _parse_time(candidate.provenance.timestamp)
        if parsed is not None:
            times.append(parsed)
    return max(times) if times else None


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
