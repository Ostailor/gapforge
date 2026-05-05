"""Markdown rendering for actual-run diagnostics."""

from __future__ import annotations

from gapforge.models import RealRunDiagnostic


def render_real_run_diagnostic_markdown(diagnostic: RealRunDiagnostic) -> str:
    env = diagnostic.environment_status
    path = diagnostic.agent_runtime_status
    lines = [
        "# GapForge Real-Run Diagnostic",
        "",
        f"- Diagnostic ID: `{diagnostic.id}`",
        f"- Version: `{diagnostic.version}`",
        f"- Created at: `{diagnostic.created_at}`",
        "",
        "## Environment",
        "",
        f"- Agent mode: `{env.agent_mode}`",
        f"- Agent name: `{env.agent_name}`",
        f"- Codex model: `{env.codex_model}`",
        f"- Real runs enabled: `{str(env.real_runs_enabled).lower()}`",
        f"- Provider LLM mode: `{env.provider_mode}`",
        f"- Required env present: `{str(env.required_env_present).lower()}`",
        f"- Safe to attempt real agent: `{str(env.safe_to_execute_real_agent).lower()}`",
    ]
    if env.missing_env:
        lines.append(f"- Missing env: {', '.join(f'`{item}`' for item in env.missing_env)}")
    if env.notes:
        lines.extend(["", "### Environment Notes", ""])
        lines.extend(f"- {note}" for note in env.notes)

    lines.extend(
        [
            "",
            "## Agent Path",
            "",
            f"- Direct execution available: `{str(path.direct_execution_available).lower()}`",
            f"- Task-pack available: `{str(path.task_pack_available).lower()}`",
            f"- Manual import available: `{str(path.manual_import_available).lower()}`",
            f"- Fake agent available: `{str(path.fake_agent_available).lower()}`",
            f"- Provider LLM available: `{str(path.provider_llm_available).lower()}`",
            f"- Failure reason: {path.failure_reason}",
            f"- Recommended path: {path.recommended_path}",
            "",
            "## Acceptance Signals",
            "",
            f"- Codex execution status: `{diagnostic.codex_execution_status}`",
            f"- Task-pack status: `{diagnostic.task_pack_status}`",
            f"- Import validator status: `{diagnostic.import_validator_status}`",
            f"- Canary status: `{diagnostic.canary_status}`",
        ]
    )

    lines.extend(["", "## Blocking Issues", ""])
    if diagnostic.blocking_issues:
        lines.extend(f"- {issue}" for issue in diagnostic.blocking_issues)
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Recommended Fixes", ""])
    if diagnostic.recommended_fixes:
        for fix in diagnostic.recommended_fixes:
            if fix.startswith("gapforge ") or fix.startswith("export "):
                lines.append(f"- `{fix}`")
            else:
                lines.append(f"- {fix}")
    else:
        lines.append("- No follow-up commands generated.")

    lines.append("")
    return "\n".join(lines)
