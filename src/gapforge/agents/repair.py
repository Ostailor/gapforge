"""Repair guidance for invalid agent/Codex output patches."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.agents.handoff import write_handoff
from gapforge.agents.output_importer import AgentOutputImporter, output_paths_for_task
from gapforge.agents.records import task_pack_dir
from gapforge.agents.schema_validator import expected_output_files, expected_output_schema
from gapforge.agents.task_spec import create_agent_task_spec
from gapforge.config import GapForgeConfig
from gapforge.models import AgentRepairRecord, AgentTaskSpec, AgentValidationResult, CampaignImportRecord, Provenance, to_plain
from gapforge.state import ResearchStateManager, slugify, utc_now_compact, utc_now_iso


def create_agent_repair_task(
    config: GapForgeConfig,
    task_spec: AgentTaskSpec,
    output_paths: list[Path],
    *,
    handoff: bool = False,
) -> tuple[AgentRepairRecord | None, AgentValidationResult, Path | None]:
    """Validate output and create a repair task pack when validation fails."""
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(task_spec.run_id)
    validation = AgentOutputImporter(config).validate(task_spec, output_paths)
    state = state_manager.load_run(task_spec.run_id)
    if validation.status == "valid":
        return None, validation, None

    repair_task = _repair_task_spec(state, task_spec, validation)
    state.agent_task_specs.append(repair_task)
    record = AgentRepairRecord(
        id=f"agent-repair-{utc_now_compact()}-{slugify(task_spec.id)}",
        original_task_id=task_spec.id,
        validation_result_id=validation.id,
        repair_task_id=repair_task.id,
        status="created",
        issues_to_fix=list(validation.issues),
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="agent-output-repair",
            source_ids=[task_spec.id, validation.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Created a validation-gated repair task from invalid agent output without weakening validation.",
        ),
    )
    state.agent_repair_records.append(record)
    state_manager.save_run(state)

    from gapforge.agents.task_packs import write_codex_task_pack

    pack_dir = write_codex_task_pack(state, repair_task)
    repair_context = _repair_context(task_spec, repair_task, validation, output_paths)
    (pack_dir / "repair_context.json").write_text(json.dumps(repair_context, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "REPAIR.md").write_text(
        render_agent_repair_instructions(
            task_id=task_spec.id,
            output_paths=[Path(path) for path in validation.rejected_output_paths] or output_paths,
            issues=validation.issues,
            expected_files=expected_output_files(task_spec),
            outputs_dir=output_paths_for_task(state, repair_task)[0].parent,
        ),
        encoding="utf-8",
    )
    if handoff:
        write_handoff(repair_task, pack_dir)
    return record, validation, pack_dir


def find_agent_repair_record(config: GapForgeConfig, repair_id: str) -> tuple[AgentRepairRecord, Path]:
    manager = ResearchStateManager(config)
    for run_dir in sorted(config.runs_dir.glob("*"), reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            state = manager.load_run(run_dir.name)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        for record in state.agent_repair_records:
            if record.id == repair_id:
                return record, run_dir
    raise FileNotFoundError(f"No agent repair record found for {repair_id}")


def render_agent_repair_instructions(
    *,
    task_id: str,
    output_paths: list[Path],
    issues: list[str],
    expected_files: list[str],
    outputs_dir: Path | None = None,
) -> str:
    """Render actionable repair instructions for a failed output validation."""
    lines = [
        f"# GapForge Agent Output Repair: `{task_id}`",
        "",
        "Validation failed or returned warnings. Do not import this output until the issues below are fixed.",
        "",
        "## Output Paths Checked",
        "",
    ]
    if output_paths:
        lines.extend(f"- `{path}`" for path in output_paths)
    else:
        lines.append("- No explicit paths were supplied; GapForge checked the task `outputs/` directory.")
    if outputs_dir is not None:
        lines.extend(["", "## Expected Output Directory", "", f"`{outputs_dir}`"])
    lines.extend(["", "## Expected Files", ""])
    lines.extend(f"- `{name}`" for name in expected_files)
    lines.extend(["", "## Validation Issues", ""])
    lines.extend(f"- {issue}" for issue in issues) if issues else lines.append("- No blocking issues were reported.")
    lines.extend(
        [
            "",
            "## Repair Rules",
            "",
            "- Keep the same filenames and required top-level JSON keys.",
            "- Remove or downgrade unsupported high-confidence claims.",
            "- Replace unknown paper IDs with known IDs from the task manifest, or move them into a search request.",
            "- Replace fake citations with known paper IDs; do not invent bibliographic entries.",
            "- Add EvidenceSpan IDs or locators for supported claims, results, limitations, and novelty comparisons.",
            "- For novelty, list closest prior work or set the verdict to `unknown` with missing searches.",
            "- Harmless extra fields are allowed when they do not introduce unsupported claims or fake citations.",
            "",
            "## Re-run Validation",
            "",
            "```bash",
            f"gapforge repair-agent-output --task-id {task_id} --path <fixed-output.json>",
            f"gapforge validate-agent-output --task-id {task_id}",
            f"gapforge import-agent-output --task-id {task_id}",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def repair_from_agent_validation(
    task_id: str,
    validation: AgentValidationResult,
    *,
    expected_files: list[str],
    outputs_dir: Path | None = None,
) -> str:
    paths = [Path(path) for path in [*validation.accepted_output_paths, *validation.rejected_output_paths]]
    return render_agent_repair_instructions(
        task_id=task_id,
        output_paths=paths,
        issues=validation.issues,
        expected_files=expected_files,
        outputs_dir=outputs_dir,
    )


def render_agent_repair_status(record: AgentRepairRecord, run_dir: Path) -> str:
    pack_dir = run_dir / "agent_tasks" / record.repair_task_id
    lines = [
        f"# Agent Repair Status: `{record.id}`",
        "",
        f"- Original task: `{record.original_task_id}`",
        f"- Validation result: `{record.validation_result_id}`",
        f"- Repair task: `{record.repair_task_id}`",
        f"- Status: `{record.status}`",
        f"- Task pack: `{pack_dir}`",
        "",
        "## Issues To Fix",
        "",
    ]
    lines.extend(f"- {issue}" for issue in record.issues_to_fix) if record.issues_to_fix else lines.append("- None recorded.")
    lines.extend(
        [
            "",
            "## Next Commands",
            "",
            "```bash",
            f"gapforge task-handoff --task-id {record.repair_task_id}",
            f"gapforge validate-agent-output --task-id {record.repair_task_id}",
            f"gapforge import-agent-output --task-id {record.repair_task_id}",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def repair_from_campaign_validation(
    task_id: str,
    record: CampaignImportRecord,
    *,
    expected_files: list[str],
    outputs_dir: Path | None = None,
) -> str:
    paths = [Path(path) for path in record.input_paths]
    issues = [*record.issues, *(f"{item.get('id')}: {item.get('reason')}" for item in record.rejected_objects)]
    return render_agent_repair_instructions(
        task_id=task_id,
        output_paths=paths,
        issues=issues,
        expected_files=expected_files,
        outputs_dir=outputs_dir,
    )


def _repair_task_spec(state, original: AgentTaskSpec, validation: AgentValidationResult) -> AgentTaskSpec:  # noqa: ANN001
    repair = create_agent_task_spec(
        state,
        skill_name=original.skill_name,
        gap_id=_target_id(original),
        project_id=original.project_id,
        instructions=_repair_instructions(original, validation),
    )
    repair.id = f"repair-{utc_now_compact()}-{slugify(original.id)}"
    repair.task_type = original.task_type
    repair.output_schema_name = original.output_schema_name
    repair.required_output_files = list(original.required_output_files)
    repair.input_artifacts = _repair_input_artifacts(state, original, validation)
    repair.evidence_rules = list(original.evidence_rules)
    repair.uncertainty_rules = [
        *original.uncertainty_rules,
        "If a missing citation cannot be resolved to known paper IDs, convert it to a search request or mark the claim unknown.",
        "Do not invent missing evidence to satisfy validation.",
    ]
    repair.provenance = Provenance(
        created_by_skill="agent-output-repair",
        source_ids=[original.id, validation.id],
        timestamp=utc_now_iso(),
        reasoning_summary="Created a repair task that asks Codex to correct validation failures while preserving strict evidence rules.",
    )
    return repair


def _repair_instructions(original: AgentTaskSpec, validation: AgentValidationResult) -> str:
    issues = "\n".join(f"- {issue}" for issue in validation.issues) or "- No explicit issues were recorded."
    accepted = "\n".join(f"- {path}" for path in validation.accepted_output_paths) or "- None."
    rejected = "\n".join(f"- {path}" for path in validation.rejected_output_paths) or "- None."
    return f"""Repair the output for original task `{original.id}`.

