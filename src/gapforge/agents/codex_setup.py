"""Codex/GPT-5.4 setup diagnostics for actual-run workflows."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.agents.base import AgentRuntimeConfig
from gapforge.config import GapForgeConfig
from gapforge.models import CodexSetupStatus, Provenance, to_plain
from gapforge.redaction import redact_text
from gapforge.state import utc_now_iso

REQUIRED_DIRECT_PLACEHOLDERS = ("{task_pack}", "{outputs_dir}", "{model}")


def build_codex_setup_status(runtime: AgentRuntimeConfig | None = None) -> CodexSetupStatus:
    cfg = runtime or AgentRuntimeConfig.from_env()
    command = cfg.command_template
    missing_placeholders = [placeholder for placeholder in REQUIRED_DIRECT_PLACEHOLDERS if placeholder not in command]
    missing_env = _missing_env(cfg, command)
    warnings = _warnings(cfg, command, missing_placeholders)
    direct_available = cfg.enable_real_runs and bool(command) and not missing_placeholders
    recommended_mode = _recommended_mode(cfg, direct_available)
    return CodexSetupStatus(
        real_runs_enabled=cfg.enable_real_runs,
        agent_mode=cfg.mode,
        agent_name=cfg.agent_name,
        model=cfg.codex_model,
        codex_command=redact_text(command),
        command_template_valid=bool(command) and not missing_placeholders,
        command_template_missing_placeholders=missing_placeholders,
        direct_available=direct_available,
        task_pack_available=True,
        manual_handoff_available=True,
        fake_available=True,
        recommended_mode=recommended_mode,
        missing_env=missing_env,
        warnings=warnings,
        next_commands=_next_commands(recommended_mode, cfg, missing_placeholders),
        provenance=Provenance(
            created_by_skill="codex-setup",
            source_ids=["environment"],
            timestamp=utc_now_iso(),
            reasoning_summary="Inspected Codex/GPT-5.4 actual-run environment and recommended the safest available execution path.",
        ),
    )


def render_codex_setup_status(status: CodexSetupStatus) -> str:
    lines = [
        "# GapForge Codex Setup",
        "",
        "Fake mode is CI-safe only and never counts as actual Codex/GPT-5.4 acceptance.",
        "",
        "## Current Configuration",
        "",
        f"- Real runs enabled: `{str(status.real_runs_enabled).lower()}`",
        f"- Agent mode: `{status.agent_mode}`",
        f"- Agent name: `{status.agent_name}`",
        f"- Model: `{status.model}`",
        f"- Codex command configured: `{str(bool(status.codex_command)).lower()}`",
        f"- Command template valid: `{str(status.command_template_valid).lower()}`",
        f"- Direct available: `{str(status.direct_available).lower()}`",
        f"- Task-pack available: `{str(status.task_pack_available).lower()}`",
        f"- Manual handoff available: `{str(status.manual_handoff_available).lower()}`",
        f"- Fake available: `{str(status.fake_available).lower()}`",
        f"- Recommended mode: `{status.recommended_mode}`",
    ]
    if status.codex_command:
        lines.append(f"- Codex command: `{status.codex_command}`")
    if status.command_template_missing_placeholders:
        lines.extend(["", "## Missing Command Placeholders", ""])
        lines.extend(f"- `{placeholder}`" for placeholder in status.command_template_missing_placeholders)
    if status.missing_env:
        lines.extend(["", "## Missing Environment", ""])
        lines.extend(f"- `{name}`" for name in status.missing_env)
    if status.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in status.warnings)
    lines.extend(["", "## Next Commands", "", "```bash"])
    lines.extend(status.next_commands or ["gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer"])
    lines.extend(["```", ""])
    return "\n".join(lines)


def write_codex_setup_report(config: GapForgeConfig, status: CodexSetupStatus) -> tuple[Path, Path]:
    output_dir = config.data_dir / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "codex_setup_latest.json"
    markdown_path = output_dir / "codex_setup_latest.md"
    json_path.write_text(json.dumps(to_plain(status), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_codex_setup_status(status), encoding="utf-8")
    return json_path, markdown_path


def _missing_env(cfg: AgentRuntimeConfig, command: str) -> list[str]:
    missing: list[str] = []
    if not cfg.enable_real_runs:
        missing.append("GAPFORGE_ENABLE_REAL_RUNS=1")
    if not cfg.agent_name:
        missing.append("GAPFORGE_AGENT_NAME=codex")
    if not cfg.codex_model:
        missing.append("GAPFORGE_CODEX_MODEL=gpt-5.4")
    if cfg.mode in {"codex", "direct"} and not command:
        missing.append("GAPFORGE_CODEX_COMMAND")
    return missing


def _warnings(cfg: AgentRuntimeConfig, command: str, missing_placeholders: list[str]) -> list[str]:
    warnings: list[str] = []
    if cfg.mode == "fake":
        warnings.append("Fake mode can validate plumbing but never counts as actual Codex/GPT-5.4 acceptance.")
    if command and "{outputs_dir}" in missing_placeholders:
        warnings.append("Command template lacks {outputs_dir}; Codex may not write outputs where validators expect them.")
    if command and "{task_pack}" in missing_placeholders:
        warnings.append("Command template lacks {task_pack}; Codex may not receive the generated task pack.")
    if command and "{model}" in missing_placeholders:
        warnings.append("Command template lacks {model}; configured model may be ignored.")
    if not cfg.enable_real_runs:
        warnings.append("Real runs are disabled; direct Codex execution cannot count as actual-run evidence.")
    if not command:
        warnings.append("No direct Codex command is configured; use task-pack or manual-handoff mode.")
    return warnings


def _recommended_mode(cfg: AgentRuntimeConfig, direct_available: bool) -> str:
    if direct_available and cfg.mode in {"codex", "direct"}:
        return "direct"
    if cfg.mode == "fake":
        return "fake"
    if cfg.mode == "task-pack":
        return "task-pack"
    if cfg.mode == "manual-handoff":
        return "manual-handoff"
    if not cfg.enable_real_runs and not cfg.command_template:
        return "manual-handoff"
    return "task-pack"


def _next_commands(mode: str, cfg: AgentRuntimeConfig, missing_placeholders: list[str]) -> list[str]:
    if mode == "direct":
        return [
            "gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer",
            "gapforge codex-command-preview --task-id <task-id>",
            "gapforge codex-run --task-id <task-id> --direct --dry-run",
            "gapforge codex-doctor --task-id <task-id>",
            "gapforge codex-run --task-id <task-id> --direct --require-direct",
            "gapforge validate-import-all --task-id <task-id>",
            "gapforge codex-doctor --task-id <task-id>",
        ]
    if mode == "fake":
        return [
            "GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression",
            "# Fake-agent output never counts as actual Codex/GPT-5.4 acceptance.",
        ]
    commands = [
        f"export GAPFORGE_AGENT_MODE={'manual-handoff' if mode == 'manual-handoff' else 'task-pack'}",
        "export GAPFORGE_AGENT_NAME=codex",
        "export GAPFORGE_CODEX_MODEL=gpt-5.4",
    ]
    if not cfg.enable_real_runs:
        commands.insert(0, "export GAPFORGE_ENABLE_REAL_RUNS=1")
    if cfg.command_template and missing_placeholders:
        commands.append("# Fix GAPFORGE_CODEX_COMMAND before using direct mode.")
    commands.extend(
        [
            "gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer",
            "gapforge codex-handoff --task-id <task-id> --print-prompt",
            "# Run Codex/GPT-5.4 externally and write JSON outputs to the task outputs directory.",
            "gapforge codex-doctor --task-id <task-id>",
            "gapforge validate-import-all --task-id <task-id>",
            'gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"',
            'gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"',
            "gapforge actual-run-status --campaign-id <campaign-id>",
        ]
    )
    return commands
