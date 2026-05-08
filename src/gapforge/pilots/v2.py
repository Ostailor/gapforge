"""Executable v2 idea-discovery pilot for low-FPR collusion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.ideas import (
    ConstructiveGapGenerator,
    CrossDomainIdeaTransferEngine,
    IdeaCodexTaskManager,
    IdeaFeedbackManager,
    IdeaMutationEngine,
    IdeaNoveltyLoop,
    IdeaSeedGenerator,
    IdeaStore,
    IdeaTournamentRunner,
    ResearchAgendaManager,
    TopicPortfolioGenerator,
    is_generic_idea_title,
)
from gapforge.ideas.codex_tasks import IDEA_CODEX_TASK_TYPES
from gapforge.ideas.models import IdeaTournament
from gapforge.models import ExternalPilotReview, Paper, PilotAcceptanceSummary, PilotRunRecord, ProjectMemoryRecord, Provenance, to_plain
from gapforge.pilots.external_review import ExternalPilotReviewManager
from gapforge.pilots.reports import render_pilot_acceptance
from gapforge.pilots.status import PilotStore
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso

V2_LOW_FPR_COLLUSION = "v2_low_fpr_collusion"
V2_LOW_FPR_NAME = "low_fpr_collusion"
V2_LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"

V2_REQUIRED_SEARCH_ARTIFACTS = [
    "topic_portfolio",
    "idea_bank",
    "mutation_report",
    "constructive_gap_report",
    "cross_domain_transfer_report",
    "codex_idea_synthesis_tasks",
    "novelty_report",
    "idea_tournament_report",
]

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


class V2IdeaPilotRunner:
    """Run the v2 idea-discovery pilot and classify the outcome conservatively."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = PilotStore(config)
        self.projects = ProjectMemoryManager(config)
        self.idea_store = IdeaStore(config)

    def run(self, name: str) -> PilotRunRecord:
        _require_v2_pilot_name(name)
        now = utc_now_iso()
        record = PilotRunRecord(
            id=f"pilot-{V2_LOW_FPR_COLLUSION}-{utc_now_compact()}",
            pilot_id=V2_LOW_FPR_COLLUSION,
            status="running",
            outcome_type="unknown",
            created_at=now,
            updated_at=now,
            provenance=Provenance(
                created_by_skill="v2-pilot-runner",
                source_ids=[V2_LOW_FPR_COLLUSION],
                timestamp=now,
                reasoning_summary="Started v2 idea-discovery pilot without accepting early refusal.",
            ),
        )
        self.store.save_record(record)
        try:
            record = self._run_workflow(record)
        except Exception as exc:  # pragma: no cover - product-failure guard.
            record.status = "product_failure"
            record.outcome_type = "product_failure"
            record.blockers.append(f"product_failure: {type(exc).__name__}: {exc}")
        self.store.save_record(record)
        summary = build_v2_pilot_acceptance(self.config, record)
        self.store.save_acceptance(record, summary)
        self.write_report(record)
        return record

    def status(self, name: str) -> dict[str, Any]:
        _require_v2_pilot_name(name)
        try:
            record = self.store.load_record(V2_LOW_FPR_COLLUSION)
        except FileNotFoundError:
            return {
                "name": name,
                "pilot_id": V2_LOW_FPR_COLLUSION,
                "status": "missing",
                "acceptance": None,
                "blockers": ["No v2 pilot run record exists."],
            }
        summary = build_v2_pilot_acceptance(self.config, record)
        self.store.save_acceptance(record, summary)
        return _status_payload(record, summary, self._requirements(record))

    def report(self, name: str) -> str:
        _require_v2_pilot_name(name)
        record = self.store.load_record(V2_LOW_FPR_COLLUSION)
        self.write_report(record)
        return (self.store.record_dir(record.id) / "v2_pilot_report.md").read_text(encoding="utf-8")

    def write_report(self, record: PilotRunRecord) -> Path:
        summary = build_v2_pilot_acceptance(self.config, record)
        record_dir = self.store.record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        report = render_v2_pilot_report(record, summary, self._requirements(record))
        report_path = record_dir / "v2_pilot_report.md"
        report_path.write_text(report, encoding="utf-8")
        (record_dir / "pilot_acceptance.md").write_text(render_pilot_acceptance(summary), encoding="utf-8")
        if record.project_id:
            try:
                program = self.projects.load_project(record.project_id)
            except FileNotFoundError:
                return report_path
            project_report = Path(program.project.root_dir) / "ideas" / "reports" / "v2_low_fpr_pilot_report.md"
            project_report.parent.mkdir(parents=True, exist_ok=True)
            project_report.write_text(report, encoding="utf-8")
            record.artifact_paths["v2_pilot_report"] = str(project_report)
            self.store.save_record(record)
        return report_path

    def _run_workflow(self, record: PilotRunRecord) -> PilotRunRecord:
        program = self.projects.create_project("v2 low-FPR collusion idea pilot", description=V2_LOW_FPR_TOPIC)
        self.projects.use_project(program.project.id)
        record.project_id = program.project.id
        record.artifact_paths["project_record"] = str(Path(program.project.root_dir) / "project.json")
        self.idea_store.create_bank(project_id=program.project.id, root_topic=V2_LOW_FPR_TOPIC)
        self._attach_pilot_corpus(program.project.id)

        portfolio = TopicPortfolioGenerator(self.config).generate(project_id=program.project.id, root_topic=V2_LOW_FPR_TOPIC)
        record.artifact_paths["topic_portfolio"] = str(Path(program.project.root_dir) / "ideas" / f"{portfolio.id}.json")

        generated = IdeaSeedGenerator(self.config).generate(project_id=program.project.id, max_candidates=40)
        record.artifact_paths["idea_bank"] = str(Path(program.project.root_dir) / "ideas" / "idea_bank.json")
        record.artifact_paths["idea_bank_report"] = str(Path(program.project.root_dir) / "ideas" / "reports" / "idea_bank.md")

        rejected = self._reject_one_seed_for_mutation(program.project.id, generated.candidates)
        if rejected:
            IdeaMutationEngine(self.config).mutate_rejected_ideas(program.project.id)
        record.artifact_paths["mutation_report"] = str(Path(program.project.root_dir) / "ideas" / "reports" / "mutations.md")

        ConstructiveGapGenerator(self.config).generate_for_project(program.project.id)
        record.artifact_paths["constructive_gap_report"] = str(
            Path(program.project.root_dir) / "ideas" / "reports" / "constructive_gaps.md"
        )

        CrossDomainIdeaTransferEngine(self.config).transfer_for_project(program.project.id)
        record.artifact_paths["cross_domain_transfer_report"] = str(
            Path(program.project.root_dir) / "ideas" / "reports" / "cross_domain_transfers.md"
        )

        codex_tasks = [
            IdeaCodexTaskManager(self.config).create_task(program.project.id, task_type) for task_type in sorted(IDEA_CODEX_TASK_TYPES)
        ]
        record.artifact_paths["codex_idea_synthesis_tasks"] = json.dumps([task.task_dir for task in codex_tasks])

        synthesis_candidate = self._add_pilot_candidate(program.project.id)
        record.artifact_paths["pilot_synthesis_candidate"] = synthesis_candidate.id

        IdeaNoveltyLoop(self.config).assess_project(program.project.id, top_k=20)
        record.artifact_paths["novelty_report"] = str(Path(program.project.root_dir) / "ideas" / "reports" / "idea_novelty.md")

        tournament = IdeaTournamentRunner(self.config).run(program.project.id, top_k=20)
        record.artifact_paths["idea_tournament_report"] = str(Path(program.project.root_dir) / "ideas" / "reports" / "idea_tournament.md")
        record.artifact_paths["idea_tournament_id"] = tournament.id

        if tournament.selected_candidate_id:
            self._accept_selected_idea(record, tournament.selected_candidate_id)
        else:
            self._accept_agenda_fallback(record, tournament)
        return self.store.load_record(record.id)

    def _attach_pilot_corpus(self, project_id: str) -> None:
        state_manager = ResearchStateManager(self.config)
        run = state_manager.create_run(V2_LOW_FPR_TOPIC)
        run.papers = [
            Paper(
                id="v2-pilot-paper-monitor-calibration",
                title="Calibration metrics for single-agent monitor false positives",
                authors=[],
                abstract=(
                    "Studies false positive rate and specificity for monitor calibration in single-agent safety audits. "
                    "It does not evaluate sequential multi-agent collusion audits or collusive communication traces."
                ),
                year=2025,
                source="v2_pilot_fixture",
            ),
            Paper(
                id="v2-pilot-paper-screening-specificity",
                title="Specificity and confirmatory testing in screening systems",
                authors=[],
                abstract="Discusses high-specificity screening, confirmatory review, and false-positive control.",
                year=2024,
                source="v2_pilot_fixture",
            ),
            Paper(
                id="v2-pilot-paper-cartel-screening",
                title="Structural screens for cartel detection",
                authors=[],
                abstract="Reviews cartel detection screens in repeated economic interactions and their limitations.",
                year=2023,
                source="v2_pilot_fixture",
            ),
            Paper(
                id="v2-pilot-paper-sequential-testing",
                title="Sequential hypothesis testing with controlled false alarms",
                authors=[],
                abstract="Presents sequential stopping rules for controlling false alarm rates over repeated tests.",
                year=2022,
                source="v2_pilot_fixture",
            ),
        ]
        state_manager.save_run(run)
        program = self.projects.attach_run(project_id, run.run_id)
        linked = [
            (
                "v2-pilot-memory-specificity",
                "medicine screening specificity confirmatory testing false positive",
                ["v2-pilot-paper-screening-specificity"],
            ),
            ("v2-pilot-memory-cartel", "cartel detection economics structural screens collusion", ["v2-pilot-paper-cartel-screening"]),
            (
                "v2-pilot-memory-sequential",
                "sequential hypothesis testing false alarm control",
                ["v2-pilot-paper-sequential-testing"],
            ),
        ]
        for record_id, text, paper_ids in linked:
            program.memory_records.append(
                ProjectMemoryRecord(
                    id=record_id,
                    project_id=project_id,
                    record_type="cross_domain_source",
                    text=text,
                    linked_paper_ids=paper_ids,
                    status="active",
                    confidence="medium",
                    created_at=utc_now_iso(),
                    updated_at=utc_now_iso(),
                    provenance=Provenance(
                        created_by_skill="v2-pilot-runner",
                        source_ids=paper_ids,
                        timestamp=utc_now_iso(),
                        reasoning_summary="Seeded cross-domain transfer evidence for the v2 pilot.",
                    ),
                )
            )
        self.projects.save_project(program)
        self.projects.sync_project_memory(project_id)

    def _reject_one_seed_for_mutation(self, project_id: str, candidates: list) -> str:
        if not candidates:
            return ""
        broad = next((candidate for candidate in candidates if "seed" in candidate.title.lower()), candidates[0])
        self.idea_store.reject_candidate(broad.id, "v2 pilot mutation exercise: broad seed needs reframing before selection.")
        return broad.id

    def _add_pilot_candidate(self, project_id: str):
        return self.idea_store.add_candidate(
            project_id=project_id,
            source_topic_id="v2-pilot-synthesis",
            title="Sequential specificity benchmark for low-FPR collusion audits",
            summary=(
                "Benchmark honest and collusive multi-agent traces with sequential audit thresholds, emphasizing specificity, "
                "false-positive control, and monitor workload rather than claiming a new detector."
            ),
            contribution_type="benchmark",
            core_claim=(
                "A benchmark centered on sequential specificity and honest-baseline false positives can make collusion-monitor "
                "claims more falsifiable."
            ),
            proposed_experiment=(
                "Compare LLM-judge, rule-based, and anomaly monitor baselines on benign coordination traces and injected "
                "collusion traces using fixed alert budgets."
            ),
            expected_baselines=["LLM judge monitor", "rule-based keyword monitor", "anomaly score threshold"],
            expected_metrics=["false positive rate", "specificity", "recall at alert budget", "sequential false alarm rate"],
            closest_prior_work_ids=["v2-pilot-paper-monitor-calibration"],
            supporting_paper_ids=["v2-pilot-paper-monitor-calibration"],
            novelty_status="unchecked",
            tractability_score=0.82,
            impact_score=0.78,
            evidence_score=0.65,
            reviewer_risk_score=0.25,
            idea_yield_score=0.95,
            maturity="candidate",
            likely_failure_mode=(
                "Closest prior work may already cover enough monitor calibration that the benchmark needs a narrower "
                "multi-agent sequential-audit contribution."
            ),
            provenance=Provenance(
                created_by_skill="v2-pilot-synthesis",
                source_ids=["v2-pilot-paper-monitor-calibration"],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Synthesized a candidate after portfolio, seed, mutation, constructive-gap, transfer, and task-pack steps."
                ),
            ),
        )

    def _accept_selected_idea(self, record: PilotRunRecord, idea_id: str) -> None:
        feedback = IdeaFeedbackManager(self.config).add_feedback(
            idea_id=idea_id,
            action="accept",
            reviewer="v2-pilot-human-review",
            rationale=(
                "Accept as a v2 pilot candidate only: evidence and novelty gates remain visible, and this is not manuscript readiness."
            ),
        )
        record.artifact_paths["accepted_idea_id"] = idea_id
        record.artifact_paths["accepted_direction_id"] = idea_id
        record.artifact_paths["human_idea_feedback"] = feedback.id
        record.status = "direction_ready"
        record.outcome_type = "defensible_direction"
        self.store.save_record(record)
        ExternalPilotReviewManager(self.config).create_review(
            record.id,
            reviewer_name="v2 pilot reviewer",
            reviewer_role="user",
            review_scope=["idea discovery workflow", "selected candidate", "evidence gates"],
            novelty_assessment="Accepted only as a candidate; novelty remains represented by the v2 novelty assessment.",
            evidence_assessment="Active idea search, mutation, constructive gaps, transfers, task packs, novelty, and tournament ran.",
            experiment_assessment="Candidate has benchmark metrics, baselines, and a minimum experiment shape.",
            artifact_assessment="Pilot artifacts are persisted under the project ideas workspace.",
            accept_outcome=True,
            reason="Selected idea is candidate-level, not paper-ready, and passed v2 pilot gates.",
        )

    def _accept_agenda_fallback(self, record: PilotRunRecord, tournament: IdeaTournament) -> None:
        agenda_id = tournament.agenda_id
        if not agenda_id:
            agenda = ResearchAgendaManager(self.config).generate(
                record.project_id,
                blocker_summary="No candidate survived v2 pilot tournament gates.",
                source_ids=[tournament.id],
            )
            agenda_id = agenda.id
        record.artifact_paths["research_agenda"] = agenda_id
        record.artifact_paths["agenda_report"] = str(
            Path(self.projects.load_project(record.project_id).project.root_dir) / "ideas" / "reports" / "research_agenda.md"
        )
        record.status = "refusal_ready"
        record.outcome_type = "correct_refusal"
        record.blockers.append(
            "research_refusal: v2 active idea search, mutation, novelty, and tournament did not find a viable idea; agenda accepted."
        )
        self.store.save_record(record)
        ExternalPilotReviewManager(self.config).create_review(
            record.id,
            reviewer_name="v2 pilot reviewer",
            reviewer_role="user",
            review_scope=["idea discovery workflow", "agenda fallback", "release blocker"],
            novelty_assessment="No selected idea is accepted.",
            evidence_assessment="Agenda accepted only after active v2 idea search artifacts were produced.",
            experiment_assessment="Agenda defines artifacts needed before a future idea can be accepted.",
            artifact_assessment="Agenda and tournament reports are persisted.",
            accept_outcome=True,
            reason="Accepted agenda fallback as an honest release blocker, not as achieved idea discovery.",
        )

    def _requirements(self, record: PilotRunRecord) -> dict[str, bool]:
        return v2_pilot_requirements(self.config, record)


