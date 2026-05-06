"""Campaign-level actual-run attestation status helpers."""

from __future__ import annotations

from gapforge.agents.attestation import (
    CAMPAIGN_IMPORT_STATUSES,
    attestation_can_count,
    campaign_attestation_status,
    normalize_execution_method,
)
from gapforge.campaigns import CampaignState
from gapforge.models import AgentActualRunAttestation, AttestationStatus, CampaignImportRecord, Provenance, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


def create_campaign_actual_run_attestation(
    state: CampaignState,
    task_id: str,
    *,
    agent_name: str,
    model: str,
    execution_method: str,
    attester: str,
    statement: str = "",
) -> AgentActualRunAttestation:
    """Record a human attestation for a campaign task.

    Attestation may be recorded before validation/import; status evaluation will
    recompute whether it is currently eligible after imports and review happen.
    """

    method = normalize_execution_method(execution_method)
    latest_import = latest_campaign_import(state, task_id)
    import_status = latest_import.status if latest_import else "missing"
    accepted = (
        latest_import is not None
        and latest_import.status in CAMPAIGN_IMPORT_STATUSES
        and attestation_can_count(
            agent_name=agent_name,
            model=model,
            method=method,
            validation_import_status=import_status,
        )
    )
    if not statement:
        statement = (
            f"{attester} attests that {agent_name}/{model} produced campaign task {task_id} "
            f"using {method}; validated import status is {import_status}."
        )
    attestation = AgentActualRunAttestation(
        id=f"agent-attestation-{utc_now_compact()}-{task_id}",
        task_spec_id=task_id,
        agent_run_record_id=latest_import.id if latest_import else "",
        attester=attester,
        agent_name=agent_name,
        model=model,
        execution_method=method,
        statement=statement,
        created_at=utc_now_iso(),
        accepted_as_actual_run=accepted,
        provenance=Provenance(
            created_by_skill="campaign-agent-attestation",
            source_ids=[state.campaign.id, task_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Recorded human attestation for a campaign task; actual-run eligibility is validation/import gated.",
        ),
    )
    state.agent_actual_run_attestations = [item for item in state.agent_actual_run_attestations if item.id != attestation.id]
    state.agent_actual_run_attestations.append(attestation)
    if latest_import is not None and accepted and not _import_has_attestation(latest_import, attestation.id):
        latest_import.accepted_objects.append(
            {
                "type": "agent_actual_run_attestation",
                "id": attestation.id,
                "accepted": True,
            }
        )
    return attestation


def campaign_task_attestation_status(state: CampaignState, task_id: str) -> AttestationStatus:
    latest_import = latest_campaign_import(state, task_id)
    latest_attestation = latest_campaign_attestation(state, task_id)
    return campaign_attestation_status(
        task_id,
        import_status=latest_import.status if latest_import else "missing",
        attestation=latest_attestation,
        campaign_id=state.campaign.id,
        human_review_accepted=campaign_human_review_accepted(state),
    )


def campaign_attestation_statuses(state: CampaignState) -> list[AttestationStatus]:
    task_ids = list(dict.fromkeys([*state.campaign.task_ids, *(record.task_id for record in state.imports)]))
    return [campaign_task_attestation_status(state, task_id) for task_id in task_ids]


def campaign_actual_run_status(state: CampaignState) -> dict[str, object]:
    """Return actionable actual-run acceptance status for one campaign."""

    statuses = campaign_attestation_statuses(state)
    accepted_outputs = accepted_real_agent_output_ids(state)
    blockers = _campaign_actual_run_blockers(state, statuses, accepted_outputs)
    next_commands = _campaign_actual_run_next_commands(state, statuses, blockers)
    return {
        "campaign_id": state.campaign.id,
        "project_id": state.campaign.project_id,
        "mode": state.campaign.mode,
        "agent_name": state.campaign.agent_name or "codex",
        "model": state.campaign.model or "gpt-5.4",
        "passed": bool(accepted_outputs) and campaign_human_review_accepted(state) and not blockers,
        "accepted_real_campaign": bool(accepted_outputs) and campaign_human_review_accepted(state),
        "accepted_real_output_count": len(accepted_outputs),
        "accepted_real_agent_outputs": accepted_outputs,
        "task_statuses": [to_plain(status) for status in statuses],
        "blockers": blockers,
        "next_commands": next_commands,
        "fake_vs_real_explanation": ("Fake-agent output validates plumbing only and never counts as actual Codex/GPT-5.4 acceptance."),
        "task_pack_actual_run_explanation": (
            "Task-pack/manual-handoff output counts only after validation/import, Codex/GPT-5.4 attestation, and human review."
        ),
    }


def campaign_human_review_accepted(state: CampaignState) -> bool:
    if state.acceptance_summary is not None and state.acceptance_summary.accepted:
        return True
    return any(review.accepted for review in state.human_reviews)


def accepted_real_agent_output_ids(state: CampaignState, *, require_human_review: bool = False) -> list[str]:
    outputs: list[str] = []
    human_review_accepted = campaign_human_review_accepted(state)
    for task_id in dict.fromkeys([record.task_id for record in state.imports]):
        latest_import = latest_campaign_import(state, task_id)
        if latest_import is None:
            continue
        status = campaign_task_attestation_status(state, task_id)
        legacy_attested = _legacy_import_attested(latest_import)
        currently_eligible = status.accepted_as_actual_run or legacy_attested
        if require_human_review and not human_review_accepted:
            currently_eligible = False
        if currently_eligible and latest_import.status in CAMPAIGN_IMPORT_STATUSES:
            outputs.append(latest_import.id)
    return outputs


def _campaign_actual_run_blockers(
    state: CampaignState,
    statuses: list[AttestationStatus],
    accepted_outputs: list[str],
) -> list[str]:
    blockers: list[str] = []
    if state.campaign.mode == "fake_agent":
        blockers.append("Fake-agent campaigns do not count as actual Codex/GPT-5.4 acceptance.")
    if state.campaign.mode not in {"codex_task_pack", "codex_direct", "manual_handoff"}:
        blockers.append("Campaign mode is not a real Codex/GPT-5.4 execution pathway.")
    if not statuses:
        blockers.append("No campaign agent tasks or imports are recorded.")
    if not any(record.status in CAMPAIGN_IMPORT_STATUSES for record in state.imports):
        blockers.append("No validated/imported Codex outputs are recorded.")
    if not accepted_outputs:
        blockers.append("No imported output is attested as actual Codex/GPT-5.4 work.")
    if not campaign_human_review_accepted(state):
        blockers.append("Campaign human review acceptance is missing.")
    for status in statuses:
        blockers.extend(status.blockers)
    return _dedupe(blockers)


def _campaign_actual_run_next_commands(
    state: CampaignState,
    statuses: list[AttestationStatus],
    blockers: list[str],
) -> list[str]:
    commands: list[str] = []
    if state.campaign.mode == "fake_agent":
        commands.append("gapforge campaign-canary-run --profile single_task_codex_handoff --real")
    if not state.campaign.task_ids:
        commands.append(f"gapforge campaign-task --campaign-id {state.campaign.id} --type novelty_reviewer")
    if any("validated/imported" in blocker.lower() or "no campaign agent tasks" in blocker.lower() for blocker in blockers):
        commands.extend(
            [
                f"gapforge codex-handoff --campaign-id {state.campaign.id} --latest-task --print-prompt",
                f"gapforge validate-import-all --campaign-id {state.campaign.id}",
            ]
        )
    pending = [status for status in statuses if not status.has_attestation or not status.accepted_as_actual_run]
    if pending:
        task_id = pending[-1].task_id
        commands.append(
            f'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
        )
    if not campaign_human_review_accepted(state):
        commands.append(f'gapforge campaign-review --campaign-id {state.campaign.id} --accept --reviewer "<name>"')
    return _dedupe(commands)


def latest_campaign_import(state: CampaignState, task_id: str) -> CampaignImportRecord | None:
    records = [record for record in state.imports if record.task_id == task_id]
    return records[-1] if records else None


def latest_campaign_attestation(state: CampaignState, task_id: str) -> AgentActualRunAttestation | None:
    attestations = [item for item in state.agent_actual_run_attestations if item.task_spec_id == task_id]
    if attestations:
        return attestations[-1]
    # Backward compatibility: older campaign imports embedded accepted attestation
    # markers but did not persist full attestation records.
    latest_import = latest_campaign_import(state, task_id)
    if latest_import is None:
        return None
    for item in reversed(latest_import.accepted_objects):
        if item.get("type") == "agent_actual_run_attestation":
            return AgentActualRunAttestation(
                id=str(item.get("id") or f"legacy-attestation-{task_id}"),
                task_spec_id=task_id,
                agent_run_record_id=latest_import.id,
                attester=str(item.get("attester") or "legacy"),
                agent_name=str(item.get("agent") or item.get("agent_name") or "codex"),
                model=str(item.get("model") or "gpt-5.4"),
                execution_method=str(item.get("method") or "task_pack"),
                accepted_as_actual_run=bool(item.get("accepted")),
                provenance=Provenance(
                    created_by_skill="legacy-campaign-attestation",
                    source_ids=[latest_import.id, task_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Synthesized status from legacy import-level attestation marker.",
                ),
            )
    return None


def _legacy_import_attested(record: CampaignImportRecord) -> bool:
    return any(item.get("type") == "agent_actual_run_attestation" and item.get("accepted") is True for item in record.accepted_objects)


def _import_has_attestation(record: CampaignImportRecord, attestation_id: str) -> bool:
    return any(item.get("type") == "agent_actual_run_attestation" and item.get("id") == attestation_id for item in record.accepted_objects)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
