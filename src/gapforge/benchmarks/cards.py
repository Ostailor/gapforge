"""Markdown rendering for benchmark records and cards."""

from __future__ import annotations

from gapforge.models import BenchmarkCard, BenchmarkRecord


def default_benchmark_card(record: BenchmarkRecord, *, fixture_labeled: bool = False) -> BenchmarkCard:
    """Create a conservative benchmark card from a benchmark record."""

    risks = list(record.limitations)
    if fixture_labeled:
        risks.append("Fixture benchmark: validates workflow only and cannot support real benchmark claims.")
    return BenchmarkCard(
        benchmark_id=record.id,
        motivation=record.description or f"Evaluate `{record.name}` as an explicit benchmark artifact.",
        intended_use=_intended_use(record, fixture_labeled=fixture_labeled),
        dataset_summary=_dataset_summary(record, fixture_labeled=fixture_labeled),
        evaluation_protocol=record.evaluation_protocol or "Evaluation protocol is not fully specified.",
        known_failure_modes=risks or ["Benchmark failure modes are not fully documented."],
        leakage_risks=_leakage_risks(record, fixture_labeled=fixture_labeled),
        fairness_or_bias_risks=record.safety_notes or ["Fairness/bias risks have not been fully reviewed."],
        citation=_citation(record),
        provenance=record.provenance,
    )


def render_benchmark_card_markdown(record: BenchmarkRecord, card: BenchmarkCard) -> str:
    label = "fixture" if is_fixture_benchmark(record) else "real-or-benchmark"
    lines = [
        f"# Benchmark Card `{record.id}`",
        "",
        f"- Name: {record.name}",
        f"- Domain: {record.domain or 'unknown'}",
        f"- Task type: `{record.task_type}`",
        f"- Benchmark label: `{label}`",
        f"- License: {record.license or 'unknown'}",
        f"- Source URL: {record.source_url or 'none'}",
        f"- Leaderboard URL: {record.leaderboard_url or 'none'}",
        f"- Datasets: {', '.join(f'`{item}`' for item in record.dataset_ids) or 'none'}",
        f"- Baselines: {', '.join(f'`{item}`' for item in record.baseline_ids) or 'none'}",
        f"- Metrics: {', '.join(f'`{item}`' for item in record.metric_ids) or 'none'}",
        f"- Expected splits: {', '.join(record.expected_splits) or 'not specified'}",
        "",
        "## Motivation",
        "",
        card.motivation or "No motivation recorded.",
        "",
        "## Intended Use",
        "",
        card.intended_use or "No intended use recorded.",
        "",
        "## Dataset Summary",
        "",
        card.dataset_summary or "No dataset summary recorded.",
        "",
        "## Evaluation Protocol",
        "",
        card.evaluation_protocol or "No evaluation protocol recorded.",
        "",
        "## Known Failure Modes",
        "",
        *[f"- {item}" for item in card.known_failure_modes],
        "",
        "## Leakage Risks",
        "",
        *[f"- {item}" for item in card.leakage_risks],
        "",
        "## Fairness Or Bias Risks",
        "",
        *[f"- {item}" for item in card.fairness_or_bias_risks],
        "",
        "## Citation",
        "",
        card.citation or "No citation recorded.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_benchmark_registry_markdown(records: list[BenchmarkRecord]) -> str:
    lines = ["# Benchmark Registry", ""]
    if not records:
        lines.append("No benchmarks are registered for this experiment workspace.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        label = "fixture" if is_fixture_benchmark(record) else "real-or-benchmark"
        lines.extend(
            [
                f"## `{record.id}`",
                "",
                f"- Name: {record.name}",
                f"- Domain: {record.domain or 'unknown'}",
                f"- Task type: `{record.task_type}`",
                f"- Benchmark label: `{label}`",
                f"- Datasets: {', '.join(f'`{item}`' for item in record.dataset_ids) or 'none'}",
                f"- Baselines: {', '.join(f'`{item}`' for item in record.baseline_ids) or 'none'}",
                f"- Metrics: {', '.join(f'`{item}`' for item in record.metric_ids) or 'none'}",
                f"- Evaluation protocol: {record.evaluation_protocol or 'not specified'}",
                "",
            ]
        )
        if is_fixture_benchmark(record):
            lines.extend(["- Fixture benchmark: workflow validation only; do not claim real benchmark performance.", ""])
    return "\n".join(lines).rstrip() + "\n"


def is_fixture_benchmark(record: BenchmarkRecord) -> bool:
    text = " ".join(
        [
            record.domain,
            record.name,
            record.description,
            " ".join(record.limitations),
            " ".join(record.safety_notes),
        ]
    ).lower()
    return "fixture" in text or "synthetic" in text


def _intended_use(record: BenchmarkRecord, *, fixture_labeled: bool) -> str:
    if fixture_labeled:
        return "Fixture benchmark for testing registry, reporting, and execution plumbing. Not for real benchmark claims."
    return record.description or "Evaluate an experiment protocol against a named benchmark task."


def _dataset_summary(record: BenchmarkRecord, *, fixture_labeled: bool) -> str:
    prefix = "Fixture benchmark dataset references" if fixture_labeled else "Benchmark dataset references"
    return f"{prefix}: {', '.join(record.dataset_ids) or 'none recorded'}."


def _leakage_risks(record: BenchmarkRecord, *, fixture_labeled: bool) -> list[str]:
    risks = ["Split integrity and duplicate leakage should be checked before interpreting benchmark results."]
    if not record.expected_splits:
        risks.append("Expected splits are not recorded.")
    if fixture_labeled:
        risks.append("Fixture splits may be tiny and are not representative.")
    return risks


def _citation(record: BenchmarkRecord) -> str:
    papers = ", ".join(record.paper_ids)
    if record.source_url and papers:
        return f"{record.source_url}; papers: {papers}"
    if record.source_url:
        return record.source_url
    if papers:
        return f"papers: {papers}"
    return ""
