"""Resumable active research loop for GapForge v0.3."""

from __future__ import annotations

import os
from typing import Any

from gapforge.citations import CitationGraphBuilder, RelatedWorkExpander
from gapforge.fulltext.structure import FullTextStructureParser
from gapforge.models import ActiveLoopDecision, ActiveLoopState, Paper, ResearchBudget, ResearchRunState
from gapforge.orchestration.decisions import ActiveLoopDecider
from gapforge.reporting import write_final_report
from gapforge.review.audit import is_rejected
from gapforge.review.queue import build_run_review_queue
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.ranking import rank_papers
from gapforge.sources.stopping import refresh_stopping_assessment


class ActiveResearchLoop:
    """Execute one-decision-at-a-time research loops with auditable stopping."""

    def __init__(self, orchestrator: Any, decider: ActiveLoopDecider | None = None) -> None:
        self.orchestrator = orchestrator
        self.decider = decider or ActiveLoopDecider()

    def start(
        self,
        topic: str,
        *,
        budget: ResearchBudget,
        project_id: str = "",
        source_policy_profile: str = "",
    ) -> ResearchRunState:
        state = self.orchestrator.init_topic(topic)
        state.config["active_loop"] = True
        state.config["v3_active_loop"] = True
        if project_id:
            state.config["project_id"] = project_id
        if source_policy_profile:
            state.config["source_policy_profile"] = source_policy_profile
        state.active_loop = ActiveLoopState(budget=budget, status="running")
        self._refresh(state)
        self.orchestrator.state_store.save_run(state)
        return self.resume_state(state)

    def resume(self, run_id: str) -> ResearchRunState:
        state = self.orchestrator.state_store.load_run(run_id)
        if state.active_loop is None:
            state.active_loop = ActiveLoopState(status="running")
        if state.active_loop.status in {"complete", "budget_exhausted"}:
            return state
        state.active_loop.status = "running"
        return self.resume_state(state)

    def resume_state(self, state: ResearchRunState) -> ResearchRunState:
        if state.active_loop is None:
            state.active_loop = ActiveLoopState(status="running")
        loop = state.active_loop
        while True:
            self._refresh(state)
            if state.coverage_stopping_assessment is not None:
                loop.stopping_assessments.append(state.coverage_stopping_assessment)
            decision = self.decider.decide(state, loop)
            loop.decisions.append(decision)
            self._execute_decision(state, decision)
            loop.current_iteration = decision.iteration
            self._refresh(state)
            self.orchestrator.state_store.save_run(state)
            if decision.decision_type == "stop":
                loop.status = _stop_status(decision)
                write_final_report(state, strict=True)
                self.orchestrator.state_store.save_run(state)
                return state
            if decision.decision_type == "request_human_review":
                loop.status = "waiting_for_human_review"
                write_final_report(state, strict=True)
                self.orchestrator.state_store.save_run(state)
                return state

    def _execute_decision(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        decision.status = "running"
        try:
            if decision.decision_type == "search_more":
                self._search_more(state, decision)
            elif decision.decision_type == "parse_more":
                self._parse_more(state, decision)
            elif decision.decision_type == "read_more":
                self._read_more(state, decision)
            elif decision.decision_type == "expand_citations":
                self._expand_citations(state, decision)
            elif decision.decision_type == "check_novelty":
                self._check_novelty(state, decision)
            elif decision.decision_type == "design_experiment":
                self._design_experiment(state, decision)
            elif decision.decision_type == "request_human_review":
                self._request_human_review(state, decision)
            elif decision.decision_type == "stop":
                decision.status = "complete"
                return
            else:
                raise ValueError(f"Unsupported active-loop decision: {decision.decision_type}")
        except Exception as exc:
            decision.status = "failed"
            decision.evidence.append(f"error={type(exc).__name__}: {exc}")
            raise
        decision.status = "complete"

    def _search_more(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        budget = state.active_loop.budget if state.active_loop else ResearchBudget()
        assessment = state.coverage_stopping_assessment or refresh_stopping_assessment(state)
        remaining_queries = max(0, budget.max_queries - len(state.search_queries))
        queries = (assessment.recommended_queries or [state.topic.text])[: max(1, min(2, remaining_queries))]
        before = len(state.papers)
        found_all: list[Paper] = []
        failures: list[str] = []
        for query in queries:
            found, query_failures = self.orchestrator._search_sources(
                state=state,
                query=query,
                max_results=max(1, min(8, budget.max_papers)),
                source_names=state.config.get("sources", []),
                newest_first=True,
                purpose="initial_topic" if not state.search_queries else "manual",
            )
            found_all.extend(found)
            failures.extend(query_failures)
        state.papers = self.orchestrator._merge_ranked_papers(state, found_all, state.topic.text, budget.max_papers)
        new_count = max(0, len(state.papers) - before)
        decision.evidence.extend([f"queries={len(queries)}", f"new_papers={new_count}", f"failures={len(failures)}"])

    def _parse_more(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        budget = state.active_loop.budget if state.active_loop else ResearchBudget()
        before_sections = len(state.paper_sections)
        artifacts = []
        if not _network_disabled():
            artifacts = self.orchestrator.pdf_downloader.download_for_state(
                state,
                max_papers=budget.max_full_text_papers,
                skip_existing=True,
            )
        else:
            decision.evidence.append("network_disabled=true")
        if any(artifact.artifact_type == "pdf" and artifact.status == "available" for artifact in state.paper_artifacts):
            self.orchestrator.fulltext_parser.parse_for_state(state)
            FullTextStructureParser().parse_all(state)
        decision.evidence.extend(
            [
                f"downloaded_artifacts={len(artifacts)}",
                f"new_sections={max(0, len(state.paper_sections) - before_sections)}",
            ]
        )

    def _read_more(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        if state.papers and state.field_map is None:
            self.orchestrator.registry.get("literature-cartographer").run(state)
        if state.papers and state.paper_triage is None:
            self.orchestrator.registry.get("paper-triage").run(state)
        if state.papers:
            self.orchestrator.registry.get("deep-reading").run(state)
        if state.paper_notes:
            self.orchestrator.registry.get("gap-mining").run(state)
        decision.evidence.extend([f"notes={len(state.paper_notes)}", f"gaps={len(state.gaps)}"])

    def _expand_citations(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        budget = state.active_loop.budget if state.active_loop else ResearchBudget()
        before = len(state.papers)
        graph = CitationGraphBuilder().build(state)
        added: list[Paper] = []
        if not _network_disabled():
            added = RelatedWorkExpander(self.orchestrator.sources).expand(
                state,
                max_new_papers=max(0, min(budget.max_papers - len(state.papers), 10)),
            )
        else:
            decision.evidence.append("network_disabled=true")
        state.papers = rank_papers(state.topic.text, state.papers, newest_first=True)[: budget.max_papers]
        decision.evidence.extend(
            [
                f"citation_edges={len(graph.edges)}",
                f"unresolved_references={len(graph.unresolved_references)}",
                f"new_papers={max(0, len(state.papers) - before)}",
                f"added_candidates={len(added)}",
            ]
        )

    def _check_novelty(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        self.orchestrator.registry.get("novelty-gate").assess(state, deep=not _network_disabled())
        decision.evidence.extend([f"assessments={len(state.novelty_assessments)}", f"dossiers={len(state.novelty_dossiers)}"])

    def _design_experiment(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        before = len(state.experiments)
        self.orchestrator.registry.get("experiment-designer").run(state)
        self.orchestrator.registry.get("reviewer-simulation").run(state)
        rejected_gap_ids = {gap.id for gap in state.gaps if is_rejected(state, "gap", gap.id)}
        decision.evidence.extend(
            [
                f"new_experiments={max(0, len(state.experiments) - before)}",
                f"reviewer_objections={len(state.reviewer_objections)}",
                f"rejected_gaps_skipped={len(rejected_gap_ids)}",
            ]
        )

    def _request_human_review(self, state: ResearchRunState, decision: ActiveLoopDecision) -> None:
        state.config["_active_loop_human_review_requested"] = True
        decision.evidence.append("human_review_requested=true")

    def _refresh(self, state: ResearchRunState) -> None:
        warnings = [str(item) for item in state.config.get("_coverage_warnings", []) if str(item)]
        if _network_disabled():
            warnings.append("Network disabled; active loop is operating in offline-safe mode.")
        refresh_source_coverage(state, warnings)
        refresh_stopping_assessment(state)
        state.review_queue = build_run_review_queue(state, project_id=str(state.config.get("project_id", "")), existing=state.review_queue)


def _network_disabled() -> bool:
    return os.environ.get("GAPFORGE_DISABLE_NETWORK", "").strip().lower() in {"1", "true", "yes"}


def _stop_status(decision: ActiveLoopDecision) -> str:
    if "budget exhausted" in decision.reason.lower():
        return "budget_exhausted"
    return "complete"
