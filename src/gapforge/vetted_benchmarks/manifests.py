"""Run manifests for vetted benchmark adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance

ADAPTER_RUN_STATUSES = {"planned", "running", "complete", "failed"}


@dataclass(slots=True)
class BenchmarkAdapterRun:
    id: str
    adapter_id: str
    dataset_id: str
    status: str = "planned"
    output_dataset_id: str = ""
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-adapter-run"))


def normalize_adapter_run_status(value: str) -> str:
    status = (value or "planned").strip().lower().replace("-", "_")
    return status if status in ADAPTER_RUN_STATUSES else "failed"


def render_adapter_run_section(run: BenchmarkAdapterRun, output_path: str = "") -> str:
    lines = [
        f"### `{run.id}`",
        "",
        f"- Status: `{run.status}`",
        f"- Dataset: `{run.dataset_id}`",
        f"- Output dataset id: `{run.output_dataset_id or 'none'}`",
        f"- Output artifact: {output_path or 'not recorded'}",
    ]
    if run.warnings:
        lines.extend(["", "Warnings:", "", *[f"- {item}" for item in run.warnings]])
    return "\n".join(lines).rstrip()
