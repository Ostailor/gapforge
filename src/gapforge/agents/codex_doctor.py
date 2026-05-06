"""Task-pack/output diagnostics for Codex/GPT-5.4 workflows."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.agents.output_importer import AgentOutputImporter
from gapforge.agents.records import output_dir_for_task, task_pack_dir
from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.import_workflow import expected_campaign_files, find_campaign_task
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.config import GapForgeConfig
from gapforge.models import AgentTaskSpec, CodexTaskDoctorReport, Provenance, ResearchRunState, to_plain
from gapforge.state import ResearchStateManager, utc_now_iso


def doctor_codex_task(
    config: GapForgeConfig,
    *,
    task_id: str = "",
    campaign_id: str = "",
) -> CodexTaskDoctorReport | list[CodexTaskDoctorReport]:
    if campaign_id:
        state = CampaignManager(config).load_campaign_state(campaign_id)
        return [_doctor_single_task(config, task) for task in state.campaign.task_ids]
    if not task_id:
        raise ValueError("Either task_id or campaign_id is required.")
    return _doctor_single_task(config, task_id)


def _doctor_single_task(config: GapForgeConfig, task_id: str) -> CodexTaskDoctorReport:
    try:
        run_state, task_spec = _load_run_task(config, task_id)
    except FileNotFoundError:
        campaign_state, pack_dir = find_campaign_task(config, task_id)
        return _doctor_campaign_task(config, campaign_state, task_id, pack_dir)
    return _doctor_run_task(config, run_state, task_spec)


def render_codex_doctor_report(report: CodexTaskDoctorReport | list[CodexTaskDoctorReport]) -> str:
    if isinstance(report, list):
        if not report:
            return "# GapForge Codex Doctor\n\nNo campaign tasks found.\n"
        return "\n\n".join(render_codex_doctor_report(item).rstrip() for item in report) + "\n"
    lines = [
        "# GapForge Codex Doctor",
        "",
        f"- Task ID: `{report.task_id}`",
        f"- Run ID: `{report.run_id or 'none'}`",
        f"- Campaign ID: `{report.campaign_id or 'none'}`",
        f"- Task pack: `{report.task_pack_path}`",
        f"- Outputs directory: `{report.outputs_dir}`",
        f"- Validation status: `{report.validation_status}`",
        f"- Import status: `{report.import_status}`",
        f"- Attestation status: `{report.attestation_status}`",
        f"- Human review status: `{report.human_review_status}`",
        f"- Actual-run eligible: `{str(report.actual_run_eligible).lower()}`",
        "",
        "## Expected Files",
        "",
    ]
    lines.extend(f"- `{name}`" for name in report.expected_files or ["none"])
    lines.extend(["", "## Existing Outputs", ""])
    lines.extend(f"- `{path}`" for path in report.existing_outputs or ["none"])
    if report.missing_outputs:
        lines.extend(["", "## Missing Outputs", ""])
        lines.extend(f"- `{name}`" for name in report.missing_outputs)
    if report.invalid_outputs:
        lines.extend(["", "## Invalid Outputs", ""])
        lines.extend(f"- {item}" for item in report.invalid_outputs)
    if report.blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in report.blockers)
    lines.extend(["", "## Next Commands", "", "```bash"])
    lines.extend(report.next_commands or ["# No next command available."])
    lines.extend(["```", ""])
    return "\n".join(lines)


def _doctor_run_task(config: GapForgeConfig, state: ResearchRunState, task_spec: AgentTaskSpec) -> CodexTaskDoctorReport:
    pack_dir = task_pack_dir(state, task_spec)
    outputs_dir = output_dir_for_task(state, task_spec)
    expected = list(task_spec.required_output_files)
    existing = _existing_outputs(outputs_dir)
    missing = _missing_outputs(expected, outputs_dir)
    invalid = _prevalidation_invalid_outputs(existing, expected)
    validation_status = "not_run_no_outputs"
    if existing:
        validation = AgentOutputImporter(config).validate(task_spec, [])
        validation_status = validation.status
        invalid.extend(_validation_issues(validation.issues))
    import_status = _run_import_status(state, task_spec.id)
    attestation_status = (
        "accepted"
        if any(item.task_spec_id == task_spec.id and item.accepted_as_actual_run for item in state.agent_actual_run_attestations)
        else "missing"
    )
    human_review_status = "present" if state.human_reviews else "missing"
    has_blocking_invalid = _has_blocking_invalid(invalid)
    blockers = _blockers(missing, invalid, validation_status, import_status, attestation_status, human_review_status)
    eligible = (
        not blockers
        and validation_status in _PASSING_VALIDATION_STATUSES
        and import_status == "imported"
        and attestation_status == "accepted"
    )
    return CodexTaskDoctorReport(
        task_id=task_spec.id,
        run_id=task_spec.run_id,
        campaign_id=task_spec.project_id,
        task_pack_path=str(pack_dir),
        outputs_dir=str(outputs_dir),
        expected_files=expected,
        existing_outputs=[str(path) for path in existing],
        missing_outputs=missing,
        invalid_outputs=invalid,
        validation_status=validation_status,
        import_status=import_status,
        attestation_status=attestation_status,
        human_review_status=human_review_status,
        actual_run_eligible=eligible,
        blockers=blockers,
        next_commands=_next_commands(
            task_spec.id,
            task_spec.run_id,
            task_spec.project_id,
            validation_status,
            import_status,
            attestation_status,
            human_review_status,
            has_blocking_invalid,
        ),
        provenance=_doctor_provenance(task_spec.id),
    )


def _doctor_campaign_task(config: GapForgeConfig, state: CampaignState, task_id: str, pack_dir: Path) -> CodexTaskDoctorReport:
    outputs_dir = pack_dir / "outputs"
    expected = expected_campaign_files(task_id)
    existing = _existing_outputs(outputs_dir)
    missing = _missing_outputs(expected, outputs_dir)
    invalid = _prevalidation_invalid_outputs(existing, expected)
    validation_status = "not_run_no_outputs"
    if existing:
        record = CampaignOutputImporter(config).validate(state.campaign.id, task_id, [])
        validation_status = record.status
        invalid.extend(_validation_issues(record.issues))
    latest_import = _latest_campaign_import(state, task_id)
    import_status = latest_import.status if latest_import else "not_imported"
    attestation_status = "accepted" if _campaign_attested(latest_import) else "missing"
    human_review_status = (
        "accepted" if state.acceptance_summary and state.acceptance_summary.accepted else ("present" if state.human_reviews else "missing")
    )
    has_blocking_invalid = _has_blocking_invalid(invalid)
    blockers = _blockers(missing, invalid, validation_status, import_status, attestation_status, human_review_status)
    if state.campaign.mode == "fake_agent":
        blockers.append("Fake-agent campaigns never count as actual Codex/GPT-5.4 acceptance.")
    eligible = (
        not blockers
        and validation_status in _PASSING_VALIDATION_STATUSES
        and import_status in {"applied", "partial", "valid"}
        and attestation_status == "accepted"
        and human_review_status == "accepted"
    )
    return CodexTaskDoctorReport(
        task_id=task_id,
        run_id="",
        campaign_id=state.campaign.id,
        task_pack_path=str(pack_dir),
        outputs_dir=str(outputs_dir),
        expected_files=expected,
        existing_outputs=[str(path) for path in existing],
        missing_outputs=missing,
        invalid_outputs=invalid,
        validation_status=validation_status,
        import_status=import_status,
        attestation_status=attestation_status,
        human_review_status=human_review_status,
        actual_run_eligible=eligible,
        blockers=blockers,
        next_commands=_next_commands(
            task_id,
            "",
            state.campaign.id,
            validation_status,
            import_status,
            attestation_status,
            human_review_status,
            has_blocking_invalid,
        ),
        provenance=_doctor_provenance(task_id),
    )


def _load_run_task(config: GapForgeConfig, task_id: str) -> tuple[ResearchRunState, AgentTaskSpec]:
    manager = ResearchStateManager(config)
    for run_dir in sorted(config.runs_dir.glob("*"), reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            state = manager.load_run(run_dir.name)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        for task_spec in state.agent_task_specs:
            if task_spec.id == task_id:
                return state, task_spec
    raise FileNotFoundError(f"No run-level agent task found for {task_id}")


def _existing_outputs(outputs_dir: Path) -> list[Path]:
    if not outputs_dir.exists():
        return []
    return [path for path in sorted(outputs_dir.iterdir()) if path.is_file()]


def _missing_outputs(expected: list[str], outputs_dir: Path) -> list[str]:
    return [name for name in expected if not (outputs_dir / name).exists()]


def _prevalidation_invalid_outputs(existing: list[Path], expected: list[str]) -> list[str]:
    expected_set = set(expected)
    invalid: list[str] = []
    for path in existing:
        if path.name not in expected_set:
            invalid.append(f"{path.name}: unexpected output file")
        if path.suffix.lower() != ".json" and path.name in expected_set:
            invalid.append(f"{path.name}: expected JSON patch output")
        elif path.suffix.lower() not in {".json", ".md"}:
            invalid.append(f"{path.name}: unsupported output file type")
    return invalid


def _validation_issues(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))


_PASSING_VALIDATION_STATUSES = {"valid", "applied", "partial", "warning"}


def _has_blocking_invalid(invalid: list[str]) -> bool:
    return any(not item.startswith("missing optional output file") for item in invalid)


def _run_import_status(state: ResearchRunState, task_id: str) -> str:
    records = [item for item in state.agent_run_records if item.task_spec_id == task_id and item.status in {"imported", "rejected"}]
    return records[-1].status if records else "not_imported"


def _latest_campaign_import(state: CampaignState, task_id: str):
    matches = [record for record in state.imports if record.task_id == task_id]
    return matches[-1] if matches else None


def _campaign_attested(record) -> bool:  # noqa: ANN001
    if record is None:
        return False
    return any(item.get("type") == "agent_actual_run_attestation" and item.get("accepted") is True for item in record.accepted_objects)


def _blockers(
    missing: list[str],
    invalid: list[str],
    validation_status: str,
    import_status: str,
    attestation_status: str,
    human_review_status: str,
) -> list[str]:
    blockers: list[str] = []
    blocking_invalid = [item for item in invalid if not item.startswith("missing optional output file")]
    if missing and validation_status not in _PASSING_VALIDATION_STATUSES:
        blockers.append("Expected output files are missing.")
    if blocking_invalid:
        blockers.append("Output files need repair before import.")
    if validation_status not in _PASSING_VALIDATION_STATUSES:
        blockers.append("Validation has not passed.")
    if import_status not in {"imported", "applied", "partial", "valid"}:
        blockers.append("Validated output has not been imported.")
    if attestation_status != "accepted":
        blockers.append("Actual Codex/GPT-5.4 attestation is missing.")
    if human_review_status != "accepted":
        blockers.append("Human review acceptance is missing.")
    return blockers


def _next_commands(
    task_id: str,
    run_id: str,
    campaign_id: str,
    validation_status: str,
    import_status: str,
    attestation_status: str,
    human_review_status: str,
    has_invalid: bool,
) -> list[str]:
    commands: list[str] = []
    if validation_status == "not_run_no_outputs":
        commands.append(f"gapforge codex-handoff --task-id {task_id} --print-prompt")
        commands.append("# Run Codex/GPT-5.4 and write the expected JSON files into the outputs directory.")
    if has_invalid:
        commands.append(f"gapforge repair-agent-output --task-id {task_id} --latest-invalid --handoff")
    if campaign_id:
        if validation_status not in _PASSING_VALIDATION_STATUSES:
            commands.append(f"gapforge validate-import-all --task-id {task_id}")
        if import_status not in {"applied", "partial", "valid"}:
            commands.append(f"gapforge validate-import-all --task-id {task_id}")
        if attestation_status != "accepted":
            commands.append(
                f'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
            )
        if human_review_status != "accepted":
            commands.append(f'gapforge campaign-review --campaign-id {campaign_id} --accept --reviewer "<name>"')
    elif run_id:
        if validation_status not in _PASSING_VALIDATION_STATUSES:
            commands.append(f"gapforge validate-import-all --task-id {task_id}")
        if import_status != "imported":
            commands.append(f"gapforge validate-import-all --task-id {task_id}")
        if attestation_status != "accepted":
            commands.append(
                f'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
            )
        if human_review_status != "accepted":
            commands.append('gapforge canary-review --canary-id <canary-id> --accept --reviewer "<name>"')
    return list(dict.fromkeys(commands))


def _doctor_provenance(task_id: str) -> Provenance:
    return Provenance(
        created_by_skill="codex-doctor",
        source_ids=[task_id],
        timestamp=utc_now_iso(),
        reasoning_summary="Diagnosed Codex/GPT-5.4 task-pack outputs, validation, import, attestation, and human review status.",
    )


def doctor_to_json(report: CodexTaskDoctorReport | list[CodexTaskDoctorReport]) -> str:
    return json.dumps(to_plain(report), indent=2) + "\n"