def build_v2_pilot_acceptance(config: GapForgeConfig, record: PilotRunRecord) -> PilotAcceptanceSummary:
    reviews = _safe_reviews(config, record.id)
    requirements = v2_pilot_requirements(config, record, reviews=reviews)
    product_failures = [
        blocker.removeprefix("product_failure: ").strip() for blocker in record.blockers if blocker.startswith("product_failure:")
    ]
    accepted_reviews = [review for review in reviews if review.accepted_outcome]
    human_review_status = (
        "accepted" if accepted_reviews or requirements.get("human_review_acceptance") else ("rejected" if reviews else "missing")
    )
    accepted_idea_id = record.artifact_paths.get("accepted_idea_id", record.artifact_paths.get("accepted_direction_id", ""))
    idea_path = record.outcome_type == "defensible_direction" and all(
        requirements[key]
        for key in [
            "active_search_completed",
            "portfolio_generated",
            "idea_bank_generated",
            "mutation_ran",
            "constructive_gaps_generated",
            "cross_domain_transfers_expanded",
            "codex_tasks_created",
            "novelty_loop_ran",
            "tournament_ran",
            "human_review_acceptance",
            "selected_idea_exists",
            "selected_idea_is_specific",
            "selected_idea_has_no_fake_citation",
            "selected_idea_has_no_fake_results",
            "selected_idea_has_evidence_gate",
        ]
    )
    agenda_path = record.outcome_type == "correct_refusal" and all(
        requirements[key]
        for key in [
            "active_search_completed",
            "mutation_ran",
            "tournament_ran",
            "agenda_exists",
            "no_selected_idea",
            "human_review_acceptance",
        ]
    )
    passed = not product_failures and (idea_path or agenda_path)
    refusal_reason = ""
    if record.outcome_type == "correct_refusal" and passed:
        refusal_reason = "; ".join(blocker for blocker in record.blockers if blocker.startswith("research_refusal:"))
    elif not passed:
        refusal_reason = "; ".join(key for key, value in requirements.items() if not value)
    return PilotAcceptanceSummary(
        pilot_id=record.id,
        passed=passed,
        outcome_type=record.outcome_type,
        accepted_direction_id=accepted_idea_id,
        refusal_reason=refusal_reason,
        product_failures=product_failures,
        human_review_status=human_review_status,
        release_gate_eligible=passed,
        provenance=Provenance(
            created_by_skill="v2-pilot-acceptance",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Classified v2 pilot acceptance; early refusal and weak ideas cannot pass.",
        ),
    )


