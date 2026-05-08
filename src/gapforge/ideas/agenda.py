"""Research agenda mode for honest no-idea outcomes."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.config import GapForgeConfig
from gapforge.ideas.models import AgendaStep, IdeaScoreRecord, ResearchAgenda, validate_agenda_step_type
from gapforge.ideas.store import IdeaStore
from gapforge.models import Provenance, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_compact, utc_now_iso


class ResearchAgendaManager:
    """Create staged agenda fallbacks when no idea is defensible yet."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.store = IdeaStore(config)
        self.campaigns = CampaignManager(config)

    def generate(
        self,
        project_id: str,
        *,
        blocker_summary: str = "",
        source_ids: list[str] | None = None,
    ) -> ResearchAgenda:
        program = self.project_manager.load_project(project_id)
        state = self.store.load_state(project_id)
        root_topic = _root_topic(program, state.idea_bank.root_topic if state.idea_bank is not None else "")
        if state.idea_bank is None:
            self.store.create_bank(project_id=project_id, root_topic=root_topic)
            state = self.store.load_state(project_id)
        blockers = _blocker_summary(state, blocker_summary=blocker_summary)
        agenda_id = _agenda_id(project_id, root_topic, blockers, len(state.agendas) + 1)
        steps = _agenda_steps(agenda_id, project_id, root_topic, blockers)
        agenda = ResearchAgenda(
            id=agenda_id,
            project_id=project_id,
            root_topic=root_topic,
            blocker_summary=blockers,
            agenda_steps=steps,
            expected_artifacts=_dedupe([step.required_artifact for step in steps]),
            decision_points=[
                "After the search step, rerun the idea-specific novelty loop on surviving seeds.",
                "After benchmark, dataset, or measurement artifacts exist, rerun the idea tournament.",
                "After human review, either promote a defensible candidate or keep the agenda as the active outcome.",
            ],
            stop_conditions=[
                "Stop if closest prior work fully subsumes all candidate contribution forms.",
                "Stop if no executable benchmark, dataset, baseline, or measurement artifact can be specified.",
                "Stop if human review rejects the remaining direction after blockers are documented.",
            ],
            estimated_effort=_estimated_effort(steps),
            provenance=Provenance(
                created_by_skill="research-agenda",
                source_ids=[project_id, *(source_ids or [])],
                timestamp=utc_now_iso(),
                reasoning_summary=("Created a staged agenda because current evidence does not justify a single accepted idea candidate."),
            ),
        )
        agenda = self.store.add_research_agenda(agenda)
        self._sync_legacy_direction(agenda)
        self.write_report(agenda.id)
        return agenda

    def load_agenda(self, agenda_id: str) -> ResearchAgenda:
        for project in self.project_manager.list_projects():
            state = self.store.load_state(project.id)
            agenda = next((item for item in state.agendas if item.id == agenda_id), None)
            if agenda is not None:
                return agenda
        raise FileNotFoundError(f"No research agenda found for {agenda_id}")

    def render_report(self, agenda_id: str) -> str:
        return render_research_agenda_markdown(self.load_agenda(agenda_id))

    def write_report(self, agenda_id: str) -> str:
        agenda = self.load_agenda(agenda_id)
        report = render_research_agenda_markdown(agenda)
        reports_dir = self._reports_dir(agenda.project_id)
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{agenda.id}.md").write_text(report, encoding="utf-8")
        (reports_dir / "research_agenda.md").write_text(report, encoding="utf-8")
        return report

    def agenda_to_campaigns(self, agenda_id: str) -> list[CampaignState]:
        agenda = self.load_agenda(agenda_id)
        campaigns: list[CampaignState] = []
        for step in agenda.agenda_steps:
            if step.step_type == "human_review":
                continue
            campaigns.append(
                self.campaigns.create_campaign(
                    _campaign_topic(agenda, step),
                    project_id=agenda.project_id,
                    title=f"Agenda {step.step_type}: {_short_title(step.description)}",
                    source_profile="generic",
                    budget_id="small",
                )
            )
        return campaigns

    def _sync_legacy_direction(self, agenda: ResearchAgenda) -> None:
        program = self.project_manager.load_project(agenda.project_id)
        direction = ResearchDirection(
            id=agenda.id,
            project_id=agenda.project_id,
            title=f"Research agenda for {agenda.root_topic}",
            summary=(
                "This is an agenda fallback, not a paper idea. It records blockers and staged artifacts needed before "
                "GapForge can try to promote a future idea candidate."
            ),
            maturity="agenda_item",
            readiness_score=0.0,
            blocking_issues=[agenda.blocker_summary],
            next_actions=[step.description for step in agenda.agenda_steps],
            provenance=agenda.provenance,
        )
        program.research_directions = [item for item in program.research_directions if item.id != agenda.id]
        program.research_directions.append(direction)
        self.project_manager.save_project(program)

    def _reports_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        return Path(program.project.root_dir) / "ideas" / "reports"


