"""Campaign-level reviewer and rebuttal loop."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.config import GapForgeConfig
from gapforge.models import (
    CampaignDecision,
    Provenance,
    ResearchDirection,
    ReviewPanel,
    ReviewQueue,
    ReviewQueueItem,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers import render_rebuttal_plans_markdown, render_review_panel_markdown
from gapforge.reviewers.panel import ReviewPanelBuilder
from gapforge.state import utc_now_compact, utc_now_iso


class CampaignReviewerLoop:
    """Create review-panel tasks, validate reviewer output, and route fixes."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.campaign_manager = CampaignManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def run(self, campaign_id: str, direction_id: str) -> dict[str, Any]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        task_pack_path = create_campaign_task_pack(self.config, campaign_id, "reviewer_panel")
        if state.campaign.mode in {"codex_task_pack", "codex_direct", "manual_handoff"}:
            state = self.campaign_manager.load_campaign_state(campaign_id)
            state.campaign.status = "paused"
            self.campaign_manager.save_campaign_state(state)
        panel = ReviewPanelBuilder(self.config).build_for_project(state.campaign.project_id, direction_id)
        validation = validate_review_panel(panel, self.project_manager.load_project(state.campaign.project_id))
        tasks = rebuttal_tasks_from_panel(panel)
        payload = {
            "campaign_id": campaign_id,
            "direction_id": direction_id,
            "task_pack_path": str(task_pack_path),
            "panel": to_plain(panel),
            "validation": validation,
            "rebuttal_tasks": tasks,
            "requires_fixes": bool(panel.required_changes),
        }
        self._write_artifacts(campaign_id, direction_id, panel, payload)
        return payload

    def rebuttal_tasks(self, campaign_id: str, direction_id: str) -> dict[str, Any]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        program = self.project_manager.load_project(state.campaign.project_id)
        panel = _require_panel(program.review_panels, direction_id)
        payload = {
            "campaign_id": campaign_id,
            "direction_id": direction_id,
            "rebuttal_tasks": rebuttal_tasks_from_panel(panel),
        }
        _campaign_dir(self.config, state.campaign.project_id, campaign_id).joinpath("rebuttal_tasks.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return payload

    def apply_fixes(self, campaign_id: str, direction_id: str) -> dict[str, Any]:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        program = self.project_manager.load_project(state.campaign.project_id)
        panel = _require_panel(program.review_panels, direction_id)
        direction = _require_direction(program.research_directions, direction_id)
        tasks = rebuttal_tasks_from_panel(panel)
        decisions = [_decision_for_task(campaign_id, index, task) for index, task in enumerate(tasks, start=1)]
        queue_items = [_queue_item_for_task(program.project.id, direction_id, task) for task in tasks]
        program.review_queue = _merge_review_queue(program.review_queue, program.project.id, queue_items)
        downgraded_to = _downgrade_direction_if_needed(direction, panel)
        self.project_manager.save_project(program)

        state = self.campaign_manager.load_campaign_state(campaign_id)
        known_decision_ids = {decision.id for decision in state.decisions}
        for decision in decisions:
            if decision.id not in known_decision_ids:
                state.decisions.append(decision)
                state.campaign.decision_ids.append(decision.id)
        if panel.required_changes:
            state.steps.append(
                _fix_step(
                    campaign_id,
                    direction_id,
                    output_artifacts=[item.id for item in queue_items],
                    blocking=panel.required_changes,
                )
            )
        self.campaign_manager.save_campaign_state(state)
        payload = {
            "campaign_id": campaign_id,
            "direction_id": direction_id,
            "decisions": to_plain(decisions),
            "review_queue_items": to_plain(queue_items),
            "direction_maturity": downgraded_to,
            "required_changes": panel.required_changes,
        }
        _campaign_dir(self.config, state.campaign.project_id, campaign_id).joinpath("reviewer_fix_actions.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return payload

    def _write_artifacts(self, campaign_id: str, direction_id: str, panel: ReviewPanel, payload: dict[str, Any]) -> None:
        state = self.campaign_manager.load_campaign_state(campaign_id)
        campaign_dir = _campaign_dir(self.config, state.campaign.project_id, campaign_id)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        (campaign_dir / "reviewer_loop.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        lines = [
            f"# Reviewer Loop `{direction_id}`",
            "",
            "## Review Panel",
            "",
            render_review_panel_markdown(panel).rstrip(),
            "",
            "## Rebuttal Tasks",
            "",
            render_rebuttal_plans_markdown([panel]).rstrip(),
            "",
            "## Validation",
            "",
            *[f"- {issue}" for issue in payload["validation"]["issues"]],
        ]
        if not payload["validation"]["issues"]:
            lines.append("- No grounding or fake-result validation issues detected.")
        (campaign_dir / "reviewer_loop.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def validate_review_panel(panel: ReviewPanel, program: object) -> dict[str, Any]:
    known_ids = _known_ids(program)
    issues: list[str] = []
    for review in panel.reviewer_reviews:
        if (review.required_fixes or review.fatal_flaws) and not review.evidence_or_prior_work:
            if not _mentions_artifact_gap([*review.required_fixes, *review.fatal_flaws, *review.weaknesses]):
                issues.append(f"{review.reviewer_id} has objections without prior work, evidence, or an explicit artifact gap.")
        for evidence_id in review.evidence_or_prior_work:
            if evidence_id and evidence_id not in known_ids and not _is_safe_artifact_reference(evidence_id):
                issues.append(f"{review.reviewer_id} cites unknown prior-work/artifact ID `{evidence_id}`.")
    text = json.dumps(to_plain(panel)).lower()
    if _looks_like_fake_result(text):
        issues.append("Reviewer output appears to claim completed experimental results.")
    return {
        "status": "valid" if not issues else "warning",
        "issues": issues,
        "fake_results_found": _looks_like_fake_result(text),
        "required_change_count": len(panel.required_changes),
    }


def rebuttal_tasks_from_panel(panel: ReviewPanel) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for review in panel.reviewer_reviews:
        for fix in [*review.fatal_flaws, *review.required_fixes]:
            action = _action_for_fix(fix, review.role)
            tasks.append(
                {
                    "id": f"rebuttal-task-{_stable_id(panel.experiment_or_direction_id, review.reviewer_id, fix)}",
                    "direction_id": panel.experiment_or_direction_id,
                    "reviewer_id": review.reviewer_id,
                    "role": review.role,
                    "severity": "fatal" if fix in review.fatal_flaws else "major",
                    "required_fix": fix,
                    "recommended_action": action,
                    "evidence_or_prior_work": review.evidence_or_prior_work,
                    "must_not_invent_results": True,
                }
            )
    return tasks


def _decision_for_task(campaign_id: str, index: int, task: dict[str, Any]) -> CampaignDecision:
    decision_type = str(task["recommended_action"])
    return CampaignDecision(
        id=f"campaign-decision-{_stable_id(campaign_id, task['id'])}",
        campaign_id=campaign_id,
        iteration=index,
        decision_type=decision_type,
        reason=str(task["required_fix"]),
        evidence=list(task.get("evidence_or_prior_work", [])),
        expected_value=_expected_value(decision_type),
        cost_estimate="human/code/research follow-up required",
        status="pending",
        provenance=Provenance(
            created_by_skill="reviewer-loop",
            source_ids=[campaign_id, str(task["direction_id"]), str(task["id"])],
            timestamp=utc_now_iso(),
            reasoning_summary="Converted a reviewer-panel required fix into an auditable campaign decision.",
        ),
    )


def _queue_item_for_task(project_id: str, direction_id: str, task: dict[str, Any]) -> ReviewQueueItem:
    severity = str(task.get("severity", "major"))
    return ReviewQueueItem(
        id=f"review-item-{_stable_id(project_id, direction_id, str(task['id']))}",
        project_id=project_id,
        object_type="reviewer_fix",
        object_id=str(task["id"]),
        priority="high" if severity == "fatal" else "medium",
        reason=f"{task['recommended_action']}: {task['required_fix']}",
        requested_by_skill="reviewer-loop",
        status="open",
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="reviewer-loop",
            source_ids=[project_id, direction_id, str(task["id"])],
            timestamp=utc_now_iso(),
            reasoning_summary="Queued a campaign reviewer required fix for human review or implementation.",
        ),
    )


def _merge_review_queue(existing: ReviewQueue | None, project_id: str, items: list[ReviewQueueItem]) -> ReviewQueue:
    merged = {item.id: item for item in (existing.items if existing else [])}
    for item in items:
        previous = merged.get(item.id)
        if previous is not None:
            item.status = previous.status
            item.assigned_to = previous.assigned_to
            item.completed_at = previous.completed_at
            item.created_at = previous.created_at or item.created_at
        merged[item.id] = item
    queue = ReviewQueue(
        project_id=project_id,
        items=sorted(merged.values(), key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item.priority, 3), item.id)),
        summary="",
        provenance=Provenance(
            created_by_skill="reviewer-loop",
            source_ids=[project_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Review queue merged with campaign reviewer required fixes.",
        ),
    )
    open_count = len([item for item in queue.items if item.status == "open"])
    queue.summary = f"{open_count} open, {len(queue.items) - open_count} completed/dismissed"
    return queue


def _downgrade_direction_if_needed(direction: ResearchDirection, panel: ReviewPanel) -> str:
    fatal_text = " ".join(flaw for review in panel.reviewer_reviews for flaw in review.fatal_flaws).lower()
    if not fatal_text:
        return direction.maturity
    if "reject" in fatal_text or "duplicative" in fatal_text or "directly solves" in fatal_text:
        direction.maturity = "rejected"
    elif direction.maturity in {"experiment_ready", "manuscript_ready"}:
        direction.maturity = "validated_gap"
    direction.blocking_issues = sorted({*direction.blocking_issues, *panel.required_changes})
    direction.next_actions = sorted({*direction.next_actions, "Resolve reviewer-loop required fixes before manuscript readiness."})
    return direction.maturity


def _fix_step(campaign_id: str, direction_id: str, *, output_artifacts: list[str], blocking: list[str]):
    from gapforge.models import CampaignStep

    return CampaignStep(
        id=f"campaign-step-{utc_now_compact()}-reviewer-fixes",
        campaign_id=campaign_id,
        name=f"Reviewer fixes for {direction_id}",
        step_type="human_review",
        status="blocked",
        output_artifacts=output_artifacts,
        blocking_issues=blocking,
        started_at=utc_now_iso(),
        completed_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="reviewer-loop",
            source_ids=[campaign_id, direction_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Campaign reviewer loop converted required fixes into a blocked human-review step.",
        ),
    )


def _action_for_fix(fix: str, role: str) -> str:
    text = fix.lower()
    if "missing search" in text or "closest-prior" in text or "novelty" in text:
        return "search_more"
    if "baseline" in text:
        return "add_baseline"
    if any(term in text for term in ["protocol", "metric", "hypothesis", "failure", "falsif", "statistical", "safety", "ethics"]):
        return "revise_protocol"
    if "soften" in text or role in {"theory", "novelty"} and "claim" in text:
        return "soften_claim"
    if "reject" in text or "duplicative" in text or "directly solves" in text:
        return "reject_direction"
    return "request_human_review"


def _expected_value(decision_type: str) -> str:
    mapping = {
        "search_more": "Resolve novelty or coverage uncertainty before recommendation.",
        "add_baseline": "Reduce empirical reviewer risk by adding required comparisons.",
        "revise_protocol": "Make the experiment protocol concrete and falsifiable.",
        "soften_claim": "Prevent overclaiming unsupported novelty or theory.",
        "reject_direction": "Avoid spending effort on a likely duplicate or invalid direction.",
        "request_human_review": "Route ambiguous reviewer concerns to explicit human judgment.",
    }
    return mapping.get(decision_type, "Address reviewer-required fix.")


def _known_ids(program: object) -> set[str]:
    known: set[str] = {"claim_graph"}
    for attr in [
        "corpus_papers",
        "research_directions",
        "related_work_matrices",
        "experiment_protocols",
        "review_panels",
        "baseline_candidates",
        "experiment_code_tasks",
    ]:
        for item in getattr(program, attr, []) or []:
            for key in ["id", "paper_id", "direction_id", "experiment_or_direction_id"]:
                value = getattr(item, key, "")
                if value:
                    known.add(str(value))
    return known


def _mentions_artifact_gap(items: list[str]) -> bool:
    text = " ".join(items).lower()
    return any(term in text for term in ["no experiment protocol", "no novelty dossier", "no baseline", "no related-work matrix"])


def _is_safe_artifact_reference(value: str) -> bool:
    return value.startswith(("protocol-", "experiment-", "gap-", "paper-", "direction-", "claim_graph"))


def _looks_like_fake_result(text: str) -> bool:
    patterns = [
        r"\bwe achieved\b",
        r"\bresults show\b",
        r"\bour method achieved\b",
        r"\bimproved by \d+",
        r"\b\d+(?:\.\d+)?%\s+(accuracy|improvement|reduction|increase)\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _require_panel(panels: list[ReviewPanel], direction_id: str) -> ReviewPanel:
    panel = next((item for item in panels if item.experiment_or_direction_id == direction_id), None)
    if panel is None:
        raise KeyError(f"No review panel found for direction {direction_id}; run reviewer-loop first.")
    return panel


def _require_direction(directions: list[ResearchDirection], direction_id: str) -> ResearchDirection:
    direction = next((item for item in directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"No research direction found for {direction_id}")
    return direction


def _campaign_dir(config: GapForgeConfig, project_id: str, campaign_id: str) -> Path:
    return config.project_root / project_id / "campaigns" / campaign_id


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
