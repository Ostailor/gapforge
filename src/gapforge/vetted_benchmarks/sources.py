"""Models and source helpers for vetted benchmark grounding."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance

VETTED_STATUSES = {"canonical", "widely_used", "emerging", "uncertain"}
BENCHMARK_TYPES = {
    "dataset",
    "benchmark",
    "leaderboard",
    "suite",
    "protocol",
    "challenge",
    "unknown",
}


@dataclass(slots=True)
class VettedBenchmarkRecord:
    id: str
    name: str
    domain: str = ""
    source: str = ""
    source_url: str = ""
    benchmark_type: str = "unknown"
    task_types: list[str] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    metric_ids: list[str] = field(default_factory=list)
    baseline_ids: list[str] = field(default_factory=list)
    paper_ids: list[str] = field(default_factory=list)
    leaderboard_url: str = ""
    license: str = ""
    terms_of_use: str = ""
    download_required: bool = False
    authentication_required: bool = False
    size_estimate: str = ""
    citation: str = ""
    vetted_status: str = "uncertain"
    limitations: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="vetted-benchmark-registry"))


def normalize_vetted_status(value: str) -> str:
    status = (value or "uncertain").strip().lower().replace("-", "_")
    return status if status in VETTED_STATUSES else "uncertain"


def normalize_benchmark_type(value: str) -> str:
    benchmark_type = (value or "unknown").strip().lower().replace("-", "_")
    return benchmark_type if benchmark_type in BENCHMARK_TYPES else benchmark_type or "unknown"


def source_visibility_warnings(record: VettedBenchmarkRecord) -> list[str]:
    warnings: list[str] = []
    if not record.license:
        warnings.append("Benchmark license is not recorded.")
    if not record.terms_of_use:
        warnings.append("Benchmark terms of use are not recorded.")
    if record.download_required and not record.size_estimate:
        warnings.append("Download is required but size estimate is not recorded.")
    if record.authentication_required:
        warnings.append("Authentication is required; access must be reviewed before adapter use.")
    if not record.source_url and not record.leaderboard_url:
        warnings.append("No stable source URL or leaderboard URL is recorded.")
    return warnings
