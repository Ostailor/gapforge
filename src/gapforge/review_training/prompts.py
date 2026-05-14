"""Prompt/task-pack templates for reviewer calibration modes."""

from __future__ import annotations

from gapforge.review_training.schemas import ReviewDatasetPaper


def reviewer_task_pack_prompt(paper: ReviewDatasetPaper, *, mode: str) -> str:
    return "\n".join(
        [
            f"# Reviewer Calibration Task `{paper.id}`",
            "",
            f"- Mode: `{mode}`",
            f"- Venue: {paper.venue} {paper.year}",
            f"- Decision label available for calibration: `{paper.decision or 'unknown'}`",
            "",
            "## Rules",
            "",
            "- Generate harsh top-conference-style critique, not acceptance prediction.",
            "- Do not invent citations, results, datasets, or artifact claims.",
            "- Link every criticism to visible paper metadata, manuscript sections, or artifact identifiers when available.",
            "- State uncertainty and missing evidence explicitly.",
            "- Do not claim equivalence to a human reviewer.",
            "",
            "## Paper Metadata",
            "",
            f"Title: {paper.title}",
            "",
            f"Abstract: {paper.abstract or 'not available'}",
            "",
        ]
    )
