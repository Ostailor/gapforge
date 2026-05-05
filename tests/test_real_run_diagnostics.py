from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.canaries import CanaryRunManager
from gapforge.config import GapForgeConfig
from gapforge.diagnostics import (
    build_real_run_diagnostic,
    diagnose_canary_markdown,
    render_real_run_diagnostic_markdown,
    write_real_run_diagnostic,
)


def test_no_env_vars_reports_real_runs_unavailable(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    monkeypatch.delenv("GAPFORGE_AGENT_MODE", raising=False)

    diagnostic = build_real_run_diagnostic(GapForgeConfig.from_cwd(tmp_path))

    assert diagnostic.environment_status.real_runs_enabled is False
    assert diagnostic.environment_status.safe_to_execute_real_agent is False
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in diagnostic.environment_status.missing_env
    assert diagnostic.agent_runtime_status.direct_execution_available is False
    assert any("No human-reviewed actual Codex" in issue for issue in diagnostic.blocking_issues)


def test_task_pack_mode_reports_manual_handoff_available(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_AGENT_MODE", "task-pack")
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)

    diagnostic = build_real_run_diagnostic(GapForgeConfig.from_cwd(tmp_path))

    assert diagnostic.environment_status.agent_mode == "task-pack"
    assert diagnostic.agent_runtime_status.task_pack_available is True
    assert diagnostic.agent_runtime_status.manual_import_available is True
    assert "manual Codex handoff" in diagnostic.agent_runtime_status.recommended_path


def test_fake_agent_mode_is_not_actual_run_acceptance(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_AGENT_MODE", "fake")

    diagnostic = build_real_run_diagnostic(GapForgeConfig.from_cwd(tmp_path))

    assert diagnostic.environment_status.agent_mode == "fake"
    assert diagnostic.agent_runtime_status.fake_agent_available is True
    assert any("Fake-agent mode" in issue for issue in diagnostic.blocking_issues)


def test_invalid_canary_diagnostic_flags_not_passed(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = CanaryRunManager(config).run("low_fpr_collusion_codex", real=False)

    report = diagnose_canary_markdown(config, record.id)

    assert "Counts as actual run: `false`" in report
    assert "not count as actual Codex/GPT-5.4 acceptance" in report


def test_real_run_report_renders_and_writes_artifacts(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    diagnostic = build_real_run_diagnostic(config)

    rendered = render_real_run_diagnostic_markdown(diagnostic)
    json_path, markdown_path, _ = write_real_run_diagnostic(config)

    assert "GapForge Real-Run Diagnostic" in rendered
    assert "Recommended Fixes" in rendered
    assert json_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["version"] == "v0.3"


def test_diagnose_real_run_cli_json(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "diagnose-real-run", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["version"] == "v0.3"
    assert "environment_status" in payload
