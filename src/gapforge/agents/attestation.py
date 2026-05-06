"""Attestation status helpers for actual Codex/GPT-5.4 runs."""

from __future__ import annotations

from gapforge.models import AgentActualRunAttestation, AgentRunRecord, AgentTaskSpec, AgentValidationResult, AttestationStatus

VALIDATED_IMPORT_STATUSES = {"valid", "warning"}
CAMPAIGN_IMPORT_STATUSES = {"valid", "applied", "partial"}
ACTUAL_AGENT_NAME = "codex"
ACTUAL_MODEL_NAME = "gpt-5.4"


def run_attestation_status(
    task_spec: AgentTaskSpec,
    *,
    validations: list[AgentValidationResult],
    run_records: list[AgentRunRecord],
    attestations: list[AgentActualRunAttestation],
    human_review_present: bool = False,
) -> AttestationStatus:
    latest_validation = validations[-1] if validations else None
    latest_record = run_records[-1] if run_records else None
    latest_attestation = attestations[-1] if attestations else None
    method = _method(latest_attestation.execution_method if latest_attestation else _record_method(latest_record))
    validation_import_status = latest_validation.status if latest_validation else "missing"
    blockers = _blockers(
        task_id=task_spec.id,
        validation_import_status=validation_import_status,
        imported=latest_record is not None and latest_record.status in {"imported", "complete"},
        attestation=latest_attestation,
        method=method,
        human_review_present=human_review_present,
        campaign_id="",
    )
    accepted = _attestation_currently_eligible(
        attestation=latest_attestation,
        method=method,
        validation_import_status=validation_import_status,
        imported=latest_record is not None and latest_record.status in {"imported", "complete"},
    )
    return AttestationStatus(
        task_id=task_spec.id,
        has_attestation=latest_attestation is not None,
        attestation_id=latest_attestation.id if latest_attestation else "",
        agent_name=latest_attestation.agent_name if latest_attestation else "",
        model=latest_attestation.model if latest_attestation else "",
        method=method,
        accepted_as_actual_run=accepted,
        validation_import_status=validation_import_status,
        blockers=blockers,
        next_commands=_next_commands(task_spec.id, method=method, campaign_id="", blockers=blockers),
    )


def campaign_attestation_status(
    task_id: str,
    *,
    import_status: str,
    attestation: AgentActualRunAttestation | None,
    campaign_id: str,
    human_review_accepted: bool = False,
) -> AttestationStatus:
    method = _method(attestation.execution_method if attestation else "task_pack")
    blockers = _blockers(
        task_id=task_id,
        validation_import_status=import_status,
        imported=import_status in CAMPAIGN_IMPORT_STATUSES,
        attestation=attestation,
        method=method,
        human_review_present=human_review_accepted,
        campaign_id=campaign_id,
    )
    accepted = _attestation_currently_eligible(
        attestation=attestation,
        method=method,
        validation_import_status=import_status,
        imported=import_status in CAMPAIGN_IMPORT_STATUSES,
    )
    return AttestationStatus(
        task_id=task_id,
        has_attestation=attestation is not None,
        attestation_id=attestation.id if attestation else "",
        agent_name=attestation.agent_name if attestation else "",
        model=attestation.model if attestation else "",
        method=method,
        accepted_as_actual_run=accepted,
        validation_import_status=import_status,
        blockers=blockers,
        next_commands=_next_commands(task_id, method=method, campaign_id=campaign_id, blockers=blockers),
    )


def attestation_can_count(
    *,
    agent_name: str,
    model: str,
    method: str,
    validation_import_status: str,
) -> bool:
    normalized_method = _method(method)
    return (
        normalized_method != "fake"
        and agent_name.strip().lower() == ACTUAL_AGENT_NAME
        and bool(model.strip())
        and model.strip().lower() == ACTUAL_MODEL_NAME
        and validation_import_status in VALIDATED_IMPORT_STATUSES | CAMPAIGN_IMPORT_STATUSES
    )


def normalize_execution_method(method: str) -> str:
    return _method(method)


def _blockers(
    *,
    task_id: str,
    validation_import_status: str,
    imported: bool,
    attestation: AgentActualRunAttestation | None,
    method: str,
    human_review_present: bool,
    campaign_id: str,
) -> list[str]:
    blockers: list[str] = []
    if method == "fake":
        blockers.append("Fake agent output never counts as actual-run acceptance.")
    if validation_import_status not in VALIDATED_IMPORT_STATUSES | CAMPAIGN_IMPORT_STATUSES:
        blockers.append("Validated import has not passed for this task.")
    if not imported:
        blockers.append("Agent output has not been imported.")
    if attestation is None:
        blockers.append("Actual Codex/GPT-5.4 attestation is missing.")
    else:
        if attestation.agent_name.strip().lower() == "fake":
            blockers.append("Fake agent attestation never counts.")
        if attestation.agent_name.strip().lower() != ACTUAL_AGENT_NAME:
            blockers.append("Attestation agent must be codex.")
        if not attestation.model.strip():
            blockers.append("Attestation model is missing.")
        elif attestation.model.strip().lower() != ACTUAL_MODEL_NAME:
            blockers.append("Attestation model must be gpt-5.4.")
    if method in {"task_pack", "manual_handoff", "direct"} and campaign_id and not human_review_present:
        blockers.append("Campaign human review acceptance is missing.")
    return list(dict.fromkeys(blockers))


def _attestation_currently_eligible(
    *,
    attestation: AgentActualRunAttestation | None,
    method: str,
    validation_import_status: str,
    imported: bool,
) -> bool:
    if attestation is None or not imported:
        return False
    return attestation_can_count(
        agent_name=attestation.agent_name,
        model=attestation.model,
        method=method,
        validation_import_status=validation_import_status,
    )


def _next_commands(task_id: str, *, method: str, campaign_id: str, blockers: list[str]) -> list[str]:
    commands: list[str] = []
    if any("Validated import" in blocker or "not been imported" in blocker for blocker in blockers):
        commands.append(f"gapforge validate-import-all --task-id {task_id}")
    if any("attestation" in blocker.lower() for blocker in blockers):
        attest_command = (
            f"gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 "
            f'--method {method or "task_pack"} --attester "<name>"'
        )
        commands.append(attest_command)
    if campaign_id and any("human review" in blocker.lower() for blocker in blockers):
        commands.append(f'gapforge campaign-review --campaign-id {campaign_id} --accept --reviewer "<name>"')
    commands.append(f"gapforge attestation-status --task-id {task_id}")
    return list(dict.fromkeys(commands))


def _record_method(record: AgentRunRecord | None) -> str:
    if record is None:
        return "task_pack"
    return str(record.usage_summary.get("execution_method") or record.usage_summary.get("mode") or "task_pack")


def _method(method: str) -> str:
    normalized = method.strip().lower().replace("-", "_")
    if normalized in {"taskpack", "task_pack"}:
        return "task_pack"
    if normalized in {"manual", "manual_handoff"}:
        return "manual_handoff"
    if normalized == "codex":
        return "direct"
    return normalized
