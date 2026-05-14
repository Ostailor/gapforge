"""Vetted benchmark registry for real benchmark grounding."""

from gapforge.vetted_benchmarks.adapter_registry import BenchmarkAdapterRegistry
from gapforge.vetted_benchmarks.adapters import BenchmarkAdapter, render_benchmark_adapter_report
from gapforge.vetted_benchmarks.cards import VettedBenchmarkCard, render_vetted_benchmark_card, render_vetted_benchmark_list
from gapforge.vetted_benchmarks.eligibility import (
    BenchmarkEligibilityAssessment,
    assess_benchmark_eligibility,
    render_eligibility_assessment,
)
from gapforge.vetted_benchmarks.manifests import BenchmarkAdapterRun
from gapforge.vetted_benchmarks.registry import VettedBenchmarkRegistry, render_vetted_benchmark_project_report
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord

__all__ = [
    "BenchmarkAdapter",
    "BenchmarkAdapterRegistry",
    "BenchmarkAdapterRun",
    "BenchmarkEligibilityAssessment",
    "VettedBenchmarkCard",
    "VettedBenchmarkRecord",
    "VettedBenchmarkRegistry",
    "assess_benchmark_eligibility",
    "render_benchmark_adapter_report",
    "render_eligibility_assessment",
    "render_vetted_benchmark_card",
    "render_vetted_benchmark_list",
    "render_vetted_benchmark_project_report",
]