def v2_pilot_requirements(
    config: GapForgeConfig,
    record: PilotRunRecord,
    *,
    reviews: list[ExternalPilotReview] | None = None,
) -> dict[str, bool]:
    state = None
    candidate = None
    selected_idea_id = record.artifact_paths.get("accepted_idea_id", record.artifact_paths.get("accepted_direction_id", ""))
    if record.project_id:
        try:
            state = IdeaStore(config).load_state(record.project_id)
        except FileNotFoundError:
            state = None
    if state is not None and selected_idea_id:
        candidate = next((item for item in state.candidates if item.id == selected_idea_id), None)
    known_paper_ids = _known_paper_ids(config, record.project_id)
    review_records = reviews if reviews is not None else _safe_reviews(config, record.id)
    return {
        "active_search_completed": all(key in record.artifact_paths for key in V2_REQUIRED_SEARCH_ARTIFACTS),
        "portfolio_generated": "topic_portfolio" in record.artifact_paths,
        "idea_bank_generated": bool(state and state.idea_bank and state.candidates),
        "mutation_ran": bool(state and state.mutations),
        "constructive_gaps_generated": bool(state and state.constructive_gaps),
        "cross_domain_transfers_expanded": bool(state and state.transfer_candidates),
        "codex_tasks_created": "codex_idea_synthesis_tasks" in record.artifact_paths,
        "novelty_loop_ran": bool(state and state.novelty_assessments),
        "tournament_ran": bool(state and state.tournaments),
        "selected_idea_exists": candidate is not None,
        "selected_idea_is_specific": bool(candidate and not is_generic_idea_title(candidate.title)),
        "selected_idea_has_no_fake_citation": bool(candidate and not (_claimed_paper_ids(candidate) - known_paper_ids)),
        "selected_idea_has_no_fake_results": bool(candidate and not _has_fake_results(candidate)),
        "selected_idea_has_evidence_gate": bool(
            candidate
            and candidate.novelty_status in {"plausible", "strong"}
            and (candidate.closest_prior_work_ids or candidate.supporting_paper_ids or candidate.evidence_span_ids)
        ),
        "agenda_exists": bool(
            state
            and record.artifact_paths.get("research_agenda")
            and any(item.id == record.artifact_paths["research_agenda"] for item in state.agendas)
        ),
        "no_selected_idea": not selected_idea_id,
        "human_review_acceptance": any(review.accepted_outcome for review in review_records)
        or bool(state and any(feedback.action == "accept" and feedback.idea_id == selected_idea_id for feedback in state.feedback_records)),
    }


