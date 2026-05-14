"""Cards and Markdown rendering for vetted benchmark records."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord, source_visibility_warnings


@dataclass(slots=True)
class VettedBenchmarkCard:
    benchmark_id: str
    why_vetted: str = ""
    intended_use: str = ""
    standard_metrics: list[str] = field(default_factory=list)
    standard_splits: list[str] = field(default_factory=list)
    common_baselines: list[str] = field(default_factory=list)
    known_limitations: list[str] = field(default_factory=list)
    leakage_risks: list[str] = field(default_factory=list)
    license_notes: str = ""
    citation_requirements: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="vetted-benchmark-card"))


def default_vetted_benchmark_card(record: VettedBenchmarkRecord) -> VettedBenchmarkCard:
    warnings = source_visibility_warnings(record)
    return VettedBenchmarkCard(
        benchmark_id=record.id,
        why_vetted=_why_vetted(record),
        intended_use=_intended_use(record),
        standard_metrics=record.metric_ids or ["Standard metrics are not recorded."],
        standard_splits=["Standard splits are not recorded."],
        common_baselines=record.baseline_ids or ["Common baselines are not recorded."],
        known_limitations=record.limitations or ["Benchmark limitations are not fully documented."],
        leakage_risks=[
            "Adapter use must preserve source splits and check duplicate or contamination leakage.",
            "Grounding in this benchmark does not automatically validate the selected protocol.",
        ],
        license_notes=_license_notes(record, warnings),
        citation_requirements=record.citation or "Citation requirements are not recorded.",
        provenance=record.provenance,
    )


def render_vetted_benchmark_card(record: VettedBenchmarkRecord, card: VettedBenchmarkCard) -> str:
    warnings = source_visibility_warnings(record)
    lines = [
        f"# Vetted Benchmark Card `{record.id}`",
        "",
        f"- Name: {record.name}",
        f"- Domain: {record.domain or 'unknown'}",
        f"- Source: {record.source or 'unknown'}",
        f"- Source URL: {record.source_url or 'none'}",
        f"- Benchmark type: `{record.benchmark_type}`",
        f"- Vetted status: `{record.vetted_status}`",
        f"- License: {record.license or 'unknown'}",
        f"- Terms of use: {record.terms_of_use or 'unknown'}",
        f"- Download required: {record.download_required}",
        f"- Authentication required: {record.authentication_required}",
        f"- Size estimate: {record.size_estimate or 'unknown'}",
        f"- Leaderboard URL: {record.leaderboard_url or 'none'}",
        f"- Task types: {_fmt(record.task_types)}",
        f"- Datasets: {_fmt(record.dataset_ids)}",
        f"- Metrics: {_fmt(record.metric_ids)}",
        f"- Baselines: {_fmt(record.baseline_ids)}",
        f"- Papers: {_fmt(record.paper_ids)}",
        "",
        "## Why Vetted",
        "",
        card.why_vetted or "No vetting rationale recorded.",
        "",
        "## Intended Use",
        "",
        card.intended_use or "No intended use recorded.",
        "",
        "## Standard Metrics",
        "",
        *[f"- {item}" for item in card.standard_metrics],
        "",
        "## Standard Splits",
        "",
        *[f"- {item}" for item in card.standard_splits],
        "",
        "## Common Baselines",
        "",
        *[f"- {item}" for item in card.common_baselines],
        "",
        "## Known Limitations",
        "",
        *[f"- {item}" for item in card.known_limitations],
        "",
        "## Leakage Risks",
        "",
        *[f"- {item}" for item in card.leakage_risks],
        "",
        "## License Notes",
        "",
        card.license_notes or "No license notes recorded.",
        "",
        "## Citation Requirements",
        "",
        card.citation_requirements or "No citation requirements recorded.",
    ]
    if warnings:
        lines.extend(["", "## Visibility Warnings", "", *[f"- {item}" for item in warnings]])
    return "\n".join(lines).rstrip() + "\n"


def render_vetted_benchmark_list(records: list[VettedBenchmarkRecord]) -> str:
    lines = ["# Vetted Benchmark Registry", ""]
    if not records:
        lines.append("No vetted benchmarks are registered.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        warnings = source_visibility_warnings(record)
        lines.extend(
            [
                f"## `{record.id}`",
                "",
                f"- Name: {record.name}",
                f"- Domain: {record.domain or 'unknown'}",
                f"- Type: `{record.benchmark_type}`",
                f"- Vetted status: `{record.vetted_status}`",
                f"- License: {record.license or 'unknown'}",
                f"- Terms of use: {record.terms_of_use or 'unknown'}",
                f"- Download/auth: download={record.download_required}, auth={record.authentication_required}",
                f"- Task types: {_fmt(record.task_types)}",
                f"- Source URL: {record.source_url or 'none'}",
                "",
            ]
        )
        if warnings:
            lines.extend([f"- Warning: {item}" for item in warnings])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _why_vetted(record: VettedBenchmarkRecord) -> str:
    if record.vetted_status == "canonical":
        return "Recorded as canonical for its domain, subject to license and fit checks."
    if record.vetted_status == "widely_used":
        return "Recorded as widely used in prior work, subject to license and fit checks."
    if record.vetted_status == "emerging":
        return "Recorded as an emerging benchmark; use requires additional fit and stability review."
    return "Vetting status is uncertain; do not treat this benchmark as authoritative without review."


def _intended_use(record: VettedBenchmarkRecord) -> str:
    return (
        "Candidate real benchmark grounding source. Fit must be assessed before using it as primary, auxiliary, "
        "or sanity-check evidence for a selected idea."
    )


def _license_notes(record: VettedBenchmarkRecord, warnings: list[str]) -> str:
    notes = []
    if record.license:
        notes.append(f"License: {record.license}.")
    if record.terms_of_use:
        notes.append(f"Terms: {record.terms_of_use}.")
    notes.extend(warnings)
    return " ".join(notes) if notes else "License and terms are not recorded."


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
