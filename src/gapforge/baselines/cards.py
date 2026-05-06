"""Baseline card rendering."""

from __future__ import annotations

from gapforge.models import BaselineCard, BaselineRecord


def default_baseline_card(record: BaselineRecord) -> BaselineCard:
    return BaselineCard(
        baseline_id=record.id,
        why_included=record.description or record.risk_if_missing or "Baseline registered for experiment comparison.",
        what_it_tests=_what_it_tests(record),
        strengths=_strengths(record),
        weaknesses=_weaknesses(record),
        implementation_notes=_implementation_notes(record),
        citation=record.code_url or ", ".join(record.source_paper_ids) or "Citation not specified.",
        provenance=record.provenance,
    )


def render_baseline_card_markdown(record: BaselineRecord, card: BaselineCard) -> str:
    lines = [
        f"# Baseline Card: {record.name}",
        "",
        f"- Baseline ID: `{record.id}`",
        f"- Type: `{record.baseline_type}`",
        f"- Required for submission: {str(record.required_for_submission).lower()}",
        f"- Code available: {str(record.code_available).lower()}",
        f"- Code URL: {record.code_url or 'unknown'}",
        f"- Implementation path: `{record.implementation_path or 'none'}`",
        f"- Source papers: {', '.join(f'`{item}`' for item in record.source_paper_ids) or 'none'}",
        f"- Related-work entries: {', '.join(f'`{item}`' for item in record.related_work_entry_ids) or 'none'}",
        "",
        "## Why Included",
        "",
        card.why_included or "Not specified.",
        "",
        "## What It Tests",
        "",
        card.what_it_tests or "Not specified.",
        "",
    ]
    _extend_list(lines, "Strengths", card.strengths)
    _extend_list(lines, "Weaknesses", card.weaknesses)
    lines.extend(
        [
            "## Implementation Notes",
            "",
            card.implementation_notes or "Not specified.",
            "",
            "## Risk If Missing",
            "",
            record.risk_if_missing or "Not specified.",
            "",
            "## Citation",
            "",
            card.citation or "Not specified.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_baseline_registry_markdown(records: list[BaselineRecord]) -> str:
    lines = ["# Baseline Registry", ""]
    if not records:
        lines.append("No baselines registered yet.")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        lines.extend(
            [
                f"## `{record.id}` {record.name}",
                "",
                f"- Type: `{record.baseline_type}`",
                f"- Required for submission: {str(record.required_for_submission).lower()}",
                f"- Code available: {str(record.code_available).lower()}",
                f"- Source papers: {', '.join(record.source_paper_ids) or 'none'}",
                f"- Risk if missing: {record.risk_if_missing or 'not specified'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _extend_list(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend([f"## {title}", ""])
    lines.extend([f"- {item}" for item in items] or ["- none"])
    lines.append("")


def _what_it_tests(record: BaselineRecord) -> str:
    if record.baseline_type in {"trivial", "heuristic"}:
        return "Whether the proposed method beats simple non-learned alternatives."
    if record.baseline_type == "prior_work":
        return "Whether the proposed method improves over closest prior work."
    if record.baseline_type == "ablation":
        return "Whether the claimed component contributes to performance."
    return "The comparative value of the proposed experiment against a known reference point."


def _strengths(record: BaselineRecord) -> list[str]:
    strengths = []
    if record.source_paper_ids:
        strengths.append("Linked to prior work.")
    if record.code_available or record.implementation_path:
        strengths.append("Implementation is available or planned explicitly.")
    if record.required_for_submission:
        strengths.append("Marked as required for submission-quality empirical interpretation.")
    return strengths or ["Provides an explicit comparator."]


def _weaknesses(record: BaselineRecord) -> list[str]:
    weaknesses = []
    if not record.source_paper_ids and record.baseline_type == "prior_work":
        weaknesses.append("Prior-work baseline lacks a source paper link.")
    if not record.code_available and not record.implementation_path:
        weaknesses.append("Implementation is not yet available.")
    return weaknesses or ["Weaknesses require empirical review."]


def _implementation_notes(record: BaselineRecord) -> str:
    if record.implementation_path:
        return f"Use local implementation at `{record.implementation_path}`."
    if record.code_url:
        return f"Inspect upstream implementation at {record.code_url} before running."
    return "Implementation must be created or wrapped before execution."
