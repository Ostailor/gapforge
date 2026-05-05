"""Research run orchestration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from gapforge.config import GapForgeConfig
from gapforge.models import (
    OrchestratorPlan,
    OrchestratorResult,
    OrchestratorStep,
    Paper,
    ResearchRunState,
    RunLogEntry,
)
from gapforge.reporting import write_final_report
from gapforge.skill_registry import SkillRegistry, default_sources
from gapforge.sources.ranking import rank_papers
from gapforge.state import ResearchStateManager, utc_now_iso


class Orchestrator:
    def __init__(
        self,
        config: GapForgeConfig | None = None,
        registry: SkillRegistry | None = None,
        sources: list[object] | None = None,
    ) -> None:
        self.config = config or GapForgeConfig.from_cwd()
        self.state_store = ResearchStateManager(self.config)
        self.registry = registry or SkillRegistry(self.config)
        self.sources = sources if sources is not None else default_sources(self.config)

    def init_topic(self, topic: str) -> ResearchRunState:
        return self.state_store.create_run(topic)

    def search(
        self,
        topic: str,
        *,
        max_results: int = 20,
        sources: list[str] | None = None,
        newest_first: bool = True,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> ResearchRunState:
        state = self._current_or_new_run(topic)
        papers, failures = self._search_sources(
            query=topic,
            max_results=max_results,
            source_names=sources,
            newest_first=newest_first,
            date_from=date_from,
            date_to=date_to,
        )
        for failure in failures:
            self._log(state, "warning", "search", failure)
        state.papers = self._merge_ranked_papers(state, papers, topic, max_results)
        self.state_store.save_run(state)
        return state

    def map_topic(self, topic: str | None = None, *, run_id: str | None = None) -> ResearchRunState:
        if run_id is not None:
            state = self.state_store.load_run(run_id)
        elif topic is not None:
            state = self.search(topic)
        else:
            raise ValueError("map_topic requires topic or run_id")
        self.registry.get("literature-cartographer").run(state)
        for skill_name in ["paper-triage", "deep-reading", "gap-mining"]:
            self.registry.get(skill_name).run(state)
        self.state_store.save_run(state)
        return state

    def triage(self, topic: str | None = None, *, run_id: str | None = None, max_tier1: int = 20) -> ResearchRunState:
        if run_id is not None:
            state = self.state_store.load_run(run_id)
        elif topic is not None:
            state = self.search(topic)
        else:
            raise ValueError("triage requires topic or run_id")
        triage_skill = cast(Any, self.registry.get("paper-triage"))
        triage_skill.max_tier1 = max_tier1
        triage_skill.run(state)
        self.state_store.save_run(state)
        return state

    def read(
        self,
        *,
        run_id: str | None = None,
        tier: int | None = None,
        paper_id: str | None = None,
    ) -> ResearchRunState:
        state = self.state_store.load_run(run_id) if run_id is not None else self.state_store.load_latest()
        if state is None:
            raise ValueError("read requires an existing run")
        selected_papers = state.papers
        if paper_id is not None:
            selected_papers = [paper for paper in state.papers if paper.id == paper_id]
            if not selected_papers:
                raise ValueError(f"No paper found for paper id {paper_id}")
        elif tier is not None and state.paper_triage is not None:
            target_tier = f"Tier {tier}"
            allowed_ids = {decision.paper_id for decision in state.paper_triage.decisions if decision.tier == target_tier}
            selected_papers = [paper for paper in state.papers if paper.id in allowed_ids]
        cast(Any, self.registry.get("deep-reading")).read_papers(state, selected_papers)
        self.state_store.save_run(state)
        return state

    def mine_gaps(self, *, run_id: str) -> ResearchRunState:
        state = self.state_store.load_run(run_id)
        self.registry.get("gap-mining").run(state)
        self.state_store.save_run(state)
        return state

    def analogies(self, *, run_id: str) -> ResearchRunState:
        state = self.state_store.load_run(run_id)
        self.registry.get("cross-domain-analogy").run(state)
        self.state_store.save_run(state)
        return state

    def novelty_check(self, *, run_id: str | None = None, gap_id: str | None = None) -> ResearchRunState:
        state = self.state_store.load_run(run_id) if run_id is not None else self.state_store.load_latest()
        if state is None:
            raise ValueError("novelty_check requires an existing run")
        cast(Any, self.registry.get("novelty-gate")).assess(state, gap_id=gap_id)
        self.state_store.save_run(state)
        return state

    def design_experiments(
        self,
        *,
        run_id: str | None = None,
        gap_id: str | None = None,
        allow_rejected: bool = False,
    ) -> ResearchRunState:
        state = self.state_store.load_run(run_id) if run_id is not None else self.state_store.load_latest()
        if state is None:
            raise ValueError("design_experiments requires an existing run")
        cast(Any, self.registry.get("experiment-designer")).design(state, gap_id=gap_id, allow_rejected=allow_rejected)
        self.state_store.save_run(state)
        return state

    def review(self, *, run_id: str | None = None, experiment_id: str | None = None) -> ResearchRunState:
        state = self.state_store.load_run(run_id) if run_id is not None else self.state_store.load_latest()
        if state is None:
            raise ValueError("review requires an existing run")
        cast(Any, self.registry.get("reviewer-simulation")).review(state, experiment_id=experiment_id)
        self.state_store.save_run(state)
        return state

    def run(
        self,
        topic: str,
        *,
        max_papers: int = 50,
        iterations: int = 1,
        sources: list[str] | None = None,
        dry_run: bool = False,
        stop_after: str | None = None,
    ) -> ResearchRunState:
        state = self.init_topic(topic)
        state.orchestrator_plan = self._build_plan(
            state,
            max_papers=max_papers,
            iterations=iterations,
            sources=sources,
            dry_run=dry_run,
        )
        state.orchestrator_result = OrchestratorResult(run_id=state.run_id, status="planned")
        self._log(state, "info", "initialize-topic", f"Initialized run for topic: {topic}")
        self.state_store.save_run(state)
        if dry_run:
            state.orchestrator_result = self._result_from_plan(state, status="planned", message="Dry run: plan created only.")
            self.state_store.save_run(state)
            return state
        return self._execute_plan(state, stop_after=stop_after)

    def resume(self, *, run_id: str, stop_after: str | None = None) -> ResearchRunState:
        state = self.state_store.load_run(run_id)
        if state.orchestrator_plan is None:
            state.orchestrator_plan = self._build_plan(
                state,
                max_papers=int(state.config.get("max_papers", 50)),
                iterations=int(state.config.get("max_iterations", 1)),
                sources=state.config.get("sources", []),
                dry_run=False,
            )
            self._mark_steps_from_state(state)
            self._log(state, "info", "resume", "Created missing orchestration plan from current state.")
            self.state_store.save_run(state)
        return self._execute_plan(state, stop_after=stop_after)

    def status(self, *, run_id: str) -> OrchestratorResult:
        state = self.state_store.load_run(run_id)
        if state.orchestrator_result is not None:
            return state.orchestrator_result
        if state.orchestrator_plan is None:
            return OrchestratorResult(run_id=run_id, status="unknown", message="No orchestrator plan found.")
        return self._result_from_plan(state, status="running", message="Plan exists without a saved result.")

    def _execute_plan(self, state: ResearchRunState, *, stop_after: str | None = None) -> ResearchRunState:
        if state.orchestrator_plan is None:
            raise ValueError("Cannot execute without an orchestrator plan")
        state.orchestrator_result = self._result_from_plan(state, status="running", message="Run in progress.")
        self.state_store.save_run(state)

        handlers: dict[str, Callable[[ResearchRunState, OrchestratorStep], None]] = {
            "initialize-topic": self._step_initialize,
            "search-papers": self._step_search_papers,
            "map-literature": self._step_map_literature,
            "triage-papers": self._step_triage_papers,
            "deep-read": self._step_deep_read,
            "mine-gaps": self._step_mine_gaps,
            "cross-domain-analogies": self._step_cross_domain_analogies,
            "analogy-search": self._step_analogy_search,
            "refresh-after-new-papers": self._step_refresh_after_new_papers,
            "novelty-gate": self._step_novelty_gate,
            "design-experiments": self._step_design_experiments,
            "reviewer-simulation": self._step_reviewer_simulation,
            "final-report": self._step_final_report,
        }

        for step in state.orchestrator_plan.steps:
            if step.status == "complete" or step.status == "skipped":
                continue
            if step.status == "running":
                step.status = "pending"
                step.error = ""
            if step.status == "failed":
                step.status = "pending"
                step.error = ""
            handler = handlers[step.name]
            self._start_step(state, step)
            try:
                handler(state, step)
                if step.status == "running":
                    self._complete_step(state, step)
            except Exception as exc:
                self._fail_step(state, step, exc)
            self.state_store.save_run(state)
            if stop_after is not None and step.name == stop_after:
                state.orchestrator_result = self._result_from_plan(
                    state,
                    status="interrupted",
                    message=f"Stopped after {stop_after}. Resume can continue pending steps.",
                )
                self._log(state, "warning", step.id, f"Execution intentionally stopped after {stop_after}.")
                self.state_store.save_run(state)
                return state

        status = "complete" if not any(step.status == "failed" for step in state.orchestrator_plan.steps) else "failed"
        state.orchestrator_result = self._result_from_plan(state, status=status, message=f"Run {status}.")
        self.state_store.save_run(state)
        return state

    def _build_plan(
        self,
        state: ResearchRunState,
        *,
        max_papers: int,
        iterations: int,
        sources: list[str] | None,
        dry_run: bool,
    ) -> OrchestratorPlan:
        bounded_iterations = max(1, min(iterations, 10))
        steps = [OrchestratorStep(id="initialize-topic", name="initialize-topic", iteration=0)]
        for iteration in range(1, bounded_iterations + 1):
            for name in [
                "search-papers",
                "map-literature",
                "triage-papers",
                "deep-read",
                "mine-gaps",
                "cross-domain-analogies",
                "analogy-search",
                "refresh-after-new-papers",
                "novelty-gate",
                "design-experiments",
                "reviewer-simulation",
            ]:
                steps.append(OrchestratorStep(id=f"iter-{iteration}-{name}", name=name, iteration=iteration))
        steps.append(OrchestratorStep(id="final-report", name="final-report", iteration=bounded_iterations))
        now = utc_now_iso()
        state.config["max_papers"] = max_papers
        state.config["max_iterations"] = bounded_iterations
        state.config["sources"] = list(sources or [])
        state.config["dry_run"] = dry_run
        return OrchestratorPlan(
            run_id=state.run_id,
            topic=state.topic.text,
            max_papers=max_papers,
            max_iterations=bounded_iterations,
            sources=list(sources or []),
            dry_run=dry_run,
            steps=steps,
            created_at=now,
            updated_at=now,
        )

    def _mark_steps_from_state(self, state: ResearchRunState) -> None:
        if state.orchestrator_plan is None:
            return
        completed = set(state.completed_skills)
        for step in state.orchestrator_plan.steps:
            if step.name == "initialize-topic":
                step.status = "complete"
            elif step.name == "search-papers" and state.papers:
                step.status = "complete"
            elif step.name == "map-literature" and state.field_map is not None:
                step.status = "complete"
            elif step.name == "triage-papers" and state.paper_triage is not None:
                step.status = "complete"
            elif step.name == "deep-read" and state.paper_notes:
                step.status = "complete"
            elif step.name == "mine-gaps" and state.gaps:
                step.status = "complete"
            elif step.name == "cross-domain-analogies" and state.cross_domain_analogies:
                step.status = "complete"
            elif step.name == "novelty-gate" and state.novelty_assessments:
                step.status = "complete"
            elif step.name == "design-experiments" and state.experiments:
                step.status = "complete"
            elif step.name == "reviewer-simulation" and state.reviewer_objections:
                step.status = "complete"
            elif step.name in completed:
                step.status = "complete"

    def _step_initialize(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        step.details["topic"] = state.topic.text
        self._complete_step(state, step)

    def _step_search_papers(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        plan = state.orchestrator_plan
        assert plan is not None
        papers, failures = self._search_sources(
            query=state.topic.text,
            max_results=plan.max_papers,
            source_names=plan.sources,
            newest_first=True,
        )
        for failure in failures:
            self._log(state, "warning", step.id, failure)
        state.papers = self._merge_ranked_papers(state, papers, state.topic.text, plan.max_papers)
        step.details.update({"paper_count": len(state.papers), "source_failures": failures})
        self._complete_step(state, step)

    def _step_map_literature(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("literature-cartographer").run(state)
        step.details["cluster_count"] = len(state.field_map.clusters) if state.field_map else 0
        self._complete_step(state, step)

    def _step_triage_papers(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("paper-triage").run(state)
        step.details["decision_count"] = len(state.paper_triage.decisions) if state.paper_triage else 0
        self._complete_step(state, step)

    def _step_deep_read(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("deep-reading").run(state)
        step.details["note_count"] = len(state.paper_notes)
        self._complete_step(state, step)

    def _step_mine_gaps(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("gap-mining").run(state)
        step.details["gap_count"] = len(state.gaps)
        self._complete_step(state, step)

    def _step_cross_domain_analogies(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("cross-domain-analogy").run(state)
        step.details["analogy_count"] = len(state.cross_domain_analogies)
        self._complete_step(state, step)

    def _step_analogy_search(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        plan = state.orchestrator_plan
        assert plan is not None
        before = len(state.papers)
        failures: list[str] = []
        all_new: list[Paper] = []
        for query in _analogy_queries(state)[: max(1, plan.max_iterations) * 6]:
            found, query_failures = self._search_sources(
                query=query,
                max_results=max(1, min(6, plan.max_papers // 4)),
                source_names=plan.sources,
                newest_first=True,
            )
            all_new.extend(found)
            failures.extend(query_failures)
        for failure in failures[:10]:
            self._log(state, "warning", step.id, failure)
        state.papers = self._merge_ranked_papers(state, all_new, state.topic.text, plan.max_papers)
        new_count = max(0, len(state.papers) - before)
        state.config["_new_papers_from_analogies"] = new_count
        step.details.update({"new_papers": new_count, "paper_count": len(state.papers), "source_failures": failures})
        self._complete_step(state, step)

    def _step_refresh_after_new_papers(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        if int(state.config.get("_new_papers_from_analogies", 0)) <= 0:
            self._skip_step(state, step, "No new papers from analogy searches.")
            return
        self.registry.get("literature-cartographer").run(state)
        self.registry.get("paper-triage").run(state)
        self.registry.get("deep-reading").run(state)
        self.registry.get("gap-mining").run(state)
        step.details.update(
            {
                "paper_count": len(state.papers),
                "note_count": len(state.paper_notes),
                "gap_count": len(state.gaps),
            }
        )
        self._complete_step(state, step)

    def _step_novelty_gate(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("novelty-gate").run(state)
        step.details["assessment_count"] = len(state.novelty_assessments)
        self._complete_step(state, step)

    def _step_design_experiments(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("experiment-designer").run(state)
        step.details["experiment_count"] = len(state.experiments)
        self._complete_step(state, step)

    def _step_reviewer_simulation(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        self.registry.get("reviewer-simulation").run(state)
        step.details["objection_count"] = len(state.reviewer_objections)
        self._complete_step(state, step)

    def _step_final_report(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        final_report = write_final_report(state)
        step.details["report_path"] = str(final_report)
        self._complete_step(state, step)

    def _search_sources(
        self,
        *,
        query: str,
        max_results: int,
        source_names: list[str] | None,
        newest_first: bool,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[list[Paper], list[str]]:
        papers: list[Paper] = []
        failures: list[str] = []
        selected_sources = _select_sources(self.sources, source_names)
        if not selected_sources:
            available = ", ".join(_source_name(source) for source in self.sources) or "none"
            wanted = ", ".join(source_names or []) or "none"
            return [], [f"No sources matched {wanted!r}. Available sources: {available}."]
        per_source = max(1, min(max_results, max_results // max(1, len(selected_sources)) or 1))
        for source in selected_sources:
            source_name = _source_name(source)
            try:
                papers.extend(
                    source.search(
                        query,
                        max_results=per_source,
                        sort="newest" if newest_first else "oldest",
                        date_from=date_from,
                        date_to=date_to,
                    )
                )
            except Exception as exc:
                failures.append(f"{source_name} search failed for {query!r}: {exc}")
        return papers, failures

    def _merge_ranked_papers(self, state: ResearchRunState, new_papers: list[Paper], query: str, max_papers: int) -> list[Paper]:
        per_source_limit = max(1, max_papers // max(1, len(_select_sources(self.sources, None))))
        return rank_papers(query, state.papers + new_papers, newest_first=True, per_source_limit=per_source_limit)[:max_papers]

    def _start_step(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        step.status = "running"
        step.started_at = utc_now_iso()
        step.error = ""
        self._touch_plan(state)
        self._log(state, "info", step.id, f"Starting {step.name}.")
        self.state_store.save_run(state)

    def _complete_step(self, state: ResearchRunState, step: OrchestratorStep) -> None:
        step.status = "complete"
        step.completed_at = utc_now_iso()
        self._touch_plan(state)
        self._log(state, "info", step.id, f"Completed {step.name}.", step.details)
        state.orchestrator_result = self._result_from_plan(state, status="running", message="Run in progress.")

    def _skip_step(self, state: ResearchRunState, step: OrchestratorStep, reason: str) -> None:
        step.status = "skipped"
        step.completed_at = utc_now_iso()
        step.details["reason"] = reason
        self._touch_plan(state)
        self._log(state, "info", step.id, f"Skipped {step.name}: {reason}", step.details)

    def _fail_step(self, state: ResearchRunState, step: OrchestratorStep, exc: Exception) -> None:
        step.status = "failed"
        step.completed_at = utc_now_iso()
        step.error = str(exc)
        self._touch_plan(state)
        self._log(state, "error", step.id, f"Failed {step.name}: {exc}", {"error_type": type(exc).__name__})
        state.orchestrator_result = self._result_from_plan(state, status="running", message="Run continued after a failed step.")

    def _result_from_plan(self, state: ResearchRunState, *, status: str, message: str) -> OrchestratorResult:
        plan = state.orchestrator_plan
        if plan is None:
            return OrchestratorResult(run_id=state.run_id, status=status, message=message)
        return OrchestratorResult(
            run_id=state.run_id,
            status=status,
            completed_steps=[step.id for step in plan.steps if step.status == "complete"],
            failed_steps=[step.id for step in plan.steps if step.status == "failed"],
            skipped_steps=[step.id for step in plan.steps if step.status == "skipped"],
            artifacts=_artifacts(state),
            message=message,
        )

    def _touch_plan(self, state: ResearchRunState) -> None:
        if state.orchestrator_plan is not None:
            state.orchestrator_plan.updated_at = utc_now_iso()

    def _log(
        self,
        state: ResearchRunState,
        level: str,
        step_id: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        state.run_log.append(
            RunLogEntry(
                timestamp=utc_now_iso(),
                level=level,
                step_id=step_id,
                message=message,
                details=dict(details or {}),
            )
        )

    def _current_or_new_run(self, topic: str) -> ResearchRunState:
        current = self.state_store.load_latest()
        if current is not None and current.topic.text == topic:
            return current
        return self.init_topic(topic)


def _select_sources(source_objects, names: list[str] | None):
    if not names:
        return source_objects
    wanted = {name.strip().lower().replace("_", "-") for name in names if name.strip()}
    return [
        source
        for source in source_objects
        if _source_name(source).lower().replace(" ", "-") in wanted or _source_name(source).lower().replace(" ", "") in wanted
    ]


def _source_name(source) -> str:
    return str(getattr(source, "name", source.__class__.__name__))


def _analogy_queries(state: ResearchRunState) -> list[str]:
    queries: list[str] = []
    for analogy in state.cross_domain_analogies:
        queries.extend(analogy.papers_or_sources_to_search)
    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        key = query.lower()
        if query and key not in seen:
            deduped.append(query)
            seen.add(key)
    return deduped


def _artifacts(state: ResearchRunState) -> list[str]:
    run_dir = Path(state.run_dir)
    names = [
        "field_map.md",
        "paper_triage.md",
        "paper_notes.md",
        "gaps.md",
        "cross_domain_analogies.md",
        "novelty_gate.md",
        "experiments.md",
        "reviewer_simulation.md",
        "revised_experiment_recommendations.md",
        "run_report.md",
        "final_report.md",
    ]
    return [str(run_dir / name) for name in names if (run_dir / name).exists()]