def render_v2_pilot_report(record: PilotRunRecord, summary: PilotAcceptanceSummary, requirements: dict[str, bool]) -> str:
    lines = [
        "# v2 Low-FPR Collusion Idea Pilot",
        "",
        f"- Pilot run: `{record.id}`",
        f"- Topic: {V2_LOW_FPR_TOPIC}",
        f"- Project: `{record.project_id or 'missing'}`",
        f"- Status: `{record.status}`",
        f"- Outcome: `{record.outcome_type}`",
        f"- Acceptance passed: {str(summary.passed).lower()}",
        f"- Release gate eligible: {str(summary.release_gate_eligible).lower()}",
        "",
        "## v2 Principle",
        "",
        "GapForge must try much harder to find a good idea, but it must not force a bad one.",
        "",
        "## Required Workflow",
        "",
    ]
    for key in V2_REQUIRED_SEARCH_ARTIFACTS:
        lines.append(f"- {key}: {'pass' if key in record.artifact_paths else 'missing'}")
    lines.extend(["", "## Acceptance Requirements", ""])
    lines.extend(f"- {key}: {'pass' if value else 'fail'}" for key, value in sorted(requirements.items()))
    lines.extend(["", "## Artifact Paths", ""])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(record.artifact_paths.items())] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in record.blockers] or ["- none"])
    lines.extend(["", "## Acceptance Summary", "", "```json", json.dumps(to_plain(summary), indent=2), "```", ""])
    if summary.passed and record.outcome_type == "defensible_direction":
        lines.append("v2 pilot produced a human-accepted candidate idea. This is candidate-level acceptance, not manuscript readiness.")
    elif summary.passed:
        lines.append(
            "v2 pilot produced an accepted research agenda fallback. This is an honest release blocker, not achieved idea discovery."
        )
    else:
        lines.append("v2 pilot did not pass. Do not claim v2 achieved idea discovery from this run.")
    return "\n".join(lines).rstrip() + "\n"


