"""Map the selected benchmark protocol to registered vetted benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks import BenchmarkEligibilityAssessment, VettedBenchmarkRegistry
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord

MAPPING_TYPES = {"direct", "substrate", "auxiliary", "analogy", "sanity_check", "rejected"}


@dataclass(slots=True)
class SelectedBenchmarkVettedMapping:
    id: str
    selected_benchmark_id: str
    vetted_benchmark_id: str
    mapping_type: str = "rejected"
    what_maps: list[str] = field(default_factory=list)
    what_does_not_map: list[str] = field(default_factory=list)
    required_adaptation: list[str] = field(default_factory=list)
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    recommended_experiment_role: str = "not_recommended"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-vetted-benchmark-map"))


@dataclass(slots=True)
class VettedBenchmarkMappingReport:
    id: str
    selected_benchmark_id: str
    mappings: list[SelectedBenchmarkVettedMapping] = field(default_factory=list)
    primary_candidate_ids: list[str] = field(default_factory=list)
    auxiliary_candidate_ids: list[str] = field(default_factory=list)
    rejected_candidate_ids: list[str] = field(default_factory=list)
    conclusion: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-vetted-benchmark-map"))


class SelectedBenchmarkVettedMappingManager:
    """Create selected-benchmark mappings from registered vetted benchmarks."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.selected_manager = SelectedBenchmarkManager(config)
        self.vetted_registry = VettedBenchmarkRegistry(config)

    def map_benchmarks(self, benchmark_id: str, vetted_benchmark_id: str = "") -> VettedBenchmarkMappingReport:
        spec = self.selected_manager.load_spec(benchmark_id)
        records = [self.vetted_registry.load(vetted_benchmark_id)] if vetted_benchmark_id else self.vetted_registry.list()
        mappings = [self._map_record(spec.id, record) for record in records]
        report = VettedBenchmarkMappingReport(
            id=f"selected-vetted-mapping-report-{slugify(spec.id)}",
            selected_benchmark_id=spec.id,
            mappings=mappings,
            primary_candidate_ids=[mapping.vetted_benchmark_id for mapping in mappings if mapping.mapping_type == "direct"],
            auxiliary_candidate_ids=[
                mapping.vetted_benchmark_id
                for mapping in mappings
                if mapping.mapping_type in {"substrate", "auxiliary", "analogy", "sanity_check"}
            ],
            rejected_candidate_ids=[mapping.vetted_benchmark_id for mapping in mappings if mapping.mapping_type == "rejected"],
            conclusion=_report_conclusion(mappings),
            provenance=Provenance(
                created_by_skill="selected-vetted-benchmark-map",
                source_ids=[spec.id, *[record.id for record in records]],
                timestamp=utc_now_iso(),
                reasoning_summary="Mapped existing vetted benchmarks to the selected benchmark without forcing fit.",
            ),
        )
        self._write_report(spec.project_id, report)
        return report

    def load_report(self, benchmark_id: str) -> VettedBenchmarkMappingReport:
        spec = self.selected_manager.load_spec(benchmark_id)
        path = self._mapping_dir(spec.project_id) / "selected_vetted_benchmark_mapping_report.json"
        if not path.exists():
            return self.map_benchmarks(benchmark_id)
        return from_dict(VettedBenchmarkMappingReport, json.loads(path.read_text(encoding="utf-8")))

    def render_report(self, benchmark_id: str) -> str:
        report = self.load_report(benchmark_id)
        markdown = render_vetted_mapping_report(report)
        spec = self.selected_manager.load_spec(benchmark_id)
        (self._mapping_dir(spec.project_id) / "selected_vetted_benchmark_mapping_report.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _map_record(self, selected_benchmark_id: str, record: VettedBenchmarkRecord) -> SelectedBenchmarkVettedMapping:
        assessment = self.vetted_registry.assess_eligibility(
            benchmark_id=record.id,
            selected_idea_id="idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
        )
        mapping_type = _mapping_type(record, assessment)
        return SelectedBenchmarkVettedMapping(
            id=f"selected-vetted-mapping-{slugify(selected_benchmark_id)}-{slugify(record.id)}",
            selected_benchmark_id=selected_benchmark_id,
            vetted_benchmark_id=record.id,
            mapping_type=mapping_type,
            what_maps=_what_maps(mapping_type, assessment, record),
            what_does_not_map=_what_does_not_map(assessment),
            required_adaptation=_required_adaptation(mapping_type, assessment),
            supported_claims=_supported_claims(mapping_type),
            unsupported_claims=_unsupported_claims(mapping_type, assessment),
            recommended_experiment_role=_recommended_role(mapping_type),
            provenance=Provenance(
                created_by_skill="selected-vetted-benchmark-map",
                source_ids=[selected_benchmark_id, record.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Classified vetted benchmark mapping role from recorded eligibility, not benchmark reputation.",
            ),
        )

    def _write_report(self, project_id: str, report: VettedBenchmarkMappingReport) -> None:
        mapping_dir = self._mapping_dir(project_id)
        mapping_dir.mkdir(parents=True, exist_ok=True)
        (mapping_dir / "selected_vetted_benchmark_mapping_report.json").write_text(
            json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8"
        )
        (mapping_dir / "selected_vetted_benchmark_mapping_report.md").write_text(render_vetted_mapping_report(report), encoding="utf-8")
        for mapping in report.mappings:
            (mapping_dir / f"{mapping.id}.json").write_text(json.dumps(to_plain(mapping), indent=2) + "\n", encoding="utf-8")

    def _mapping_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "vetted_mappings"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_vetted_mapping_report(report: VettedBenchmarkMappingReport) -> str:
    lines = [
        f"# Selected Benchmark Vetted Benchmark Mapping `{report.selected_benchmark_id}`",
        "",
        f"- Report ID: `{report.id}`",
        f"- Primary candidates: {_fmt(report.primary_candidate_ids)}",
        f"- Auxiliary candidates: {_fmt(report.auxiliary_candidate_ids)}",
        f"- Rejected candidates: {_fmt(report.rejected_candidate_ids)}",
        "",
        "## Conclusion",
        "",
        report.conclusion or "No conclusion recorded.",
        "",
        "## Manuscript Limitation Feed",
        "",
        "Unsupported claims from these mappings must feed manuscript limitations and cannot be answered by benchmark reputation alone.",
        "",
    ]
    if not report.mappings:
        lines.append("No vetted benchmark mappings are available.")
        return "\n".join(lines).rstrip() + "\n"
    for mapping in report.mappings:
        lines.extend(
            [
                f"## `{mapping.vetted_benchmark_id}`",
                "",
                f"- Mapping type: `{mapping.mapping_type}`",
                f"- Recommended experiment role: `{mapping.recommended_experiment_role}`",
                "",
                "### What Maps",
                "",
                *[f"- {item}" for item in (mapping.what_maps or ["Nothing maps strongly."])],
                "",
                "### What Does Not Map",
                "",
                *[f"- {item}" for item in (mapping.what_does_not_map or ["No mismatch recorded."])],
                "",
                "### Required Adaptation",
                "",
                *[f"- {item}" for item in (mapping.required_adaptation or ["No adaptation recorded."])],
                "",
                "### Supported Claims",
                "",
                *[f"- {item}" for item in (mapping.supported_claims or ["No claims supported."])],
                "",
                "### Unsupported Claims",
                "",
                *[f"- {item}" for item in (mapping.unsupported_claims or ["No unsupported claims recorded."])],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _mapping_type(record: VettedBenchmarkRecord, assessment: BenchmarkEligibilityAssessment) -> str:
    if (
        assessment.can_support_low_fpr
        and assessment.can_support_multi_agent_or_monitoring
        and assessment.can_support_sequential_evaluation
        and assessment.recommended_use in {"primary", "auxiliary"}
    ):
        return "direct"
    if assessment.can_support_multi_agent_or_monitoring and _has_any(
        _record_text(record),
        ["trace", "trajectory", "conversation", "agent"],
    ):
        return "substrate"
    supported_components = sum(
        [
            assessment.can_support_low_fpr,
            assessment.can_support_multi_agent_or_monitoring,
            assessment.can_support_sequential_evaluation,
        ]
    )
    if supported_components >= 1 and assessment.fit_score >= 0.25:
        return "auxiliary"
    if _has_any(_record_text(record), ["anomaly", "screening", "cartel", "covert", "safety"]):
        return "analogy"
    if _has_any(_record_text(record), ["calibration", "baseline", "sanity"]):
        return "sanity_check"
    return "rejected"


def _what_maps(mapping_type: str, assessment: BenchmarkEligibilityAssessment, record: VettedBenchmarkRecord) -> list[str]:
    if mapping_type == "direct":
        return [
            "Sequential monitor/audit evaluation substrate.",
            "Low-FPR or specificity measurement component.",
            "Monitoring/collusion-relevant task framing.",
        ]
    if mapping_type == "substrate":
        return ["Task substrate can host traces, trajectories, conversations, or agent/monitor observations."]
    if mapping_type == "auxiliary":
        mapped = []
        if assessment.can_support_low_fpr:
            mapped.append("Low-FPR, specificity, or false-alarm component.")
        if assessment.can_support_multi_agent_or_monitoring:
            mapped.append("Monitoring, audit, evasion, coordination, or multi-agent component.")
        if assessment.can_support_sequential_evaluation:
            mapped.append("Sequential, online, repeated-window, or time-series component.")
        return mapped or ["One component may be useful, but fit remains limited."]
    if mapping_type == "analogy":
        return [
            "Provides analogy pressure for benchmark validity, anomaly detection, screening, covert coordination, or safety monitoring."
        ]
    if mapping_type == "sanity_check":
        return ["Can sanity-check baseline plumbing, metric implementation, or calibration workflow only."]
    return []


def _what_does_not_map(assessment: BenchmarkEligibilityAssessment) -> list[str]:
    items = []
    if not assessment.can_support_low_fpr:
        items.append("Does not directly support low-FPR specificity claims.")
    if not assessment.can_support_multi_agent_or_monitoring:
        items.append("Does not directly support collusion, multi-agent monitoring, or audit claims.")
    if not assessment.can_support_sequential_evaluation:
        items.append("Does not directly support sequential evaluation or repeated audit windows.")
    return items


def _required_adaptation(mapping_type: str, assessment: BenchmarkEligibilityAssessment) -> list[str]:
    if mapping_type == "rejected":
        return ["Do not adapt unless new evidence changes the fit assessment."]
    adaptations = list(assessment.adaptation_needed)
    adaptations.append("Add manuscript limitation text explaining exactly which selected-benchmark claims remain unsupported.")
    if mapping_type in {"substrate", "auxiliary", "analogy", "sanity_check"}:
        adaptations.append("Use as support for a bounded role only; preserve the new benchmark protocol as necessary.")
    return adaptations


def _supported_claims(mapping_type: str) -> list[str]:
    if mapping_type == "direct":
        return ["Existing vetted benchmark can be evaluated as a direct candidate for bounded sequential low-FPR monitor experiments."]
    if mapping_type == "substrate":
        return ["Existing vetted benchmark can provide a task substrate after adapter construction and limitation review."]
    if mapping_type == "auxiliary":
        return ["Existing vetted benchmark can test one component of the selected benchmark protocol."]
    if mapping_type == "analogy":
        return ["Existing vetted benchmark can motivate validity concerns or analogical evaluation design only."]
    if mapping_type == "sanity_check":
        return ["Existing vetted benchmark can sanity-check adapter, metric, or baseline plumbing."]
    return []


def _unsupported_claims(mapping_type: str, assessment: BenchmarkEligibilityAssessment) -> list[str]:
    claims = [
        "Does not by itself validate the new sequential specificity benchmark.",
        "Does not establish real-world deployment validity.",
        "Does not remove the need for the selected benchmark protocol.",
    ]
    if mapping_type != "direct":
        claims.append("Does not directly evaluate the full low-FPR collusion-audit contribution.")
    claims.extend(_what_does_not_map(assessment))
    return claims


def _recommended_role(mapping_type: str) -> str:
    return {
        "direct": "primary",
        "substrate": "substrate",
        "auxiliary": "auxiliary",
        "analogy": "auxiliary",
        "sanity_check": "sanity_check",
        "rejected": "not_recommended",
    }[mapping_type]


def _report_conclusion(mappings: list[SelectedBenchmarkVettedMapping]) -> str:
    if not mappings:
        return "No vetted benchmarks are registered. Preserve the synthetic benchmark as a protocol contribution."
    if any(mapping.mapping_type == "direct" for mapping in mappings):
        return "At least one vetted benchmark may serve as a direct primary candidate after adapter and limitation review."
    if any(mapping.mapping_type in {"substrate", "auxiliary", "analogy", "sanity_check"} for mapping in mappings):
        return (
            "No direct vetted benchmark is available. Use existing vetted benchmarks as auxiliary or sanity-check evidence while "
            "preserving the new benchmark protocol as the main contribution."
        )
    return (
        "No registered vetted benchmark fits the selected idea. The manuscript should explain why a new benchmark is needed and "
        "preserve synthetic evidence as protocol evidence only."
    )


def _record_text(record: VettedBenchmarkRecord) -> str:
    return " ".join(
        [
            record.name,
            record.domain,
            record.source,
            record.benchmark_type,
            " ".join(record.task_types),
            " ".join(record.dataset_ids),
            " ".join(record.metric_ids),
            " ".join(record.baseline_ids),
            record.citation,
            " ".join(record.limitations),
        ]
    ).lower()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
