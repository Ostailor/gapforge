"""Task-pack and run-record helpers for AgentClient implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from gapforge.models import AgentRunRecord, AgentTaskSpec, AgentValidationResult, ResearchRunState
from gapforge.redaction import redact_text


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def task_pack_dir(state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
    return Path(state.run_dir) / "agent_tasks" / task_spec.id


def output_dir_for_task(state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
    return task_pack_dir(state, task_spec) / "outputs"


def write_task_pack(state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
    from gapforge.agents.task_packs import write_codex_task_pack

    return write_codex_task_pack(state, task_spec)


def render_task_pack_markdown(state: ResearchRunState, task_spec: AgentTaskSpec) -> str:
    lines = [
        f"# GapForge Agent Task: {task_spec.skill_name}",
        "",
        f"- Task ID: `{task_spec.id}`",
        f"- Run ID: `{task_spec.run_id}`",
        f"- Project ID: `{task_spec.project_id or 'none'}`",
        f"- Task type: `{task_spec.task_type}`",
        f"- Output schema: `{task_spec.output_schema_name or 'unspecified'}`",
        "- Model default for Codex actual runs: `gpt-5.4` unless configured otherwise",
        "",
        "## Instructions",
        "",
        redact_text(task_spec.instructions).strip() or "No task-specific instructions were supplied.",
        "",
        "## Input Artifacts",
        "",
    ]
    lines.extend(f"- `{artifact}`" for artifact in task_spec.input_artifacts)
    if not task_spec.input_artifacts:
        lines.append("- none")
    lines.extend(["", "## Required Output Files", ""])
    lines.extend(f"- `{filename}`" for filename in task_spec.required_output_files)
    if not task_spec.required_output_files:
        lines.append("- none")
    lines.extend(["", "## Evidence Rules", ""])
    lines.extend(f"- {rule}" for rule in task_spec.evidence_rules)
    lines.extend(["", "## Uncertainty Rules", ""])
    lines.extend(f"- {rule}" for rule in task_spec.uncertainty_rules)
    lines.extend(
        [
            "",
            "## Output Contract",
            "",
            "Return JSON that matches the named schema. Cite existing paper IDs and EvidenceSpan locators.",
            "Do not invent citations, paper IDs, evidence spans, prior work, or results.",
            "Store concise public reasoning summaries only; do not store hidden chain-of-thought.",
            "",
            "## Run Snapshot",
            "",
            f"- Topic: {state.topic.text}",
            f"- Papers: {len(state.papers)}",
            f"- Evidence spans: {len(state.evidence_spans)}",
            f"- Claims: {len(state.claims)}",
            f"- Gaps: {len(state.gaps)}",
            f"- Novelty dossiers: {len(state.novelty_dossiers)}",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def append_validation_result(state: ResearchRunState, result: AgentValidationResult) -> None:
    state.agent_validation_results = [item for item in state.agent_validation_results if item.id != result.id]
    state.agent_validation_results.append(result)


def append_run_record(state: ResearchRunState, record: AgentRunRecord) -> None:
    state.agent_run_records = [item for item in state.agent_run_records if item.id != record.id]
    state.agent_run_records.append(record)
