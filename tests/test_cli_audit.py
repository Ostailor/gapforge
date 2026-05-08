from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.cli import build_parser
from gapforge.cli_audit import CLICommandAuditor, render_cli_command_audit
from gapforge.config import GapForgeConfig

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "gapforge.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_audit_runs(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "cli-audit")

    assert result.returncode == 0, result.stderr
    assert "# GapForge CLI Usability Audit" in result.stdout
    assert "## Command Groups" in result.stdout


def test_cli_audit_all_commands_have_help(tmp_path: Path) -> None:
    audit = CLICommandAuditor(GapForgeConfig.from_cwd(tmp_path)).audit(build_parser())

    assert audit.command_count > 100
    assert audit.missing_help == []


def test_deprecated_alias_works(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "v1-gate", "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["recommended_next_version"] == "v0.9"


def test_project_alias_preserves_backward_compatibility(tmp_path: Path) -> None:
    old = run_cli(tmp_path, "list-projects")
    alias = run_cli(tmp_path, "project-list")

    assert old.returncode == 0, old.stderr
    assert alias.returncode == 0, alias.stderr
    assert old.stdout == alias.stdout


def test_command_groups_render(tmp_path: Path) -> None:
    audit = CLICommandAuditor(GapForgeConfig.from_cwd(tmp_path)).audit(build_parser())
    rendered = render_cli_command_audit(audit)

    for group in ["project", "campaign", "literature", "codex", "experiment", "benchmark", "manuscript", "release-gate", "safety"]:
        assert f"### {group}" in rendered
        assert audit.command_groups[group]


def test_cli_audit_write_report_marks_release_gate(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "cli-audit", "--write-report")

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "data" / "release_gate" / "cli_audit.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert (tmp_path / "data" / "cli_audit" / "cli_audit_latest.md").exists()