def render_research_agenda_markdown(agenda: ResearchAgenda) -> str:
    lines = [
        "# Research Agenda",
        "",
        "This agenda is not a paper idea and is not paper-ready. It is the honest outcome when no single idea is defensible yet.",
        "",
        f"- Agenda ID: `{agenda.id}`",
        f"- Project ID: `{agenda.project_id}`",
        f"- Root topic: {agenda.root_topic}",
        f"- Estimated effort: {agenda.estimated_effort or 'unknown'}",
        "",
        "## Blockers",
        "",
        agenda.blocker_summary or "No blockers recorded.",
        "",
        "## Steps",
        "",
    ]
    for step in agenda.agenda_steps:
        lines.extend(
            [
                f"### `{step.step_type}`",
                "",
                f"- Step ID: `{step.id}`",
                f"- Description: {step.description}",
                f"- Required artifact: {step.required_artifact}",
                f"- Success criteria: {step.success_criteria}",
                f"- Next decision: {step.next_decision}",
                "",
            ]
        )
    lines.extend(["## Expected Artifacts", ""])
    lines.extend(f"- {artifact}" for artifact in agenda.expected_artifacts)
    lines.extend(["", "## Decision Points", ""])
    lines.extend(f"- {point}" for point in agenda.decision_points)
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {condition}" for condition in agenda.stop_conditions)
    return "\n".join(lines).rstrip() + "\n"


def _root_topic(program, bank_topic: str) -> str:
    if bank_topic:
        return bank_topic
    if program.topics:
        return program.topics[0].text
    return program.project.description or program.project.name


def _blocker_summary(state, *, blocker_summary: str) -> str:
    blockers: list[str] = []
    if blocker_summary:
        blockers.append(blocker_summary)
    if not state.candidates:
        blockers.append("No idea candidates exist or survived active search.")
    for candidate in state.candidates:
        if candidate.maturity == "rejected":
            reason = candidate.rejection_reason or "rejected without a detailed reason"
            blockers.append(f"Rejected idea `{candidate.id}` ({candidate.title}): {reason}")
    if state.tournaments:
        for record in state.tournaments[-1].score_records:
            if record.blockers:
                blockers.append(f"Tournament blocker for `{record.idea_id}`: {'; '.join(record.blockers)}")
    for assessment in state.novelty_assessments:
        if assessment.verdict in {"reject", "unknown"}:
            detail = assessment.similarity_summary or "; ".join(assessment.missing_searches) or assessment.verdict
            blockers.append(f"Novelty blocker for `{assessment.idea_id}`: {detail}")
    for feedback in state.feedback_records:
        if feedback.action == "reject":
            blockers.append(f"Human rejection for `{feedback.idea_id}`: {feedback.rationale or feedback.notes or 'no rationale'}")
    return "\n".join(f"- {item}" for item in _dedupe(blockers[:10]))