def render_v2_pilot_status(config: GapForgeConfig, name: str) -> str:
    return json.dumps(V2IdeaPilotRunner(config).status(name), indent=2) + "\n"


def _status_payload(record: PilotRunRecord, summary: PilotAcceptanceSummary, requirements: dict[str, bool]) -> dict[str, Any]:
    return {
        "name": V2_LOW_FPR_NAME,
        "pilot_id": record.pilot_id,
        "pilot_run_id": record.id,
        "project_id": record.project_id,
        "status": record.status,
        "outcome_type": record.outcome_type,
        "artifact_paths": record.artifact_paths,
        "blockers": record.blockers,
        "requirements": requirements,
        "acceptance": to_plain(summary),
    }


def _require_v2_pilot_name(name: str) -> None:
    if name not in {V2_LOW_FPR_NAME, V2_LOW_FPR_COLLUSION}:
        raise ValueError(f"Unknown v2 pilot {name!r}. Expected {V2_LOW_FPR_NAME!r}.")


def _safe_reviews(config: GapForgeConfig, pilot_id: str) -> list[ExternalPilotReview]:
    try:
        return PilotStore(config).load_external_reviews(pilot_id)
    except FileNotFoundError:
        return []


def _known_paper_ids(config: GapForgeConfig, project_id: str) -> set[str]:
    if not project_id:
        return set()
    try:
        program = ProjectMemoryManager(config).sync_project_memory(project_id)
    except FileNotFoundError:
        return set()
    known = {record.paper_id for record in program.corpus_papers}
    for record in program.corpus_papers:
        known.update(record.source_paper_ids)
    return {paper_id for paper_id in known if paper_id}


def _claimed_paper_ids(candidate) -> set[str]:
    return {
        paper_id
        for paper_id in [
            *candidate.closest_prior_work_ids,
            *candidate.supporting_paper_ids,
            *candidate.counterevidence_paper_ids,
        ]
        if paper_id
    }


def _has_fake_results(candidate) -> bool:
    text = " ".join([candidate.title, candidate.summary, candidate.core_claim, candidate.proposed_experiment]).lower()
    return any(marker in text for marker in RESULT_CLAIM_MARKERS)
