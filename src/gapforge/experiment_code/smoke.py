"""Smoke-test command helpers for experiment code scaffolds."""

from __future__ import annotations

from pathlib import Path


def smoke_script_path(code_root: Path) -> Path:
    return code_root / "scripts" / "run_smoke.sh"


def expected_smoke_files(code_root: Path) -> list[Path]:
    return [
        code_root / "pyproject.toml",
        code_root / "README.md",
        code_root / "src" / "data.py",
        code_root / "src" / "baselines.py",
        code_root / "src" / "metrics.py",
        code_root / "src" / "run_experiment.py",
        code_root / "tests" / "test_metrics.py",
        code_root / "tests" / "test_baselines.py",
        code_root / "tests" / "test_data.py",
        code_root / "configs" / "smoke.json",
        code_root / "configs" / "pilot.json",
        smoke_script_path(code_root),
    ]


def smoke_command(code_root: Path) -> list[str]:
    return ["bash", str(smoke_script_path(code_root))]
