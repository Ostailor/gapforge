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
from gapforge.models import CampaignDecision, CampaignStep, Provenance, ResearchRunState, SearchQueryRecord
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval import build_project_index
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


class CampaignController:
    """Run one or more auditable campaign decisions."""

    def __init__(self, config: GapForgeConfig, policy: CampaignDecisionPolicy | None = None) -> None:
        self.config = config
        self.manager = CampaignManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.policy = policy or CampaignDecisionPolicy()

    def next_action(self, campaign_id: str, *, max_iterations: int | None = None) -> CampaignAction:
        state, program, runs = self._load_context(campaign_id)
        budget = campaign_budget_status(state, papers_seen=sum(len(run.papers) for run in runs), max_iterations_override=max_iterations)
        assessment = build_campaign_assessment(state, program, runs, budget_status=budget)
        return self.policy.decide(assessment)

    def run(self, campaign_id: str, *, mode: str | None = None, max_iterations: int | None = None) -> CampaignState:
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
            assessment = build_campaign_assessment(state, program, runs, budget_status=budget)
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
            if action.decision_type == "search_more":
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
    if action.decision_type == "search_more":
        return "Improve source coverage before claims or novelty decisions."
    if action.decision_type == "ask_codex":
        return "Produce agent-backed synthesis for later validation and import."
    if action.decision_type == "build_index":
        return "Enable retrieval-backed reading, gap mining, and novelty checks."
    return "Advance campaign state without weakening evidence discipline."


def _cost_estimate(action: CampaignAction) -> str:
    if action.decision_type == "ask_codex":
        return "agent_task=1"
    if action.decision_type == "search_more":
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
