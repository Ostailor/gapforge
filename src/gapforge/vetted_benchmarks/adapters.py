"""Adapter models and reports for vetted benchmark substrates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gapforge.models import Provenance

ADAPTER_TYPES = {"direct", "trace_conversion", "label_mapping", "metric_mapping", "monitor_wrapper", "auxiliary"}


@dataclass(slots=True)
class BenchmarkAdapter:
    id: str
    vetted_benchmark_id: str
    selected_benchmark_id: str
    adapter_type: str = "auxiliary"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    transformation_description: str = ""
    limitations: list[str] = field(default_factory=list)
    implementation_path: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-adapter"))


def normalize_adapter_type(value: str) -> str:
    adapter_type = (value or "auxiliary").strip().lower().replace("-", "_")
    return adapter_type if adapter_type in ADAPTER_TYPES else "auxiliary"


def render_benchmark_adapter_report(adapter: BenchmarkAdapter, run_sections: list[str]) -> str:
    lines = [
        f"# Benchmark Adapter `{adapter.id}`",
        "",
        f"- Vetted benchmark: `{adapter.vetted_benchmark_id}`",
        f"- Selected benchmark: `{adapter.selected_benchmark_id}`",
        f"- Adapter type: `{adapter.adapter_type}`",
        f"- Implementation path: {adapter.implementation_path or 'not recorded'}",
        "",
        "## Claim Guardrail",
        "",
        (
            "Adapted datasets are substrate or calibration evidence only. Do not call adapted data real collusion traces unless "
            "the source benchmark explicitly contains real collusion traces and labels."
        ),
        "",
        "## Transformation",
        "",
        adapter.transformation_description or "No transformation description recorded.",
        "",
        "## Input Schema",
        "",
        *[f"- `{key}`: {value}" for key, value in adapter.input_schema.items()],
        "",
        "## Output Schema",
        "",
        *[f"- `{key}`: {value}" for key, value in adapter.output_schema.items()],
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in (adapter.limitations or ["No limitations recorded."])],
    ]
    if run_sections:
        lines.extend(["", "## Runs", "", *run_sections])
    else:
        lines.extend(["", "## Runs", "", "No adapter runs recorded."])
    return "\n".join(lines).rstrip() + "\n"
