"""Slurm availability checks."""

from __future__ import annotations

import shutil


def detect_slurm() -> tuple[bool, list[str]]:
    commands = [name for name in ("sbatch", "squeue", "srun") if shutil.which(name)]
    if not commands:
        return False, ["No Slurm commands were found on PATH."]
    return True, [f"Found Slurm commands: {', '.join(commands)}."]
