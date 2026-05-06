"""Validation for generated experiment code scaffolds."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.experiment_code.smoke import expected_smoke_files, smoke_command


@dataclass(slots=True)
class ExperimentCodeValidation:
    workspace_id: str
    code_root: str
    status: str
    missing_files: list[str] = field(default_factory=list)
    smoke_returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = field(default_factory=list)


def validate_experiment_code(*, workspace_id: str, code_root: Path, run_smoke: bool = True) -> ExperimentCodeValidation:
    missing = [str(path.relative_to(code_root)) for path in expected_smoke_files(code_root) if not path.exists()]
    warnings = _honesty_warnings(code_root)
    if missing:
        return ExperimentCodeValidation(
            workspace_id=workspace_id,
            code_root=str(code_root),
            status="invalid",
            missing_files=missing,
            warnings=warnings,
        )
    if not run_smoke:
        return ExperimentCodeValidation(
            workspace_id=workspace_id,
            code_root=str(code_root),
            status="valid" if not warnings else "warning",
            warnings=warnings,
        )
    env = {**os.environ, "PYTHONPATH": str(code_root / "src")}
    completed = subprocess.run(
        smoke_command(code_root),
        cwd=code_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    status = "valid" if completed.returncode == 0 and not warnings else "warning" if completed.returncode == 0 else "invalid"
    return ExperimentCodeValidation(
        workspace_id=workspace_id,
        code_root=str(code_root),
        status=status,
        smoke_returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        warnings=warnings,
    )


def render_experiment_code_validation(result: ExperimentCodeValidation) -> str:
    lines = [
        f"# Experiment Code Validation `{result.workspace_id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Code root: `{result.code_root}`",
        f"- Smoke return code: `{result.smoke_returncode if result.smoke_returncode is not None else 'not run'}`",
        "",
        "## Missing Files",
        "",
    ]
    lines.extend([f"- `{item}`" for item in result.missing_files] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    if result.stdout:
        lines.extend(["", "## Smoke Stdout", "", "```text", result.stdout.strip(), "```"])
    if result.stderr:
        lines.extend(["", "## Smoke Stderr", "", "```text", result.stderr.strip(), "```"])
    return "\n".join(lines).rstrip() + "\n"


def _honesty_warnings(code_root: Path) -> list[str]:
    warnings: list[str] = []
    for path in code_root.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".py", ".toml", ".sh"}:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "accuracy: 0." in text or "result: 0." in text:
                warnings.append(f"Potential fake result wording in `{path.relative_to(code_root)}`.")
    return warnings
