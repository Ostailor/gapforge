"""Adapter models and reports for vetted benchmark substrates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gapforge.models import Provenance

ADAPTER_TYPES = {"direct", "trace_conversion", "label_mapping", "metric_mapping", "monitor_wrapper", "auxiliary", "sanity_check"}


@dataclass(slots=True)
class BenchmarkAdapter:
    id: str
    vetted_benchmark_id: str
    selected_benchmark_id: str
    candidate_benchmark_id: str = ""
    adapter_type: str = "auxiliary"
    evidence_label: str = "vetted_adapter"
    expected_claim_support: str = "auxiliary"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    transformation_description: str = ""
    limitations: list[str] = field(default_factory=list)
    implementation_path: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-adapter"))


@dataclass(slots=True)
class RealBenchmarkAdapterAssessment:
    id: str
    candidate_benchmark_id: str
    selected_benchmark_id: str
    adapter_possible: bool = False
    adapter_type: str = "auxiliary"
    schema_mismatches: list[str] = field(default_factory=list)
    label_mismatches: list[str] = field(default_factory=list)
    sequentialization_needed: bool = False
    observability_mapping: list[str] = field(default_factory=list)
    expected_claim_support: str = "no_fit"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="real-benchmark-adapter-assessment"))


def normalize_adapter_type(value: str) -> str:
    adapter_type = (value or "auxiliary").strip().lower().replace("-", "_")
    return adapter_type if adapter_type in ADAPTER_TYPES else "auxiliary"


def render_benchmark_adapter_report(adapter: BenchmarkAdapter, run_sections: list[str]) -> str:
    lines = [
        f"# Benchmark Adapter `{adapter.id}`",
        "",
        f"- Vetted benchmark: `{adapter.vetted_benchmark_id}`",
        f"- Real candidate benchmark: `{adapter.candidate_benchmark_id or 'none'}`",
        f"- Selected benchmark: `{adapter.selected_benchmark_id}`",
        f"- Adapter type: `{adapter.adapter_type}`",
        f"- Evidence label: `{adapter.evidence_label}`",
        f"- Expected claim support: `{adapter.expected_claim_support}`",
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


def render_real_benchmark_adapter_assessment(assessment: RealBenchmarkAdapterAssessment) -> str:
    lines = [
        f"# Real Benchmark Adapter Assessment `{assessment.candidate_benchmark_id}`",
        "",
        f"- Selected benchmark: `{assessment.selected_benchmark_id}`",
        f"- Adapter possible: {str(assessment.adapter_possible).lower()}",
        f"- Adapter type: `{assessment.adapter_type}`",
        f"- Sequentialization needed: {str(assessment.sequentialization_needed).lower()}",
        f"- Expected claim support: `{assessment.expected_claim_support}`",
        "",
        "## Observability Mapping",
        "",
        *[f"- {item}" for item in (assessment.observability_mapping or ["No observability mapping recorded."])],
        "",
        "## Schema Mismatches",
        "",
        *[f"- {item}" for item in (assessment.schema_mismatches or ["none"])],
        "",
        "## Label Mismatches",
        "",
        *[f"- {item}" for item in (assessment.label_mismatches or ["none"])],
        "",
        "## Blockers",
        "",
        *[f"- {item}" for item in (assessment.blockers or ["none"])],
        "",
        "## Claim Boundary",
        "",
        "- Strong claims require direct mapping to collusion/monitoring labels and sequential low-FPR evaluation.",
        "- Sanity-check adapters must keep their outputs labeled `sanity_check`.",
        "- Artificial sequentialization is a warning, not evidence of native sequential validity.",
    ]
    return "\n".join(lines).rstrip() + "\n"
