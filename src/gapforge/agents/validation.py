"""Backward-compatible validation entrypoint for AgentClient implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.agents.attestation import attestation_can_count, run_attestation_status
from gapforge.agents.records import append_attestation, utc_now_iso
from gapforge.agents.schema_validator import validate_task_outputs
from gapforge.models import AgentActualRunAttestation, AgentTaskSpec, AgentValidationResult, Provenance, ResearchRunState
from gapforge.state import utc_now_compact


def validate_agent_outputs(state: ResearchRunState, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
    return validate_task_outputs(state, task_spec, output_paths)


def create_actual_run_attestation(
    state: ResearchRunState,
    task_spec: AgentTaskSpec,
    *,
    agent_name: str,
    model: str,
    execution_method: str,
    attester: str,
    statement: str = "",
) -> AgentActualRunAttestation:
    method = _normalize_method(execution_method)
    latest_record = _latest_run_record(state, task_spec.id)
    latest_validation = _latest_validation(state, task_spec.id)
    validation_status = latest_validation.status if latest_validation else "missing"
    accepted = latest_record is not None and attestation_can_count(
        agent_name=agent_name,
        model=model,
        method=method,
        validation_import_status=validation_status,
    )
    if not statement:
        statement = (
            f"{attester} attests that {agent_name}/{model} produced the outputs for task {task_spec.id} "
            f"using {method}; validation status is {latest_validation.status if latest_validation else 'missing'}."
        )
    attestation = AgentActualRunAttestation(
        id=f"agent-attestation-{utc_now_compact()}-{task_spec.id}",
        task_spec_id=task_spec.id,
        agent_run_record_id=latest_record.id if latest_record else "",
        attester=attester,
        agent_name=agent_name,
        model=model,
        execution_method=method,
        statement=statement,
        created_at=utc_now_iso(),
        accepted_as_actual_run=accepted,
        provenance=Provenance(
            created_by_skill="agent-actual-run-attestation",
            source_ids=[task_spec.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Recorded human attestation for whether validated agent outputs count as actual Codex/GPT-5.4 work.",
        ),
    )
    append_attestation(state, attestation)
    return attestation


def actual_run_status(state: ResearchRunState) -> dict[str, Any]:
    task_statuses: list[dict[str, Any]] = []
    accepted_task_ids: list[str] = []
    for task_spec in state.agent_task_specs:
        latest_record = _latest_run_record(state, task_spec.id)
        latest_validation = _latest_validation(state, task_spec.id)
        latest_attestation = _latest_attestation(state, task_spec.id)
        status = run_attestation_status(
            task_spec,
            validations=[latest_validation] if latest_validation else [],
            run_records=[latest_record] if latest_record else [],
            attestations=[latest_attestation] if latest_attestation else [],
        )
        counts = status.accepted_as_actual_run
        if counts:
            accepted_task_ids.append(task_spec.id)
        task_statuses.append(
            {
                "task_id": task_spec.id,
                "skill_name": task_spec.skill_name,
                "task_type": task_spec.task_type,
                "latest_run_record_id": latest_record.id if latest_record else "",
                "latest_run_status": latest_record.status if latest_record else "missing",
                "validation_id": latest_validation.id if latest_validation else "",
                "validation_status": latest_validation.status if latest_validation else "missing",
                "attestation_id": latest_attestation.id if latest_attestation else "",
                "attested": latest_attestation is not None,
                "execution_method": status.method,
                "counts_as_actual_run": counts,
                "blockers": status.blockers,
                "next_commands": status.next_commands,
            }
        )
    return {
        "run_id": state.run_id,
        "passed": bool(accepted_task_ids),
        "accepted_task_ids": accepted_task_ids,
        "task_statuses": task_statuses,
        "blockers": _aggregate_blockers(task_statuses),
    }


def _latest_run_record(state: ResearchRunState, task_id: str):
    records = [record for record in state.agent_run_records if record.task_spec_id == task_id]
    return records[-1] if records else None


def _latest_validation(state: ResearchRunState, task_id: str):
    validations = [validation for validation in state.agent_validation_results if validation.task_spec_id == task_id]
    return validations[-1] if validations else None


def _latest_attestation(state: ResearchRunState, task_id: str) -> AgentActualRunAttestation | None:
    attestations = [attestation for attestation in state.agent_actual_run_attestations if attestation.task_spec_id == task_id]
    return attestations[-1] if attestations else None


def _record_method(record: Any) -> str:
    if record is None:
        return "unknown"
    method = record.usage_summary.get("execution_method") or record.usage_summary.get("mode") or "unknown"
    return _normalize_method(str(method))


def _normalize_method(method: str) -> str:
    normalized = method.strip().lower().replace("-", "_")
    if normalized in {"taskpack", "task_pack"}:
        return "task_pack"
    if normalized in {"manual", "manual_handoff"}:
        return "manual_handoff"
    if normalized == "codex":
        return "direct"
    return normalized


def _aggregate_blockers(task_statuses: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for status in task_statuses:
        blockers.extend(str(blocker) for blocker in status["blockers"])
    return sorted(set(blockers))
