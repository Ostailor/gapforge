"""Human-oriented setup guidance for real Codex/GPT-5.4 runs."""

from __future__ import annotations

from gapforge.agents.base import AgentRuntimeConfig, agent_capabilities, agent_status


def render_real_run_setup(runtime: AgentRuntimeConfig | None = None) -> str:
    """Render current real-run configuration and next steps."""
    cfg = runtime or AgentRuntimeConfig.from_env()
    status = agent_status(cfg)
    capabilities = agent_capabilities(cfg)
    lines = [
        "# GapForge Real-Run Setup",
        "",
        "GapForge supports three practical actual-run paths:",
        "",
        "- `direct`: GapForge invokes a configured Codex command and validates outputs before import.",
        "- `task-pack`: GapForge writes a task pack; Codex/GPT-5.4 runs externally; GapForge validates/imports outputs.",
        "- `manual-handoff`: same validation path as task-pack, with a checklist and attestation instructions.",
        "",
        "Fake-agent mode is CI-safe only and never counts as actual Codex/GPT-5.4 acceptance.",
        "",
        "## Current Status",
        "",
    ]
    for key in [
        "mode",
        "execution_method",
        "agent_name",
        "codex_model",
        "real_runs_enabled",
        "codex_execution_available",
        "runner_command_configured",
        "codex_command_configured",
        "codex_workdir",
        "codex_timeout_seconds",
    ]:
        lines.append(f"- {key}: `{status.get(key)}`")

    lines.extend(["", "## Required Environment", ""])
    required = [
        ("GAPFORGE_AGENT_MODE", "task-pack, manual-handoff, direct, codex, or fake"),
        ("GAPFORGE_AGENT_NAME", "codex"),
        ("GAPFORGE_CODEX_MODEL", "gpt-5.4"),
        ("GAPFORGE_ENABLE_REAL_RUNS", "1 for direct or release-counted real runs"),
        ("GAPFORGE_CODEX_COMMAND", "direct runner command template; must write to {outputs_dir}"),
        ("GAPFORGE_CODEX_WORKDIR", "optional direct runner working directory"),
        ("GAPFORGE_CODEX_TIMEOUT_SECONDS", "optional direct runner timeout"),
    ]
    lines.extend(f"- `{name}`: {description}" for name, description in required)

    lines.extend(["", "## Runtime Capabilities", ""])
    for capability in capabilities:
        availability = "available" if capability.available else "unavailable"
        counts = "can count as actual run" if capability.can_count_as_actual_run else "does not count as actual run"
        lines.append(f"- `{capability.mode}`: {availability}; {counts}. {capability.reason}")

    lines.extend(
        [
            "",
            "## Recommended Commands",
            "",
            "Task-pack/handoff path:",
            "",
            "```bash",
            "export GAPFORGE_AGENT_MODE=task-pack",
            "export GAPFORGE_AGENT_NAME=codex",
            "export GAPFORGE_CODEX_MODEL=gpt-5.4",
            "gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer",
            "gapforge codex-handoff --task-id <task-id> --print-prompt",
            "gapforge validate-import-all --task-id <task-id>",
            'gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"',
            'gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"',
            "```",
            "",
            "Direct path:",
            "",
            "```bash",
            "export GAPFORGE_ENABLE_REAL_RUNS=1",
            "export GAPFORGE_AGENT_MODE=direct",
            "export GAPFORGE_CODEX_MODEL=gpt-5.4",
            "export GAPFORGE_CODEX_COMMAND='<command that reads {task_pack} and writes JSON to {outputs_dir}>'",
            "gapforge codex-command-preview --task-id <task-id>",
            "gapforge codex-run --task-id <task-id> --direct --dry-run",
            "gapforge codex-run --task-id <task-id> --direct --require-direct",
            "```",
            "",
            "Diagnostics:",
            "",
            "```bash",
            "gapforge diagnose-real-run --write-report",
            "gapforge agent-capabilities",
            "```",
            "",
        ]
    )
    return "\n".join(lines)