Validation failed. Correct only the output JSON/Markdown files; do not weaken claims to bypass validation.

Validation errors:
{issues}

Accepted fields/files that may be preserved if still valid:
{accepted}

Rejected fields/files that must be corrected:
{rejected}

Rules:
- Keep the same expected output filenames and top-level schema.
- Do not invent citations, paper IDs, EvidenceSpan IDs, results, or prior work.
- Missing citations must become search requests or uncertainty, not fabricated references.
- Unsupported high-confidence claims must be downgraded or supported by valid evidence locators.
- Store public reasoning summaries only; do not include hidden chain-of-thought.
"""


def _repair_input_artifacts(state, original: AgentTaskSpec, validation: AgentValidationResult) -> list[str]:  # noqa: ANN001
    pack_dir = task_pack_dir(state, original)
    artifacts = [
        *original.input_artifacts,
        str(pack_dir / "TASK.md"),
        str(pack_dir / "input_manifest.json"),
        str(pack_dir / "expected_output_schema.json"),
        str(pack_dir / "validation.json"),
        *validation.accepted_output_paths,
        *validation.rejected_output_paths,
    ]
    return [path for path in dict.fromkeys(artifacts) if path]


def _repair_context(
    original: AgentTaskSpec,
    repair_task: AgentTaskSpec,
    validation: AgentValidationResult,
    output_paths: list[Path],
) -> dict[str, object]:
    return {
        "original_task": to_plain(original),
        "repair_task": to_plain(repair_task),
        "validation": to_plain(validation),
        "output_paths_checked": [str(path) for path in output_paths],
        "schema": expected_output_schema(original),
        "repair_rules": [
            "Repair cannot bypass validation.",
            "Do not invent evidence or citations.",
            "Use known IDs from the original task manifest.",
            "Convert unresolved citations into search requests or uncertainty.",
        ],
    }


def _target_id(task_spec: AgentTaskSpec) -> str:
    for source_id in task_spec.provenance.source_ids:
        if source_id:
            return source_id
    return ""
