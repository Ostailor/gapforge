"""Campaign-level reports with explicit stop reasons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gapforge.config import GapForgeConfig
from gapforge.models import ResearchProgramState, ResearchRunState, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager

if TYPE_CHECKING:
    from gapforge.campaigns import CampaignState


STOP_REASON_TAXONOMY = {
    "ready_experiment_protocol",
    "ready_paper_package",
    "not_ready_poor_coverage",
    "not_ready_novelty_unknown",
    "rejected_duplicate_prior_work",
    "human_review_required",
    "budget_exhausted",
    "no_new_information",
    "agent_output_invalid",
    "manual_handoff_pending",
    "failed",
}

READY_STOP_REASONS = {"ready_experiment_protocol", "ready_paper_package"}


def write_campaign_report(config: GapForgeConfig, campaign_id: str, *, output_format: str = "markdown") -> Path:
    """Write a campaign report artifact and return its path."""
    from gapforge.campaigns import CampaignManager

    manager = CampaignManager(config)
    state = manager.load_campaign_state(campaign_id)
    program, runs = load_campaign_report_context(config, state)
    campaign_dir = config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id
    payload = build_campaign_report_payload(state, program, runs, campaign_dir=campaign_dir)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path = campaign_dir / "campaign_report.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path
    if output_format != "markdown":
        raise ValueError("Campaign report format must be `markdown` or `json`.")
    path = campaign_dir / "campaign_report.md"
    path.write_text(render_campaign_report_markdown(payload), encoding="utf-8")
    (campaign_dir / "campaign_report.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_campaign_report_context(config: GapForgeConfig, state: CampaignState) -> tuple[ResearchProgramState, list[ResearchRunState]]:
    """Load project and run context without failing the report for missing run artifacts."""
    program = ProjectMemoryManager(config).load_project(state.campaign.project_id)
    state_manager = ResearchStateManager(config)
    runs: list[ResearchRunState] = []
    for run_id in state.campaign.run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return program, runs


def build_campaign_report_payload(
    state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    *,
    campaign_dir: Path | None = None,
) -> dict[str, Any]:
    stop = campaign_stop_reason(state, program, runs)
    recommendation = _recommended_direction(state, program, runs, stop_reason=str(stop["reason"]))
    source_coverage = _source_coverage_payload(runs)
    retrieval_coverage = _retrieval_coverage_payload(program)
    return {
        "campaign_summary": {
            "campaign_id": state.campaign.id,
            "project_id": state.campaign.project_id,
            "title": state.campaign.title or state.campaign.topic,
            "topic": state.campaign.topic,
            "status": state.campaign.status,
            "run_ids": list(state.campaign.run_ids),
            "task_ids": list(state.campaign.task_ids),
            "created_at": state.campaign.created_at,
            "updated_at": state.campaign.updated_at,
        },
        "topic_and_source_profile": {
            "topic": state.campaign.topic,
            "source_profile": state.campaign.source_profile,
        },
        "agent": {
            "mode": state.campaign.mode,
            "agent_name": state.campaign.agent_name or "none",
            "model": state.campaign.model or "none",
        },
        "actual_run_status": _actual_run_status(state),
        "timeline": _timeline(state),
        "decisions": [_decision_payload(decision) for decision in state.decisions],
        "source_coverage": source_coverage,
        "retrieval_coverage": retrieval_coverage,
        "papers_read": _papers_read_payload(runs),
        "evidence_backed_gaps": _gaps_payload(runs),
        "novelty_dossiers": _novelty_payload(runs),
        "related_work_matrix": _related_work_payload(program),
        "research_directions": _directions_payload(program),
        "experiment_protocols": _protocols_payload(program),
        "reviewer_panel": _review_panels_payload(program),
        "human_review_queue": _review_queue_payload(program),
        "stop_reason": stop,
        "what_remains_uncertain": _uncertainties(state, program, runs, stop, source_coverage, retrieval_coverage),
        "next_recommended_action": _next_action(stop, recommendation),
        "recommendation": recommendation,
        "artifact_paths": _artifact_paths(campaign_dir),
    }


def campaign_stop_reason(
    state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
) -> dict[str, Any]:
    """Return a normalized, auditable campaign stop reason."""
    reasons = [condition.reason for condition in state.stop_conditions if condition.triggered and condition.reason]
    evidence = [item for condition in state.stop_conditions for item in condition.evidence]
    decision_text = " ".join(decision.reason for decision in state.decisions)
    blocking_text = " ".join(issue for step in state.steps for issue in step.blocking_issues)
    import_issues = [issue for record in state.imports for issue in record.issues]
    all_text = " ".join([*reasons, decision_text, blocking_text, *import_issues]).lower()

    if state.campaign.status == "failed" or any(step.status == "failed" for step in state.steps):
        reason = "failed"
    elif any(record.status == "rejected" for record in state.imports) or "invalid" in all_text:
        reason = "agent_output_invalid"
    elif _manual_handoff_pending(state):
        reason = "manual_handoff_pending"
    elif "human review" in all_text or any(step.step_type == "human_review" and step.status == "blocked" for step in state.steps):
        reason = "human_review_required"
    elif "budget" in all_text or "iteration limit" in all_text:
        reason = "budget_exhausted"
    elif _ready_for_paper_package(program):
        reason = "ready_paper_package"
    elif _ready_for_experiment_protocol(program):
        reason = "ready_experiment_protocol"
    elif _duplicate_prior_work_seen(runs):
        reason = "rejected_duplicate_prior_work"
    elif _novelty_unknown(runs, program):
        reason = "not_ready_novelty_unknown"
    elif _poor_coverage(runs):
        reason = "not_ready_poor_coverage"
    elif "no useful direction" in all_text or "no new" in all_text:
        reason = "no_new_information"
    else:
        reason = "no_new_information"

    explicit = bool(reasons)
    return {
        "reason": reason,
        "explicit": explicit,
        "taxonomy": sorted(STOP_REASON_TAXONOMY),
        "recorded_reasons": reasons,
        "evidence": evidence,
        "classification_basis": _classification_basis(reason, state, runs, program),
    }


def render_campaign_report_markdown(payload: dict[str, Any]) -> str:
    """Render a campaign report payload as conservative Markdown."""
    summary = payload["campaign_summary"]
    stop = payload["stop_reason"]
    recommendation = payload["recommendation"]
    lines = [
        f"# GapForge Campaign Report: {summary['title']}",
        "",
        "## 1. Campaign summary",
        "",
        f"- Campaign ID: `{summary['campaign_id']}`",
        f"- Project ID: `{summary['project_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Runs: {len(summary['run_ids'])}",
        f"- Agent tasks: {len(summary['task_ids'])}",
        "",
        "## 2. Topic and source profile",
        "",
        f"- Topic: {payload['topic_and_source_profile']['topic']}",
        f"- Source profile: `{payload['topic_and_source_profile']['source_profile']}`",
        "",
        "## 3. Agent/mode/model used",
        "",
        f"- Mode: `{payload['agent']['mode']}`",
        f"- Agent: `{payload['agent']['agent_name']}`",
        f"- Model: `{payload['agent']['model']}`",
        "",
        "## 4. Actual-run status",
        "",
        f"- Actual Codex/GPT-5.4 outputs imported: {len(payload['actual_run_status']['accepted_real_agent_outputs'])}",
        f"- Attestation present: {_yes_no(payload['actual_run_status']['attestation_present'])}",
        f"- Release-gate eligible: {_yes_no(payload['actual_run_status']['release_gate_eligible'])}",
        "",
        "## 5. Campaign timeline",
        "",
        *_bullets(payload["timeline"], empty="No campaign timeline entries recorded yet."),
        "",
        "## 6. Decisions made",
        "",
        *_bullets(
            [
                f"`{item['id']}` iteration={item['iteration']} `{item['decision_type']}` [{item['status']}]: {item['reason']}"
                for item in payload["decisions"]
            ],
            empty="No campaign decisions recorded yet.",
        ),
        "",
        "## 7. Source coverage",
        "",
        *_coverage_lines(payload["source_coverage"]),
        "",
        "## 8. Retrieval coverage",
        "",
        *_retrieval_lines(payload["retrieval_coverage"]),
        "",
        "## 9. Papers read",
        "",
        *_bullets(payload["papers_read"], empty="No paper notes are attached to this campaign yet."),
        "",
        "## 10. Evidence-backed gaps",
        "",
        *_bullets(payload["evidence_backed_gaps"], empty="No evidence-backed gaps are attached to this campaign yet."),
        "",
        "## 11. Novelty dossiers",
        "",
        *_bullets(payload["novelty_dossiers"], empty="No novelty dossiers are attached to this campaign yet."),
        "",
        "## 12. Related-work matrix",
        "",
        *_bullets(payload["related_work_matrix"], empty="No related-work matrix is attached to this campaign yet."),
        "",
        "## 13. Research directions and maturity",
        "",
        *_bullets(payload["research_directions"], empty="No research directions are attached to this campaign yet."),
        "",
        "## 14. Experiment protocols",
        "",
        *_bullets(payload["experiment_protocols"], empty="No experiment protocols are attached to this campaign yet."),
        "",
        "## 15. Reviewer panel",
        "",
        *_bullets(payload["reviewer_panel"], empty="No reviewer panel is attached to this campaign yet."),
        "",
        "## 16. Human review queue",
        "",
        *_bullets(payload["human_review_queue"], empty="No open human review queue items are recorded."),
        "",
        "## 17. Stop reason",
        "",
        f"- Stop reason: `{stop['reason']}`",
        f"- Explicit stop condition recorded: {_yes_no(stop['explicit'])}",
        *_bullets(stop["recorded_reasons"], empty="No explicit stop condition text is recorded."),
        "- Classification basis:",
        *_bullets(stop["classification_basis"], empty="No additional classification basis recorded."),
        "",
        "## 18. What remains uncertain",
        "",
        *_bullets(payload["what_remains_uncertain"], empty="No additional uncertainty was detected by the report generator."),
        "",
        "## 19. Next recommended action",
        "",
        payload["next_recommended_action"],
        "",
        "## Recommendation",
        "",
    ]
    if recommendation["ready"]:
        lines.extend(
            [
                f"- Recommended direction: `{recommendation['direction_id']}`",
                f"- Novelty dossier: `{recommendation['novelty_dossier_id']}`",
                f"- Related-work matrix: `{recommendation['related_work_matrix_id']}`",
                f"- Experiment protocol: `{recommendation['experiment_protocol_id']}`",
                f"- Source coverage assessment: `{recommendation['source_coverage_assessment']}`",
                f"- Evidence locators: {', '.join(f'`{item}`' for item in recommendation['evidence_locators']) or 'none'}",
            ]
        )
    else:
        lines.append(f"- No direction is ready for recommendation: {recommendation['reason']}")
    lines.extend(
        [
            "",
            "## Campaign Safety",
            "",
            "- This report explains process state and stop conditions; it does not certify research correctness.",
            "- Agent outputs count only after validation, attestation when required, and human acceptance.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _actual_run_status(state: CampaignState) -> dict[str, Any]:
    accepted = [
        str(obj.get("id", ""))
        for record in state.imports
        if record.status in {"applied", "partial"}
        for obj in record.accepted_objects
        if obj.get("type") == "agent_actual_run_attestation" and obj.get("accepted") is True
    ]
    attested = bool(accepted)
    return {
        "attestation_present": attested,
        "accepted_real_agent_outputs": accepted,
        "release_gate_eligible": bool(state.acceptance_summary and state.acceptance_summary.release_gate_eligible),
        "campaign_acceptance": to_plain(state.acceptance_summary) if state.acceptance_summary else None,
    }


def _timeline(state: CampaignState) -> list[str]:
    entries: list[tuple[str, str]] = []
    for step in state.steps:
        stamp = step.started_at or step.completed_at or ""
        entries.append((stamp, f"`{step.id}` {step.name} [{step.step_type}, {step.status}]"))
    for milestone in state.milestones:
        entries.append((milestone.id, f"`{milestone.id}` milestone `{milestone.milestone_type}` [{milestone.status}] {milestone.notes}"))
    return [entry for _, entry in sorted(entries, key=lambda item: item[0])]


def _decision_payload(decision: Any) -> dict[str, Any]:
    return {
        "id": decision.id,
        "iteration": decision.iteration,
        "decision_type": decision.decision_type,
        "reason": decision.reason,
        "evidence": list(decision.evidence),
        "expected_value": decision.expected_value,
        "cost_estimate": decision.cost_estimate,
        "status": decision.status,
    }


def _source_coverage_payload(runs: list[ResearchRunState]) -> dict[str, Any]:
    coverages = [run.source_coverage for run in runs if run.source_coverage is not None]
    searched_sources = sorted({source for coverage in coverages for source in coverage.searched_sources})
    warnings = [warning for coverage in coverages for warning in coverage.coverage_warnings]
    failed_sources = sorted({source for coverage in coverages for source in coverage.failed_sources})
    papers_by_source: dict[str, int] = {}
    for coverage in coverages:
        for source, count in coverage.papers_by_source.items():
            papers_by_source[source] = papers_by_source.get(source, 0) + count
    return {
        "run_count": len(runs),
        "coverage_records": len(coverages),
        "searched_sources": searched_sources,
        "failed_sources": failed_sources,
        "papers_by_source": papers_by_source,
        "papers_total": sum(len(run.papers) for run in runs),
        "papers_with_full_text": sorted({paper_id for coverage in coverages for paper_id in coverage.papers_with_full_text}),
        "papers_abstract_only": sorted({paper_id for coverage in coverages for paper_id in coverage.papers_abstract_only}),
        "fallback_paper_count": sum(coverage.fallback_paper_count for coverage in coverages),
        "warnings": warnings,
        "confidence": _best_confidence([coverage.confidence for coverage in coverages]),
    }


def _retrieval_coverage_payload(program: ResearchProgramState) -> dict[str, Any]:
    manifest_path = Path(program.project.root_dir) / "retrieval" / "manifest.json"
    payload: dict[str, Any] = {"index_exists": manifest_path.exists(), "manifest_path": str(manifest_path)}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload.update(
                {
                    "document_count": manifest.get("document_count", 0),
                    "index_type": manifest.get("index_type", ""),
                    "embedding_model": manifest.get("embedding_model", ""),
                }
            )
        except json.JSONDecodeError:
            payload["warning"] = "Retrieval manifest exists but is not valid JSON."
    return payload


def _papers_read_payload(runs: list[ResearchRunState]) -> list[str]:
    lines: list[str] = []
    paper_titles = {paper.id: paper.title for run in runs for paper in run.papers}
    for run in runs:
        for note in run.paper_notes:
            basis = "full-text" if any(section.paper_id == note.paper_id for section in run.paper_sections) else "abstract-only"
            title = paper_titles.get(note.paper_id, note.paper_id)
            lines.append(f"`{note.paper_id}` {title} ({basis}, confidence={note.confidence})")
    return lines


def _gaps_payload(runs: list[ResearchRunState]) -> list[str]:
    rows: list[str] = []
    matrix_by_gap = {matrix.gap_id: matrix for run in runs for matrix in run.gap_evidence_matrices}
    for run in runs:
        for gap in run.gaps:
            matrix = matrix_by_gap.get(gap.id)
            evidence = f"{len(matrix.evidence_rows)} evidence rows" if matrix else "no evidence matrix"
            rows.append(
                f"`{gap.id}` {gap.title or gap.description or 'Untitled gap'} "
                f"(confidence={gap.confidence}, {evidence}, papers={','.join(gap.supporting_paper_ids) or 'none'})"
            )
    return rows


def _novelty_payload(runs: list[ResearchRunState]) -> list[str]:
    rows: list[str] = []
    for run in runs:
        for dossier in run.novelty_dossiers:
            prior = ", ".join(dossier.top_prior_work) or "none listed"
            rows.append(
                f"`{dossier.target_id}` verdict=`{dossier.verdict}` strength=`{dossier.novelty_strength}` closest_prior_work={prior}"
            )
    return rows


def _related_work_payload(program: ResearchProgramState) -> list[str]:
    return [
        f"`{matrix.direction_id}` entries={len(matrix.entries)} missing={', '.join(matrix.missing_categories) or 'none'}"
        for matrix in program.related_work_matrices
    ]


def _directions_payload(program: ResearchProgramState) -> list[str]:
    return [
        f"`{direction.id}` {direction.title} maturity=`{direction.maturity}` readiness={direction.readiness_score:.2f}"
        for direction in sorted(program.research_directions, key=lambda item: item.readiness_score, reverse=True)
    ]


def _protocols_payload(program: ResearchProgramState) -> list[str]:
    return [
        f"`{protocol.id}` direction=`{protocol.direction_id}` metrics={', '.join(protocol.metrics) or 'unspecified'} "
        f"baselines={len(protocol.baselines)}"
        for protocol in program.experiment_protocols
    ]


def _review_panels_payload(program: ResearchProgramState) -> list[str]:
    return [
        f"`{panel.experiment_or_direction_id}` decision_risk=`{panel.decision_risk}` required_changes={len(panel.required_changes)}"
        for panel in program.review_panels
    ]


def _review_queue_payload(program: ResearchProgramState) -> list[str]:
    if program.review_queue is None:
        return []
    return [
        f"`{item.id}` {item.object_type}:{item.object_id} priority={item.priority} status={item.status}: {item.reason}"
        for item in program.review_queue.items
        if item.status == "open"
    ]


def _uncertainties(
    state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    stop: dict[str, Any],
    source_coverage: dict[str, Any],
    retrieval_coverage: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    if not stop["explicit"]:
        items.append("No explicit CampaignStopCondition is recorded; acceptance must wait for an auditable stop reason.")
    if source_coverage["confidence"] in {"", "low"}:
        items.append("Source coverage is low or absent.")
    if not retrieval_coverage["index_exists"]:
        items.append("No retrieval index is present for closest-prior-work or counterevidence search.")
    if any(dossier.verdict == "unknown" for run in runs for dossier in run.novelty_dossiers):
        items.append("At least one novelty dossier is still unknown.")
    if not program.related_work_matrices:
        items.append("No related-work matrix exists for direction-level prior-work positioning.")
    if any(step.status == "blocked" for step in state.steps):
        items.append("One or more campaign steps are blocked and require import, handoff, or human review.")
    return items


def _next_action(stop: dict[str, Any], recommendation: dict[str, Any]) -> str:
    reason = str(stop["reason"])
    if recommendation["ready"]:
        return "Proceed to human review of the linked direction, novelty dossier, related-work matrix, and experiment protocol."
    if reason == "manual_handoff_pending":
        return "Complete the Codex/GPT-5.4 handoff, place outputs in the task outputs directory, then validate and import them."
    if reason == "agent_output_invalid":
        return "Inspect validation errors, fix the agent output patch, and rerun campaign validation before import."
    if reason == "not_ready_poor_coverage":
        return "Run additional source-policy searches and regenerate source coverage before recommending a direction."
    if reason == "not_ready_novelty_unknown":
        return "Expand closest-prior-work search and rerun novelty dossier validation."
    if reason == "human_review_required":
        return "Resolve open human review queue items before continuing the campaign."
    if reason == "budget_exhausted":
        return "Increase the campaign budget or close the campaign as not ready with the current evidence."
    return "Continue only after resolving the listed uncertainties; no direction is currently ready."


def _recommended_direction(
    state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    *,
    stop_reason: str,
) -> dict[str, Any]:
    if stop_reason not in READY_STOP_REASONS:
        return {"ready": False, "reason": f"Stop reason `{stop_reason}` is not a ready state."}
    directions = [
        direction
        for direction in program.research_directions
        if direction.maturity in {"experiment_ready", "manuscript_ready"} and direction.maturity != "rejected"
    ]
    if not directions:
        return {"ready": False, "reason": "No experiment-ready or manuscript-ready direction exists."}
    direction = sorted(directions, key=lambda item: item.readiness_score, reverse=True)[0]
    dossier = _dossier_for_direction(direction.id, direction.linked_gap_ids, runs)
    matrix = next((item for item in program.related_work_matrices if item.direction_id == direction.id), None)
    protocol = next((item for item in program.experiment_protocols if item.direction_id == direction.id), None)
    source_coverage = _source_coverage_payload(runs)
    evidence_locators = _evidence_locators_for_direction(direction, runs)
    missing: list[str] = []
    if dossier is None:
        missing.append("novelty dossier")
    if matrix is None:
        missing.append("related-work matrix")
    if protocol is None:
        missing.append("experiment protocol")
    if source_coverage["confidence"] in {"", "low"}:
        missing.append("medium-or-better source coverage")
    if not evidence_locators:
        missing.append("evidence locators")
    if missing:
        return {"ready": False, "direction_id": direction.id, "reason": "Missing required links: " + ", ".join(missing)}
    assert dossier is not None
    assert matrix is not None
    assert protocol is not None
    return {
        "ready": True,
        "direction_id": direction.id,
        "novelty_dossier_id": dossier.target_id,
        "related_work_matrix_id": matrix.direction_id,
        "experiment_protocol_id": protocol.id,
        "evidence_locators": evidence_locators,
        "source_coverage_assessment": source_coverage["confidence"],
        "reason": "Direction has required campaign report links.",
    }


def _dossier_for_direction(direction_id: str, linked_gap_ids: list[str], runs: list[ResearchRunState]) -> Any | None:
    target_ids = {direction_id, *linked_gap_ids}
    dossiers = [dossier for run in runs for dossier in run.novelty_dossiers]
    return next((dossier for dossier in dossiers if dossier.target_id in target_ids), dossiers[0] if dossiers else None)


def _evidence_locators_for_direction(direction: Any, runs: list[ResearchRunState]) -> list[str]:
    gap_ids = set(direction.linked_gap_ids)
    locators = [
        row.locator
        for run in runs
        for matrix in run.gap_evidence_matrices
        if not gap_ids or matrix.gap_id in gap_ids
        for row in matrix.evidence_rows
        if row.locator
    ]
    locators.extend(span.locator for run in runs for span in run.evidence_spans if span.locator)
    return sorted(set(locators))[:20]


def _artifact_paths(campaign_dir: Path | None) -> dict[str, str]:
    if campaign_dir is None:
        return {}
    return {
        "campaign_report_markdown": str(campaign_dir / "campaign_report.md"),
        "campaign_report_json": str(campaign_dir / "campaign_report.json"),
        "steps": str(campaign_dir / "steps.json"),
        "decisions": str(campaign_dir / "decisions.json"),
        "stop_conditions": str(campaign_dir / "stop_conditions.json"),
    }


def _coverage_lines(payload: dict[str, Any]) -> list[str]:
    warnings = payload["warnings"] or []
    return [
        f"- Records: {payload['coverage_records']} across {payload['run_count']} run(s)",
        f"- Confidence: `{payload['confidence'] or 'low'}`",
        f"- Papers: {payload['papers_total']} total, {len(payload['papers_with_full_text'])} full-text, "
        f"{len(payload['papers_abstract_only'])} abstract-only",
        f"- Sources searched: {', '.join(payload['searched_sources']) or 'none'}",
        f"- Failed sources: {', '.join(payload['failed_sources']) or 'none'}",
        f"- Warnings: {'; '.join(warnings) if warnings else 'none'}",
    ]


def _retrieval_lines(payload: dict[str, Any]) -> list[str]:
    lines = [f"- Index exists: {_yes_no(payload['index_exists'])}", f"- Manifest: `{payload['manifest_path']}`"]
    if payload.get("document_count") is not None:
        lines.append(f"- Documents: {payload.get('document_count', 0)}")
    if payload.get("warning"):
        lines.append(f"- Warning: {payload['warning']}")
    return lines


def _classification_basis(reason: str, state: CampaignState, runs: list[ResearchRunState], program: ResearchProgramState) -> list[str]:
    if reason == "manual_handoff_pending":
        return [
            issue for step in state.steps for issue in step.blocking_issues if "awaiting" in issue.lower() or "handoff" in issue.lower()
        ]
    if reason == "agent_output_invalid":
        return [issue for record in state.imports for issue in record.issues] or [
            f"import {record.id} status={record.status}" for record in state.imports if record.status == "rejected"
        ]
    if reason == "not_ready_poor_coverage":
        return [f"source_coverage={coverage.confidence}" for run in runs if run.source_coverage for coverage in [run.source_coverage]]
    if reason == "not_ready_novelty_unknown":
        return [f"dossier {dossier.target_id} verdict={dossier.verdict}" for run in runs for dossier in run.novelty_dossiers]
    if reason.startswith("ready"):
        return [f"directions={len(program.research_directions)}", f"protocols={len(program.experiment_protocols)}"]
    return [condition.reason for condition in state.stop_conditions if condition.reason]


def _manual_handoff_pending(state: CampaignState) -> bool:
    return any(
        step.status == "blocked"
        and any("awaiting validated" in issue.lower() or "handoff" in issue.lower() for issue in step.blocking_issues)
        for step in state.steps
    )


def _ready_for_paper_package(program: ResearchProgramState) -> bool:
    return any(direction.maturity == "manuscript_ready" for direction in program.research_directions)


def _ready_for_experiment_protocol(program: ResearchProgramState) -> bool:
    return bool(program.experiment_protocols) and any(
        direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions
    )


def _duplicate_prior_work_seen(runs: list[ResearchRunState]) -> bool:
    return any(dossier.verdict == "reject" for run in runs for dossier in run.novelty_dossiers) or any(
        "duplicate" in getattr(idea, "reason", "").lower() for run in runs for idea in run.rejected_ideas
    )


def _novelty_unknown(runs: list[ResearchRunState], program: ResearchProgramState) -> bool:
    if any(dossier.verdict == "unknown" for run in runs for dossier in run.novelty_dossiers):
        return True
    return bool(program.research_directions) and not any(run.novelty_dossiers for run in runs)


def _poor_coverage(runs: list[ResearchRunState]) -> bool:
    if not runs:
        return True
    coverages = [run.source_coverage for run in runs if run.source_coverage is not None]
    if not coverages:
        return True
    return _best_confidence([coverage.confidence for coverage in coverages]) == "low"


def _best_confidence(values: list[str]) -> str:
    if "high" in values:
        return "high"
    if "medium" in values:
        return "medium"
    if "low" in values:
        return "low"
    return "low"


def _bullets(items: list[str], *, empty: str) -> list[str]:
    return [f"- {item}" for item in items] if items else [f"- {empty}"]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
