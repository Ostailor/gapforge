"""Docker availability checks."""

from __future__ import annotations

import shutil
import subprocess


def detect_docker() -> tuple[bool, list[str]]:
    docker = shutil.which("docker")
    if docker is None:
        return False, ["Docker command was not found."]
    try:
        completed = subprocess.run([docker, "--version"], text=True, capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, [f"Docker version check failed: {exc}"]
    if completed.returncode != 0:
        return False, [completed.stderr.strip() or "Docker command returned a non-zero status."]
    return True, [completed.stdout.strip()]
