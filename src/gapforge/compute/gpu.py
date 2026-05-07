"""CUDA/GPU detection that is safe in CI."""

from __future__ import annotations

import os
import shutil
import subprocess


def detect_cuda() -> tuple[bool, int, list[str]]:
    """Detect CUDA GPUs without making them required.

    Tests and local smoke runs can set GAPFORGE_FAKE_CUDA=1 to exercise the
    GPU path without depending on host hardware.
    """

    if os.environ.get("GAPFORGE_FAKE_CUDA") == "1":
        return True, _fake_gpu_count(), ["Using GAPFORGE_FAKE_CUDA fixture override."]

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return False, 0, ["nvidia-smi was not found; CUDA/GPU execution is unavailable."]
    try:
        completed = subprocess.run(
            [nvidia_smi, "-L"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, 0, [f"nvidia-smi check failed: {exc}"]
    if completed.returncode != 0:
        return False, 0, [completed.stderr.strip() or "nvidia-smi returned a non-zero status."]
    count = len([line for line in completed.stdout.splitlines() if line.strip().lower().startswith("gpu ")])
    return count > 0, count, ["CUDA GPUs detected with nvidia-smi."] if count else ["nvidia-smi reported no GPUs."]


def _fake_gpu_count() -> int:
    raw_count = os.environ.get("GAPFORGE_FAKE_GPU_COUNT", "1")
    try:
        return max(1, int(raw_count))
    except ValueError:
        return 1
