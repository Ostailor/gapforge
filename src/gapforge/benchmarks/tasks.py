"""Benchmark task helpers."""

from __future__ import annotations

from gapforge.models import BenchmarkRecord, BenchmarkTask, Provenance
from gapforge.state import slugify, utc_now_iso


def default_benchmark_task(record: BenchmarkRecord) -> BenchmarkTask:
    """Create the default task record for a registered benchmark."""

    return BenchmarkTask(
        id=f"benchmark-task-{slugify(record.name)}",
        benchmark_id=record.id,
        name=record.name,
        description=record.description,
        input_schema={"type": "object", "description": "Benchmark input schema is not fully specified."},
        output_schema={"type": "object", "description": "Benchmark output schema is not fully specified."},
        splits=record.expected_splits,
        metrics=record.metric_ids,
        required_baselines=record.baseline_ids,
        minimum_sample_size_notes=_sample_size_notes(record),
        provenance=Provenance(
            created_by_skill="benchmark-task",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Created a default benchmark task from the benchmark registry record.",
        ),
    )


def _sample_size_notes(record: BenchmarkRecord) -> str:
    text = " ".join([record.name, record.description, " ".join(record.metric_ids)]).lower()
    if "false positive" in text or "fpr" in text:
        return "Low-FPR benchmark tasks require enough negative examples to support confidence intervals."
    return "Minimum sample size must be justified before claiming benchmark performance."
