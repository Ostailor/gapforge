"""Eligibility assessment for adapting vetted benchmarks to selected ideas."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.models import Provenance
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord, source_visibility_warnings

RECOMMENDED_USES = {"primary", "auxiliary", "sanity_check", "not_recommended"}


@dataclass(slots=True)
class BenchmarkEligibilityAssessment:
    benchmark_id: str
    selected_idea_id: str
    fit_score: float = 0.0
    fit_reason: str = ""
    mismatch_reason: str = ""
    adaptation_needed: list[str] = field(default_factory=list)
    can_support_low_fpr: bool = False
    can_support_multi_agent_or_monitoring: bool = False
    can_support_sequential_evaluation: bool = False
    recommended_use: str = "not_recommended"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="vetted-benchmark-eligibility"))


def assess_benchmark_eligibility(record: VettedBenchmarkRecord, *, selected_idea_id: str) -> BenchmarkEligibilityAssessment:
    text = _record_text(record)
    idea_text = selected_idea_id.lower()
    can_low_fpr = _has_any(text, ["low-fpr", "low fpr", "false positive", "specificity", "false alarm", "rare event"])
    can_monitoring = _has_any(text, ["multi-agent", "multi agent", "collusion", "monitor", "audit", "evasion", "coordination"])
    can_sequential = _has_any(text, ["sequential", "time series", "timeseries", "online", "stream", "longitudinal", "window", "repeated"])

    score = 0.0
    if can_low_fpr:
        score += 0.35
    if can_monitoring:
        score += 0.35
    if can_sequential:
        score += 0.2
    if record.vetted_status in {"canonical", "widely_used"}:
        score += 0.1
    if "low-fpr" in idea_text or "collusion" in idea_text:
        score = min(score, 1.0)

    blockers = source_visibility_warnings(record)
    adaptation_needed = _adaptation_needed(can_low_fpr, can_monitoring, can_sequential)
    recommended = _recommended_use(score, can_low_fpr, can_monitoring, can_sequential)
    if recommended == "primary" and blockers:
        recommended = "auxiliary"
    if score < 0.2:
        blockers.append("Poor fit: recorded fields do not support low-FPR, multi-agent/monitoring, or sequential evaluation.")

    return BenchmarkEligibilityAssessment(
        benchmark_id=record.id,
        selected_idea_id=selected_idea_id,
        fit_score=round(score, 2),
        fit_reason=_fit_reason(can_low_fpr, can_monitoring, can_sequential, record),
        mismatch_reason=_mismatch_reason(can_low_fpr, can_monitoring, can_sequential),
        adaptation_needed=adaptation_needed,
        can_support_low_fpr=can_low_fpr,
        can_support_multi_agent_or_monitoring=can_monitoring,
        can_support_sequential_evaluation=can_sequential,
        recommended_use=recommended,
        blockers=blockers,
        provenance=Provenance(
            created_by_skill="vetted-benchmark-eligibility",
            source_ids=[record.id, selected_idea_id],
            reasoning_summary="Assessed vetted benchmark fit instead of assuming known-benchmark relevance.",
        ),
    )


def render_eligibility_assessment(assessment: BenchmarkEligibilityAssessment) -> str:
    lines = [
        f"# Benchmark Eligibility `{assessment.benchmark_id}`",
        "",
        f"- Selected idea: `{assessment.selected_idea_id}`",
        f"- Fit score: {assessment.fit_score:.2f}",
        f"- Recommended use: `{assessment.recommended_use}`",
        f"- Can support low-FPR: {assessment.can_support_low_fpr}",
        f"- Can support multi-agent or monitoring: {assessment.can_support_multi_agent_or_monitoring}",
        f"- Can support sequential evaluation: {assessment.can_support_sequential_evaluation}",
        "",
        "## Fit Reason",
        "",
        assessment.fit_reason or "No fit rationale recorded.",
        "",
        "## Mismatch Reason",
        "",
        assessment.mismatch_reason or "No mismatch recorded.",
        "",
        "## Adaptation Needed",
        "",
        *[f"- {item}" for item in (assessment.adaptation_needed or ["No adaptation requirements recorded."])],
        "",
        "## Blockers",
        "",
        *[f"- {item}" for item in (assessment.blockers or ["No blockers recorded."])],
        "",
        "## Grounding Rule",
        "",
        (
            "A vetted benchmark does not automatically mean good fit. If no benchmark fits, preserve the synthetic benchmark "
            "as a protocol contribution."
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _record_text(record: VettedBenchmarkRecord) -> str:
    parts = [
        record.name,
        record.domain,
        record.source,
        record.benchmark_type,
        " ".join(record.task_types),
        " ".join(record.dataset_ids),
        " ".join(record.metric_ids),
        " ".join(record.baseline_ids),
        " ".join(record.paper_ids),
        record.citation,
        " ".join(record.limitations),
    ]
    return " ".join(parts).lower()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _adaptation_needed(can_low_fpr: bool, can_monitoring: bool, can_sequential: bool) -> list[str]:
    items: list[str] = [
        "Define adapter mapping without treating benchmark fame as validity evidence.",
        "Preserve license, terms, download, and authentication constraints in the adapter card.",
    ]
    if not can_low_fpr:
        items.append("Add or justify low-FPR false-positive denominator and thresholding policy.")
    if not can_monitoring:
        items.append("Use only as auxiliary/sanity-check unless monitoring or multi-agent semantics can be justified.")
    if not can_sequential:
        items.append("Construct audit windows or mark sequential evaluation unsupported.")
    return items


def _recommended_use(score: float, can_low_fpr: bool, can_monitoring: bool, can_sequential: bool) -> str:
    if score >= 0.85 and can_low_fpr and can_monitoring and can_sequential:
        return "primary"
    if score >= 0.55 and (can_low_fpr or can_monitoring):
        return "auxiliary"
    if score >= 0.25:
        return "sanity_check"
    return "not_recommended"


def _fit_reason(can_low_fpr: bool, can_monitoring: bool, can_sequential: bool, record: VettedBenchmarkRecord) -> str:
    supported = []
    if can_low_fpr:
        supported.append("low-FPR or specificity signals")
    if can_monitoring:
        supported.append("multi-agent, monitoring, audit, collusion, coordination, or evasion signals")
    if can_sequential:
        supported.append("sequential, online, time-series, repeated, or windowed evaluation signals")
    if not supported:
        return "Recorded benchmark fields do not show direct support for the selected low-FPR collusion-audit protocol."
    return f"Recorded fields suggest support for {', '.join(supported)}. Vetted status is `{record.vetted_status}`."


def _mismatch_reason(can_low_fpr: bool, can_monitoring: bool, can_sequential: bool) -> str:
    missing = []
    if not can_low_fpr:
        missing.append("low-FPR/specificity support")
    if not can_monitoring:
        missing.append("multi-agent or monitoring support")
    if not can_sequential:
        missing.append("sequential evaluation support")
    return f"Missing: {', '.join(missing)}." if missing else "No major protocol-fit mismatch detected from recorded fields."
