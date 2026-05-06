"""Agentic campaign controller for v0.4 research campaigns."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.budgets import campaign_budget_status
from gapforge.campaigns.decision_policy import CampaignAction, CampaignDecisionPolicy, build_campaign_assessment
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.recovery import mark_waiting_steps_running
from gapforge.campaigns.stop_conditions import campaign_stop_condition
from gapforge.campaigns.task_packs import CAMPAIGN_TASK_OUTPUTS, create_campaign_task_pack
from gapforge.config import GapForgeConfig
from gapforge.models import (
    CampaignDecision,
    CampaignStep,
    ExperimentProtocol,
    Provenance,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchRunState,
    SearchQueryRecord,
    to_plain,
)
from gapforge.novelty.recall_gate import assess_run_prior_work_recall
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval import build_project_index
from gapforge.search_strategy import execute_search_strategy, plan_search_strategy, save_strategy
from gapforge.skills.deep_reading import DeepReading
from gapforge.skills.gap_mining import GapMining
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.sources.canonical import canonicalize_run
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.live_diagnostics import (
    render_live_source_diagnostic_markdown,
    run_live_source_diagnostic,
    write_live_source_diagnostic,
)
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


class CampaignController:
    """Run one or more auditable campaign decisions."""

    def __init__(self, config: GapForgeConfig, policy: CampaignDecisionPolicy | None = None) -> None:
        self.config = config
        self.manager = CampaignManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.policy = policy or CampaignDecisionPolicy()

    def next_action(self, campaign_id: str, *, max_iterations: int | None = None, real_literature: bool = False) -> CampaignAction:
        state, program, runs = self._load_context(campaign_id)
        budget = campaign_budget_status(state, papers_seen=sum(len(run.papers) for run in runs), max_iterations_override=max_iterations)
        assessment = build_campaign_assessment(state, program, runs, budget_status=budget, real_literature=real_literature)
        return self.policy.decide(assessment)

    def run(
        self,
        campaign_id: str,
        *,
        mode: str | None = None,
        max_iterations: int | None = None,
        real_literature: bool = False,
    ) -> CampaignState:
        state = self.manager.load_campaign_state(campaign_id)
        if mode:
            state.campaign.mode = mode
        state.campaign.status = "running"
        mark_waiting_steps_running(state)
        self.manager.save_campaign_state(state)

        actions_this_call = 0
        while True:
            state, program, runs = self._load_context(campaign_id)
            budget = campaign_budget_status(
                state,
                papers_seen=sum(len(run.papers) for run in runs),
                max_iterations_override=max_iterations,
            )
            assessment = build_campaign_assessment(state, program, runs, budget_status=budget, real_literature=real_literature)
            action = self.policy.decide(assessment)
            decision = self._record_decision(state, action)
            step = self._record_step(state, action, decision)
            self.manager.save_campaign_state(state)

            self._execute_action(state, action, step)
            actions_this_call += 1
            self.manager.save_campaign_state(state)

            if action.terminal or state.campaign.status in {"paused", "complete", "failed", "accepted", "rejected"}:
                return state
            if max_iterations is not None and actions_this_call >= max_iterations:
                state.campaign.status = "paused"
                state.stop_conditions.append(
                    campaign_stop_condition(
                        campaign_id,
                        reason=f"Paused after requested controller iteration limit ({max_iterations}).",
                        evidence=[decision.id],
                    )
                )
                self.manager.save_campaign_state(state)
                return state

    def resume(self, campaign_id: str, *, mode: str | None = None, max_iterations: int | None = None) -> CampaignState:
        state = self.manager.resume_campaign(campaign_id)
        return self.run(state.campaign.id, mode=mode, max_iterations=max_iterations)

    def _execute_action(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        try:
            if action.decision_type == "source_health_check":
                self._execute_source_health_check(state, step)
            elif action.decision_type == "plan_search_strategy":
                self._execute_plan_search_strategy(state, step)
            elif action.decision_type == "execute_search_round":
                self._execute_search_round(state, step)
            elif action.decision_type == "canonicalize_papers":
                self._execute_canonicalize_papers(state, step)
            elif action.decision_type == "run_prior_work_recall_gate":
                self._execute_prior_work_recall_gate(state, step)
            elif action.decision_type == "gap_synthesis":
                self._execute_gap_synthesis(state, step)
            elif action.decision_type == "search_counterevidence":
                self._execute_search_counterevidence(state, step)
            elif action.decision_type == "download_or_parse_priority_papers":
                self._execute_parse_more(state, step)
            elif action.decision_type == "build_retrieval_index":
                self._execute_build_index(state, step)
            elif action.decision_type == "request_codex_synthesis":
                self._execute_request_codex_synthesis(state, action, step)
            elif action.decision_type == "stop_insufficient_live_coverage":
                self._execute_quality_stop(state, action, step, status="paused")
            elif action.decision_type == "reject_low_novelty_direction":
                self._execute_quality_stop(state, action, step, status="rejected")
            elif action.decision_type == "search_more":
                self._execute_search_more(state, step)
            elif action.decision_type == "build_index":
                self._execute_build_index(state, step)
            elif action.decision_type == "parse_more":
                self._execute_parse_more(state, step)
            elif action.decision_type in {"read_more", "gap_synthesis", "check_novelty", "reviewer_panel"}:
                self._execute_deterministic_placeholder(state, action, step)
            elif action.decision_type == "ask_codex":
                self._execute_codex_task(state, action, step)
            elif action.decision_type == "import_outputs":
                self._execute_import_outputs(state, action, step)
            elif action.decision_type == "request_human_review":
                self._execute_request_human_review(state, action, step)
            elif action.decision_type == "export_package":
                self._execute_export_package(state, action, step)
            elif action.decision_type == "stop":
                self._execute_stop(state, action, step)
            else:
                raise ValueError(f"Unsupported campaign controller action: {action.decision_type}")
        except Exception as exc:
            state.campaign.status = "failed"
            step.status = "failed"
            step.completed_at = utc_now_iso()
            step.blocking_issues.append(f"{type(exc).__name__}: {exc}")
            raise

    def _execute_search_more(self, state: CampaignState, step: CampaignStep) -> None:
        run = self._latest_or_new_run(state)
        run.search_queries.append(
            SearchQueryRecord(
                id=f"query-{len(run.search_queries) + 1:04d}",
                query=state.campaign.topic,
                source_names=[],
                purpose="campaign_controller",
                max_results=(state.budget.max_papers if state.budget else 50),
                executed_at=utc_now_iso(),
                result_paper_ids=[],
                failure_messages=(
                    ["GAPFORGE_DISABLE_NETWORK=1; campaign controller recorded a search request without live source calls."]
                    if _network_disabled()
                    else ["Campaign controller requested source search; use source connectors or Codex literature_scout to execute it."]
                ),
                provenance=Provenance(
                    created_by_skill="campaign-controller",
                    source_ids=[state.campaign.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Recorded an auditable campaign search request without inventing source results.",
                ),
            )
        )
        refresh_source_coverage(run, warnings=["Campaign source coverage remains incomplete until source searches return papers."])
        self.state_manager.save_run(run)
        self.project_manager.attach_run(state.campaign.project_id, run.run_id)
        if run.run_id not in state.campaign.run_ids:
            state.campaign.run_ids.append(run.run_id)
        step.run_id = run.run_id
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [str(Path(run.run_dir) / "source_coverage.json")]

    def _execute_source_health_check(self, state: CampaignState, step: CampaignStep) -> None:
        diagnostic = run_live_source_diagnostic(
            self.config,
            topic=state.campaign.topic,
            source_profile=state.campaign.source_profile or "generic",
        )
        json_path, md_path = write_live_source_diagnostic(self.config, diagnostic)
        campaign_dir = self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        campaign_json = campaign_dir / "live_source_diagnostic.json"
        campaign_md = campaign_dir / "live_source_diagnostic.md"
        campaign_json.write_text(json.dumps(to_plain(diagnostic), indent=2) + "\n", encoding="utf-8")
        campaign_md.write_text(render_live_source_diagnostic_markdown(diagnostic), encoding="utf-8")
        blockers = diagnostic.blocking_issues
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [json_path, md_path, str(campaign_json), str(campaign_md)]
        if blockers:
            step.blocking_issues = blockers
            return
        state.milestones.append(
            _milestone(state.campaign.id, "live_sources_ready", [json_path, md_path, str(campaign_md)], "Live source health passed.")
        )

    def _execute_plan_search_strategy(self, state: CampaignState, step: CampaignStep) -> None:
        run = self._latest_or_new_run(state)
        profile = state.campaign.source_profile or "generic"
        strategy = plan_search_strategy(self.config, state.campaign.topic, source_profile=profile)
        if strategy.id not in {item.id for item in run.search_strategies}:
            run.search_strategies.append(strategy)
        json_path, md_path = save_strategy(self.config, strategy)
        run.config["source_policy_profile"] = strategy.source_profile
        self.state_manager.save_run(run)
        self.project_manager.attach_run(state.campaign.project_id, run.run_id)
        if run.run_id not in state.campaign.run_ids:
            state.campaign.run_ids.append(run.run_id)
        step.run_id = run.run_id
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [str(json_path), str(md_path), str(Path(run.run_dir) / "search_strategies.json")]

    def _execute_search_round(self, state: CampaignState, step: CampaignStep) -> None:
        run = self._latest_or_new_run(state)
        if not run.search_strategies:
            strategy = plan_search_strategy(self.config, state.campaign.topic, source_profile=state.campaign.source_profile or "generic")
            run.search_strategies.append(strategy)
            self.state_manager.save_run(run)
        strategy = run.search_strategies[-1]
        rounds = execute_search_strategy(self.config, run.run_id, strategy.id)
        reloaded = self.state_manager.load_run(run.run_id)
        self.project_manager.attach_run(state.campaign.project_id, run.run_id)
        step.run_id = run.run_id
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [
            str(Path(reloaded.run_dir) / "search_rounds.json"),
            str(Path(reloaded.run_dir) / "search_queries.json"),
            str(Path(reloaded.run_dir) / "papers.json"),
        ]
        skipped_or_failed = [round_item for round_item in rounds if round_item.status != "complete"]
        if skipped_or_failed:
            step.blocking_issues = [
                f"{round_item.round_type}: {round_item.status}; {'; '.join(round_item.failures) or 'no failure detail'}"
                for round_item in skipped_or_failed
            ]

    def _execute_canonicalize_papers(self, state: CampaignState, step: CampaignStep) -> None:
        artifacts: list[str] = []
        for run in self._load_runs(state):
            canonicalize_run(self.config, run.run_id)
            artifacts.append(str(Path(run.run_dir) / "paper_merge_report.md"))
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = artifacts

    def _execute_prior_work_recall_gate(self, state: CampaignState, step: CampaignStep) -> None:
        artifacts: list[str] = []
        issues: list[str] = []
        for run in self._load_runs(state):
            for gap in run.gaps:
                assessment = assess_run_prior_work_recall(self.config, run.run_id, gap_id=gap.id)
                if not assessment.novelty_allowed:
                    issues.extend(assessment.blocking_issues)
            artifacts.append(str(Path(run.run_dir) / "prior_work_recall.md"))
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = artifacts
        step.blocking_issues = issues

    def _execute_gap_synthesis(self, state: CampaignState, step: CampaignStep) -> None:
        artifacts: list[str] = []
        for run in self._load_runs(state):
            run = GapMining().run(run, force=True)
            run = NoveltyGate(search_sources=False).assess(run, deep=True)
            self.state_manager.save_run(run)
            artifacts.extend(
                [
                    str(Path(run.run_dir) / "gaps.json"),
                    str(Path(run.run_dir) / "gap_evidence_matrix.json"),
                    str(Path(run.run_dir) / "novelty_dossiers.json"),
                ]
            )
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = artifacts

    def _execute_search_counterevidence(self, state: CampaignState, step: CampaignStep) -> None:
        run = self._latest_or_new_run(state)
        run.search_queries.append(
            SearchQueryRecord(
                id=f"query-{len(run.search_queries) + 1:04d}",
                query=f"{state.campaign.topic} counterevidence closest prior work duplicate baseline",
                source_names=[],
                purpose="real_literature_counterevidence",
                max_results=8,
                executed_at=utc_now_iso(),
                result_paper_ids=[],
                failure_messages=[
                    "Counterevidence search requested by real-literature controller; execute source strategy before claiming novelty."
                ],
                provenance=Provenance(
                    created_by_skill="campaign-controller",
                    source_ids=[state.campaign.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Recorded counterevidence search requirement without inventing results.",
                ),
            )
        )
        refresh_source_coverage(run, warnings=["Counterevidence search is pending execution."])
        self.state_manager.save_run(run)
        step.run_id = run.run_id
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [str(Path(run.run_dir) / "search_queries.json")]

    def _execute_build_index(self, state: CampaignState, step: CampaignStep) -> None:
        program = self.project_manager.sync_project_memory(state.campaign.project_id)
        manifest = build_project_index(program)
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [str(Path(manifest.path) / "manifest.json")]
        state.milestones.append(
            _milestone(state.campaign.id, "reading_ready", [str(Path(manifest.path) / "manifest.json")], "Built project retrieval index.")
        )

    def _execute_parse_more(self, state: CampaignState, step: CampaignStep) -> None:
        runs = self._load_runs(state)
        for run in runs:
            if run.papers and not run.paper_notes:
                priority_papers = sorted(run.papers, key=lambda paper: (_is_fallback_paper(paper), paper.title.lower()))
                run = DeepReading().read_papers(run, priority_papers[: min(len(priority_papers), 12)], allow_abstract_only=True)
            refresh_source_coverage(
                run, warnings=["Controller found missing full text; run PDF download/parse workflow for stronger evidence."]
            )
            self.state_manager.save_run(run)
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [str(Path(run.run_dir) / "full_text_coverage.md") for run in runs]

    def _execute_deterministic_placeholder(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        step.status = "skipped"
        step.completed_at = utc_now_iso()
        step.blocking_issues.append(
            f"Deterministic campaign controller recorded `{action.decision_type}` but did not fabricate research outputs."
        )
        state.campaign.status = "paused"

    def _execute_codex_task(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        task_type = action.task_type or "campaign_planning"
        pack_dir = create_campaign_task_pack(self.config, state.campaign.id, task_type)
        updated = self.manager.load_campaign_state(state.campaign.id)
        task_id = updated.campaign.task_ids[-1]
        state.campaign.task_ids = updated.campaign.task_ids
        _merge_steps(state, updated.steps)
        step.task_spec_id = task_id
        step.output_artifacts = [str(pack_dir / "outputs" / name) for name in CAMPAIGN_TASK_OUTPUTS[task_type]]
        if state.campaign.mode == "fake_agent":
            output_paths = _write_fake_campaign_outputs(pack_dir, task_type)
            record = CampaignOutputImporter(self.config).import_outputs(state.campaign.id, task_id, output_paths)
            refreshed = self.manager.load_campaign_state(state.campaign.id)
            state.steps = refreshed.steps
            state.imports = refreshed.imports
            state.milestones = refreshed.milestones
            _set_step_status(
                state,
                step.id,
                status="complete" if record.status in {"applied", "partial"} else "failed",
                completed_at=utc_now_iso(),
                issues=record.issues,
            )
            if record.issues:
                step.blocking_issues = record.issues
            return
        step.status = "blocked"
        step.blocking_issues = ["awaiting validated Codex/GPT-5.4 campaign output import"]
        step.completed_at = utc_now_iso()
        state.campaign.status = "paused"

    def _execute_request_codex_synthesis(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        if state.campaign.mode in {"fake_agent", "codex_task_pack", "codex_direct", "manual_handoff"}:
            self._execute_codex_task(state, action, step)
            return
        self._execute_deterministic_research_synthesis(state, step)

    def _execute_deterministic_research_synthesis(self, state: CampaignState, step: CampaignStep) -> None:
        program = self.project_manager.load_project(state.campaign.project_id)
        runs = self._load_runs(state)
        selected_run = next((run for run in runs if run.gaps and run.prior_work_recall_assessments), None)
        if selected_run is None:
            self._execute_deterministic_placeholder(
                state,
                CampaignAction(
                    decision_type="request_codex_synthesis",
                    step_type="review",
                    reason="No gap with prior-work recall exists for deterministic synthesis.",
                ),
                step,
            )
            return
        allowed = next((item for item in selected_run.prior_work_recall_assessments if item.novelty_allowed), None)
        gap = next((item for item in selected_run.gaps if allowed and item.id == allowed.target_id), selected_run.gaps[0])
        direction_id = f"direction-{gap.id}"
        prior_work_ids = (allowed.top_prior_work_ids if allowed else [])[:5]
        direction = ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title=gap.title,
            summary=(
                "Deterministic v0.5 synthesis from live search, abstract/full-text notes, "
                "gap evidence matrix, and prior-work recall. Requires human review before use."
            ),
            linked_gap_ids=[gap.id],
            linked_novelty_dossier_ids=[dossier.target_id for dossier in selected_run.novelty_dossiers if dossier.target_id == gap.id],
            supporting_paper_ids=gap.supporting_paper_ids[:6],
            counterevidence_paper_ids=prior_work_ids,
            maturity="experiment_ready",
            readiness_score=0.72,
            blocking_issues=["Requires expert review and stronger full-text coverage before manuscript claims."],
            next_actions=["Validate baselines, collect full text for top prior work, and run reviewer panel."],
            provenance=Provenance(
                created_by_skill="campaign-controller",
                source_ids=[state.campaign.id, selected_run.run_id, gap.id, *prior_work_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a conservative experiment-ready direction after real-literature prior-work gates passed.",
            ),
        )
        program.research_directions = [item for item in program.research_directions if item.id != direction_id] + [direction]
        entries = [
            RelatedWorkEntry(
                direction_id=direction_id,
                paper_id=paper_id,
                relationship="closest_prior_work",
                relevance_score=0.75,
                what_it_contributes="Closest prior-work candidate from recall gate.",
                what_it_does_not_solve="Requires human review before treating this as a decisive novelty distinction.",
                must_cite=True,
                reviewer_risk_if_omitted="High; omission would weaken novelty and related-work review.",
                provenance=Provenance(
                    created_by_skill="campaign-controller",
                    source_ids=[paper_id, gap.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Added closest-prior-work entry from prior-work recall.",
                ),
            )
            for paper_id in prior_work_ids
        ]
        if entries:
            program.related_work_matrices = [item for item in program.related_work_matrices if item.direction_id != direction_id] + [
                RelatedWorkMatrix(
                    direction_id=direction_id,
                    entries=entries,
                    coverage_summary="Closest-prior-work matrix from v0.5 prior-work recall gate.",
                    must_read_paper_ids=prior_work_ids,
                    provenance=Provenance(
                        created_by_skill="campaign-controller",
                        source_ids=[state.campaign.id, *prior_work_ids],
                        timestamp=utc_now_iso(),
                        reasoning_summary="Created related-work matrix from recalled prior work.",
                    ),
                )
            ]
        protocol_id = f"protocol-{direction_id}"
        program.experiment_protocols = [item for item in program.experiment_protocols if item.id != protocol_id] + [
            ExperimentProtocol(
                id=protocol_id,
                direction_id=direction_id,
                linked_experiment_plan_id="",
                objective=f"Test whether the proposed gap can be addressed: {gap.title}",
                hypothesis=gap.description or gap.title,
                datasets=["live-literature-derived benchmark candidates; exact dataset must be selected before implementation"],
                metrics=["false positive rate", "precision", "recall", "confidence interval"],
                statistical_tests=["binomial confidence intervals for low-FPR estimates"],
                ablations=["remove monitor signal", "vary detection threshold", "compare against closest prior-work baseline"],
                expected_artifacts=["evaluation script", "baseline comparison", "error analysis"],
                failure_modes=["closest prior work already solves the gap", "insufficient full-text evidence", "benchmark mismatch"],
                safety_ethics_notes=["Do not deploy monitor claims without adversarial and false-positive analysis."],
                compute_budget="small offline prototype before any large-scale benchmark",
                timeline=["Confirm full-text prior work", "Implement baseline", "Run smoke evaluation", "Human review"],
                provenance=Provenance(
                    created_by_skill="campaign-controller",
                    source_ids=[direction_id, gap.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created concrete experiment protocol from a v0.5 research direction.",
                ),
            )
        ]
        self.project_manager.save_project(program)
        state.campaign.status = "complete"
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.output_artifacts = [
            str(Path(program.project.root_dir) / "research_directions.json"),
            str(Path(program.project.root_dir) / "related_work_matrices.json"),
            str(Path(program.project.root_dir) / "experiment_protocols.json"),
        ]
        state.stop_conditions.append(
            campaign_stop_condition(
                state.campaign.id,
                reason="ready_experiment_protocol",
                evidence=[direction_id, protocol_id, gap.id],
            )
        )

    def _execute_import_outputs(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        task_id = action.evidence[0]
        record = CampaignOutputImporter(self.config).import_outputs(state.campaign.id, task_id, [])
        refreshed = self.manager.load_campaign_state(state.campaign.id)
        state.imports = refreshed.imports
        state.milestones = refreshed.milestones
        step.task_spec_id = task_id
        step.status = "complete" if record.status in {"applied", "partial"} else "failed"
        step.completed_at = utc_now_iso()
        step.blocking_issues = record.issues

    def _execute_request_human_review(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        state.campaign.status = "paused"
        step.status = "blocked"
        step.completed_at = utc_now_iso()
        step.blocking_issues = ["human review required before the campaign can safely continue"]
        state.stop_conditions.append(campaign_stop_condition(state.campaign.id, reason=action.reason, evidence=action.evidence))

    def _execute_export_package(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        step.status = "skipped"
        step.completed_at = utc_now_iso()
        step.blocking_issues.append("Package export is gated by direction maturity and explicit export workflow.")
        state.campaign.status = "paused"

    def _execute_stop(self, state: CampaignState, action: CampaignAction, step: CampaignStep) -> None:
        state.campaign.status = "complete" if "stop_ready" in action.evidence else "paused"
        step.status = "complete"
        step.completed_at = utc_now_iso()
        state.stop_conditions.append(campaign_stop_condition(state.campaign.id, reason=action.reason, evidence=action.evidence))

    def _execute_quality_stop(self, state: CampaignState, action: CampaignAction, step: CampaignStep, *, status: str) -> None:
        state.campaign.status = status
        step.status = "complete"
        step.completed_at = utc_now_iso()
        step.blocking_issues = action.evidence
        state.stop_conditions.append(campaign_stop_condition(state.campaign.id, reason=action.reason, evidence=action.evidence))

    def _record_decision(self, state: CampaignState, action: CampaignAction) -> CampaignDecision:
        decision = CampaignDecision(
            id=f"campaign-decision-{utc_now_compact()}",
            campaign_id=state.campaign.id,
            iteration=len(state.decisions) + 1,
            decision_type=action.decision_type,
            reason=action.reason,
            evidence=[*action.evidence, *([f"task_type={action.task_type}"] if action.task_type else [])],
            expected_value=_expected_value(action),
            cost_estimate=_cost_estimate(action),
            status="complete",
            provenance=Provenance(
                created_by_skill="campaign-controller",
                source_ids=[state.campaign.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Campaign controller selected the next action from persisted campaign/project state.",
            ),
        )
        state.decisions.append(decision)
        if decision.id not in state.campaign.decision_ids:
            state.campaign.decision_ids.append(decision.id)
        return decision

    def _record_step(self, state: CampaignState, action: CampaignAction, decision: CampaignDecision) -> CampaignStep:
        step = CampaignStep(
            id=f"campaign-step-{utc_now_compact()}-{action.step_type}",
            campaign_id=state.campaign.id,
            name=action.reason,
            step_type=action.step_type,
            status=action.status,
            input_artifacts=[decision.id],
            started_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="campaign-controller",
                source_ids=[state.campaign.id, decision.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Campaign step created for the controller decision.",
            ),
        )
        state.steps.append(step)
        return step

    def _latest_or_new_run(self, state: CampaignState) -> ResearchRunState:
        runs = self._load_runs(state)
        if runs:
            return runs[-1]
        run = self.state_manager.create_run(state.campaign.topic)
        run.config["project_id"] = state.campaign.project_id
        run.config["campaign_id"] = state.campaign.id
        self.state_manager.save_run(run)
        return run

    def _load_context(self, campaign_id: str) -> tuple[CampaignState, Any, list[ResearchRunState]]:
        state = self.manager.load_campaign_state(campaign_id)
        program = self.project_manager.load_project(state.campaign.project_id)
        runs = self._load_runs(state)
        return state, program, runs

    def _load_runs(self, state: CampaignState) -> list[ResearchRunState]:
        runs: list[ResearchRunState] = []
        for run_id in state.campaign.run_ids:
            try:
                runs.append(self.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        return runs


def _expected_value(action: CampaignAction) -> str:
    if action.decision_type == "source_health_check":
        return "Validate live source readiness before spending campaign budget."
    if action.decision_type == "plan_search_strategy":
        return "Create auditable multi-round search coverage before synthesis."
    if action.decision_type == "execute_search_round":
        return "Collect live literature records for coverage, triage, and novelty checks."
    if action.decision_type == "canonicalize_papers":
        return "Remove duplicate paper records before ranking and novelty checks."
    if action.decision_type == "run_prior_work_recall_gate":
        return "Block overclaiming by checking whether close prior work has been searched and compared."
    if action.decision_type == "request_codex_synthesis":
        return "Ask Codex to synthesize only after evidence gathering and recall gates pass."
    if action.decision_type in {"stop_insufficient_live_coverage", "reject_low_novelty_direction"}:
        return "Stop before producing misleading research recommendations."
    if action.decision_type == "search_more":
        return "Improve source coverage before claims or novelty decisions."
    if action.decision_type == "ask_codex":
        return "Produce agent-backed synthesis for later validation and import."
    if action.decision_type == "build_index":
        return "Enable retrieval-backed reading, gap mining, and novelty checks."
    return "Advance campaign state without weakening evidence discipline."


def _cost_estimate(action: CampaignAction) -> str:
    if action.decision_type in {"ask_codex", "request_codex_synthesis"}:
        return "agent_task=1"
    if action.decision_type in {"search_more", "execute_search_round", "search_counterevidence"}:
        return "query=1"
    return "local"


def _milestone(campaign_id: str, milestone_type: str, artifacts: list[str], notes: str):
    from gapforge.models import CampaignMilestone

    return CampaignMilestone(
        id=f"campaign-milestone-{utc_now_compact()}",
        campaign_id=campaign_id,
        milestone_type=milestone_type,
        status="complete",
        linked_artifacts=artifacts,
        notes=notes,
        provenance=Provenance(
            created_by_skill="campaign-controller",
            source_ids=[campaign_id, *artifacts],
            timestamp=utc_now_iso(),
            reasoning_summary="Campaign controller recorded a milestone.",
        ),
    )


def _write_fake_campaign_outputs(pack_dir: Path, task_type: str) -> list[Path]:
    outputs_dir = pack_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for filename in CAMPAIGN_TASK_OUTPUTS[task_type]:
        path = outputs_dir / filename
        path.write_text(json.dumps(_fake_payload(filename), indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _fake_payload(filename: str) -> dict[str, Any]:
    top_key = filename.removesuffix(".json")
    object_id = f"fake-{top_key}"
    if filename == "stop_condition_patch.json":
        return {top_key: [{"id": object_id, "reason": "Fake campaign controller stop condition.", "triggered": True}]}
    if filename == "final_recommendation_patch.json":
        return {top_key: [{"id": object_id, "recommendation": "Fake agent cannot recommend a real direction.", "verdict": "unknown"}]}
    if "novelty" in filename:
        return {
            top_key: [
                {
                    "id": object_id,
                    "target_id": "unknown",
                    "idea_summary": "Fake agent leaves novelty unknown.",
                    "verdict": "unknown",
                    "novelty_strength": "unknown",
                    "confidence": "low",
                    "missing_searches": ["real prior-work search required"],
                }
            ]
        }
    if filename == "missing_searches_patch.json":
        return {top_key: [{"id": object_id, "search_request": "Run a real closest-prior-work search."}]}
    if "gap" in filename:
        return {
            top_key: [
                {
                    "id": object_id,
                    "gap_id": "unknown",
                    "description": "Fake agent gap output is a schema regression artifact only.",
                    "risk_that_gap_is_fake": "High; fake output is not research evidence.",
                    "confidence": "low",
                }
            ]
        }
    if "evidence" in filename:
        return {top_key: [{"id": object_id, "paper_id": "unknown", "quote": "Fake agent produced no evidence.", "confidence": "low"}]}
    if "paper_notes" in filename:
        return {
            top_key: [
                {
                    "id": object_id,
                    "paper_id": "unknown",
                    "one_sentence_summary": "Fake agent produced a non-conclusive placeholder note.",
                    "confidence": "low",
                }
            ]
        }
    if "claims" in filename:
        return {
            top_key: [
                {
                    "id": object_id,
                    "text": "Fake agent output is not an evidence-backed research claim.",
                    "status": "uncertain",
                    "confidence": "low",
                }
            ]
        }
    if "review" in filename or "rebuttal" in filename or "required_fixes" in filename:
        return {
            top_key: [{"id": object_id, "recommendation": "Fake reviewer requires real evidence before acceptance.", "confidence": "low"}]
        }
    if "experiment" in filename or "baseline" in filename or "reproducibility" in filename:
        return {top_key: [{"id": object_id, "recommendation": "Fake experiment output is not paper-ready.", "confidence": "low"}]}
    return {top_key: [{"id": object_id, "recommendation": "Fake campaign output for schema validation.", "confidence": "low"}]}


def _merge_steps(state: CampaignState, incoming: list[CampaignStep]) -> None:
    known = {step.id for step in state.steps}
    for step in incoming:
        if step.id not in known:
            state.steps.append(step)
            known.add(step.id)


def _set_step_status(
    state: CampaignState,
    step_id: str,
    *,
    status: str,
    completed_at: str,
    issues: list[str] | None = None,
) -> None:
    for step in state.steps:
        if step.id == step_id:
            step.status = status
            step.completed_at = completed_at
            if issues is not None:
                step.blocking_issues = issues
            return


def _network_disabled() -> bool:
    return os.environ.get("GAPFORGE_DISABLE_NETWORK", "").strip() in {"1", "true", "TRUE", "yes"}


def _is_fallback_paper(paper: Any) -> bool:
    return (
        bool(getattr(paper, "raw_metadata", {}).get("fallback"))
        or "fallback" in (getattr(getattr(paper, "provenance", None), "reasoning_summary", "") or "").lower()
    )