def _agenda_steps(agenda_id: str, project_id: str, root_topic: str, blockers: str) -> list[AgendaStep]:
    source_ids = [project_id, agenda_id]
    now = utc_now_iso()
    specs = [
        (
            "search",
            "Run targeted prior-work and counterevidence searches on the blocked idea dimensions.",
            "prior-work and counterevidence search matrix",
            "Each surviving topic variant has closest-prior-work IDs, missing-search notes, or an explicit unknown verdict.",
            "Rerun idea-novelty and reject, mutate, or pursue each seed.",
        ),
        (
            "benchmark",
            "Define the smallest benchmark that could make the topic empirically testable.",
            "benchmark specification with tasks, metrics, baselines, and exclusion criteria",
            "At least one benchmark candidate has executable metrics and identifiable baselines.",
            "Promote benchmark-backed seeds into the tournament or stop if no benchmark is feasible.",
        ),
        (
            "measurement",
            "Measure honest-baseline behavior so future claims have false-positive and failure-rate anchors.",
            "measurement plan with population, metrics, and analysis thresholds",
            "The project has a falsifiable measurement protocol and enough baselines to estimate uncertainty.",
            "Create measurement-study candidates or stop if the measurement cannot be made reliable.",
        ),
        (
            "baseline_study",
            "Inventory available baselines and replicate enough of them to know what a future contribution must beat.",
            "baseline replication ledger",
            "Relevant baselines are runnable, blocked with reasons, or ruled out with documented evidence.",
            "Use the ledger to update tractability and reviewer-risk scores.",
        ),
        (
            "dataset",
            "Specify the minimum dataset or simulation harness needed to separate honest from target behaviors.",
            "dataset or simulation harness card",
            "A concrete data artifact exists with inclusion rules, labels, controls, and known limitations.",
            "Create dataset, benchmark, or negative-result candidates from the artifact.",
        ),
        (
            "human_review",
            "Ask a human reviewer to choose which artifact path is worth another idea-search pass.",
            "human preference and blocker review",
            "A reviewer accepts the staged path, requests mutation, or rejects the topic with rationale.",
            "Either rerun active idea search with preferences or keep the agenda as the release outcome.",
        ),
    ]
    steps: list[AgendaStep] = []
    for index, (step_type, description, artifact, criteria, next_decision) in enumerate(specs, start=1):
        steps.append(
            AgendaStep(
                id=_step_id(agenda_id, index, step_type, root_topic),
                agenda_id=agenda_id,
                step_type=validate_agenda_step_type(step_type),
                description=f"{description} Root topic: {root_topic}. Blocker context: {_compact_blockers(blockers)}",
                required_artifact=artifact,
                success_criteria=criteria,
                next_decision=next_decision,
                provenance=Provenance(
                    created_by_skill="research-agenda",
                    source_ids=source_ids,
                    timestamp=now,
                    reasoning_summary="Added a concrete agenda step that creates evidence before any future paper idea claim.",
                ),
            )
        )
    return steps


def _estimated_effort(steps: list[AgendaStep]) -> str:
    non_review = len([step for step in steps if step.step_type != "human_review"])
    return f"{max(1, non_review)} staged work items; plan one small campaign per non-review step before rerunning idea selection."


def _campaign_topic(agenda: ResearchAgenda, step: AgendaStep) -> str:
    return f"{agenda.root_topic} :: agenda {step.step_type} :: {step.required_artifact}"


def _short_title(text: str) -> str:
    return text.split(".")[0][:80].rstrip()


def _compact_blockers(blockers: str) -> str:
    text = " ".join(line.removeprefix("- ").strip() for line in blockers.splitlines() if line.strip())
    return text[:240] if text else "uncertainty remains about novelty, evidence, or feasibility"


def _agenda_id(project_id: str, root_topic: str, blockers: str, index: int) -> str:
    digest = hashlib.sha1(f"{project_id}::{root_topic}::{blockers}::{index}::{utc_now_compact()}".encode()).hexdigest()[:8]
    return f"research-agenda-{utc_now_compact()}-{slugify(root_topic)}-{digest}"


def _step_id(agenda_id: str, index: int, step_type: str, root_topic: str) -> str:
    digest = hashlib.sha1(f"{agenda_id}::{index}::{step_type}::{root_topic}".encode()).hexdigest()[:8]
    return f"agenda-step-{index}-{step_type}-{digest}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def tournament_blocker_summary(score_records: list[IdeaScoreRecord]) -> str:
    blockers = [f"{record.idea_id}: {'; '.join(record.blockers)}" for record in score_records if record.blockers]
    return "\n".join(f"- {item}" for item in blockers) or "- No tournament candidate was viable."
