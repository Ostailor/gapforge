"""Actual-run postmortem and diagnosis helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gapforge.canaries import CanaryReviewManager, CanaryRunManager
from gapforge.config import GapForgeConfig
from gapforge.diagnostics.agent_path import inspect_agent_path
from gapforge.diagnostics.environment import inspect_agent_environment
from gapforge.diagnostics.report import render_real_run_diagnostic_markdown
from gapforge.models import Provenance, RealRunDiagnostic, to_plain
from gapforge.state import ResearchStateManager

_V03_ACCEPTANCE_DOCS = (
    "docs/V0_3_REAL_RUN_ACCEPTANCE.md",
    "docs/releases/v0.3.0-real-run-acceptance.md",
)


def build_real_run_diagnostic(config: GapForgeConfig | None = None) -> RealRunDiagnostic:
    cfg = config or GapForgeConfig.from_env_or_cwd()
    environment_status = inspect_agent_environment()
    path_status = inspect_agent_path()
    acceptance = CanaryReviewManager(cfg).real_run_acceptance()
    doc_status = _read_v03_acceptance_docs(cfg.root)

    blocking_issues: list[str] = []
    if not environment_status.safe_to_execute_real_agent:
        blocking_issues.append("Real Codex/GPT-5.4 execution environment is not fully enabled.")
    if not path_status.direct_execution_available:
        blocking_issues.append("Direct Codex execution is unavailable in the current AgentClient implementation.")
    if environment_status.agent_mode == "fake":
        blocking_issues.append("Fake-agent mode validates CI integration only and cannot satisfy actual-run acceptance.")
    if not acceptance.get("passed"):
        blocking_issues.append("No human-reviewed actual Codex/GPT-5.4 canary has been accepted.")
    if doc_status == "not_completed":
        blocking_issues.append("v0.3 release documentation records actual-run acceptance as not completed.")

    recommended_fixes = _recommended_fixes(environment_status.agent_mode, path_status.direct_execution_available)
    canary_status = "passed" if acceptance.get("passed") else "not_passed"
    missing_acceptance = acceptance.get("missing")
    if isinstance(missing_acceptance, list):
        canary_status += f": {'; '.join(str(item) for item in missing_acceptance)}"

    return RealRunDiagnostic(
        id=f"realrun-{uuid4().hex[:12]}",
        version="v0.3",
        created_at=datetime.now(UTC).isoformat(),
        environment_status=environment_status,
        agent_runtime_status=path_status,
        codex_execution_status="available" if path_status.direct_execution_available else "unavailable",
        task_pack_status="available" if path_status.task_pack_available else "unavailable",
        import_validator_status="available" if path_status.manual_import_available else "unavailable",
        canary_status=canary_status,
        blocking_issues=blocking_issues,
        recommended_fixes=recommended_fixes,
        provenance=Provenance(
            created_by_skill="real-run-diagnostics",
            reasoning_summary=(
                "Inspected environment variables, AgentClient path capabilities, canary acceptance records, and v0.3 acceptance docs."
            ),
        ),
    )


def write_real_run_diagnostic(config: GapForgeConfig | None = None) -> tuple[Path, Path, RealRunDiagnostic]:
    cfg = config or GapForgeConfig.from_env_or_cwd()
    diagnostic = build_real_run_diagnostic(cfg)
    output_dir = cfg.data_dir / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "real_run_diagnostic_latest.json"
    markdown_path = output_dir / "real_run_diagnostic_latest.md"
    json_path.write_text(json.dumps(to_plain(diagnostic), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_real_run_diagnostic_markdown(diagnostic), encoding="utf-8")
    return json_path, markdown_path, diagnostic


def diagnose_run_agent_markdown(config: GapForgeConfig, run_id: str) -> str:
    manager = ResearchStateManager(config)
    state = manager.load_run(run_id)
    diagnostic = build_real_run_diagnostic(config)
    lines = [
        f"# Agent Diagnosis for Run `{run_id}`",
        "",
        f"- Topic: {state.topic.text}",
        f"- Agent task specs: `{len(state.agent_task_specs)}`",
        f"- Agent run records: `{len(state.agent_run_records)}`",
        f"- Agent validations: `{len(state.agent_validation_results)}`",
        f"- Direct Codex execution: `{diagnostic.codex_execution_status}`",
        f"- Recommended path: {diagnostic.agent_runtime_status.recommended_path}",
        "",
        "## Validation Status",
        "",
    ]
    if not state.agent_validation_results:
        lines.append("- No agent outputs have been validated for this run.")
    else:
        for validation in state.agent_validation_results[-10:]:
            lines.append(f"- `{validation.id}` for task `{validation.task_spec_id}`: `{validation.status}`")
    lines.extend(["", "## Next Commands", ""])
    lines.extend(f"- `{command}`" for command in _recommended_fixes(diagnostic.environment_status.agent_mode, False))
    lines.append("")
    return "\n".join(lines)


def diagnose_canary_markdown(config: GapForgeConfig, canary_id: str) -> str:
    run_manager = CanaryRunManager(config)
    review_manager = CanaryReviewManager(config)
    record = run_manager.load_record(canary_id)
    summary = review_manager.summary(canary_id)
    counts_as_actual = bool(record.validation_summary.get("counts_as_actual_run"))
    lines = [
        f"# Canary Diagnosis `{canary_id}`",
        "",
        f"- Profile: `{record.profile_id}`",
        f"- Status: `{record.status}`",
        f"- Counts as actual run: `{str(counts_as_actual).lower()}`",
        f"- Human review ID: `{record.human_review_id or 'none'}`",
        f"- Acceptance summary: `{summary.release_gate_status}`",
        "",
        "## Blocking Failures",
        "",
    ]
    blocking = list(summary.blocking_failures)
    if not counts_as_actual:
        blocking.append("This canary does not count as actual Codex/GPT-5.4 acceptance.")
    if record.status in {"failed", "rejected"}:
        blocking.append(f"Canary record status is {record.status}.")
    if blocking:
        lines.extend(f"- {issue}" for issue in blocking)
    else:
        lines.append("- None detected.")
    lines.extend(["", "## Next Commands", ""])
    if record.status == "failed":
        lines.append(f"- `gapforge canary-plan --profile {record.profile_id}`")
    lines.append(f"- `gapforge canary-review --canary-id {canary_id}`")
    lines.append(f"- `gapforge canary-summary --canary-id {canary_id}`")
    lines.append("")
    return "\n".join(lines)


def _read_v03_acceptance_docs(root: Path) -> str:
    found = False
    for relative_path in _V03_ACCEPTANCE_DOCS:
        path = root / relative_path
        if not path.exists():
            continue
        found = True
        text = path.read_text(encoding="utf-8").lower()
        if "actual-run acceptance not completed" in text or "not completed" in text:
            return "not_completed"
        if "actual-run acceptance passed" in text:
            return "passed"
    return "missing" if not found else "unknown"


def _recommended_fixes(agent_mode: str, direct_execution_available: bool) -> list[str]:
    fixes = [
        "gapforge diagnose-real-run --write-report",
        "gapforge canary-list",
    ]
    if not direct_execution_available:
        fixes.extend(
            [
                "export GAPFORGE_AGENT_MODE=task-pack",
                "gapforge codex-task --run-id <run-id> --skill novelty-gate --gap-id <gap-id>",
                "gapforge validate-agent-output --task-id <task-id>",
                "gapforge import-agent-output --task-id <task-id>",
            ]
        )
    if agent_mode != "codex":
        fixes.append("export GAPFORGE_AGENT_MODE=codex")
    fixes.extend(
        [
            "export GAPFORGE_ENABLE_REAL_RUNS=1",
            "gapforge canary-run --profile low_fpr_collusion_codex --real",
            "gapforge canary-review --canary-id <canary-id> --reviewer <name> --accept",
            "gapforge real-run-acceptance",
        ]
    )
    return fixes
