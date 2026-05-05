"""Markdown rendering for related-work matrices."""

from __future__ import annotations

from gapforge.models import RelatedWorkMatrix
from gapforge.related_work.taxonomy import relationship_label


def render_related_work_matrices_markdown(matrices: list[RelatedWorkMatrix]) -> str:
    if not matrices:
        return "# Related Work Matrix\n\nNo related-work matrices generated yet.\n"
    lines = ["# Related Work Matrix", ""]
    for matrix in matrices:
        lines.append(render_related_work_matrix_markdown(matrix).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_related_work_matrix_markdown(matrix: RelatedWorkMatrix) -> str:
    lines = [
        f"## Direction `{matrix.direction_id}`",
        "",
        "### Coverage Summary",
        "",
        matrix.coverage_summary or "No coverage summary recorded.",
        "",
        "### Missing Categories",
        "",
    ]
    lines.extend([f"- {relationship_label(category)}" for category in matrix.missing_categories] or ["- none"])
    lines.extend(["", "### Must Read Papers", ""])
    lines.extend([f"- `{paper_id}`" for paper_id in matrix.must_read_paper_ids] or ["- none"])
    lines.extend(["", "### Baseline Papers", ""])
    lines.extend([f"- `{paper_id}`" for paper_id in matrix.baseline_paper_ids] or ["- none"])
    lines.extend(["", "### Entries", ""])
    if not matrix.entries:
        lines.append("- none")
    for entry in sorted(matrix.entries, key=lambda item: (-item.relevance_score, item.relationship, item.paper_id)):
        lines.extend(
            [
                f"#### `{entry.paper_id}` {relationship_label(entry.relationship)}",
                "",
                f"- Relevance score: {entry.relevance_score:.2f}",
                f"- Must cite: {entry.must_cite}",
                f"- Baseline candidate: {entry.baseline_candidate}",
                f"- Evidence spans: {', '.join(f'`{item}`' for item in entry.evidence_span_ids) or 'none'}",
                f"- Reviewer risk if omitted: {entry.reviewer_risk_if_omitted or 'none'}",
                "",
                "Contributes: " + (entry.what_it_contributes or "Not specified."),
                "",
                "Does not solve: " + (entry.what_it_does_not_solve or "Not specified."),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
