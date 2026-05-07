"""Local CPU and memory detection."""

from __future__ import annotations

import os
import platform

from gapforge.models import ComputeEnvironment, Provenance
from gapforge.state import utc_now_iso


def detect_local_environment() -> ComputeEnvironment:
    """Return the always-available local process environment."""

    return ComputeEnvironment(
        id="local",
        name="Local CPU",
        environment_type="local",
        available=True,
        python_version=platform.python_version(),
        cpu_count=os.cpu_count() or 1,
        memory_gb=_memory_gb(),
        notes=["Local execution is CI-safe and does not require GPU, Docker, or Slurm."],
        provenance=Provenance(
            created_by_skill="compute-local",
            timestamp=utc_now_iso(),
            reasoning_summary="Detected local CPU resources without requiring optional accelerators.",
        ),
    )


def _memory_gb() -> float:
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError):
            return 0.0
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0 and page_size > 0:
            return round((pages * page_size) / (1024**3), 2)
    return 0.0
