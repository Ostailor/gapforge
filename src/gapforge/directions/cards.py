"""Markdown cards for mature research directions."""

from __future__ import annotations

from pathlib import Path

from gapforge.models import ResearchDirection


def render_direction_card(
    direction: ResearchDirection,
    *,
    evidence_locators: list[str] | None = None,
    novelty_summary: str = "",
    reviewer_summary: str = "",
) -> str:
    locators = evidence_locators or []
    lines = [
        f"# Direction Card: {direction.title}",
        "",
        f"- Direction ID: `{direction.id}`",
        f"- Project ID: `{direction.project_id}`",
        f"- Maturity: {direction.maturity}",
        f"- Readiness score: {direction.readiness_score:.2f}",
        f"- Human owner: {direction.human_owner or 'unassigned'}",
        "",
        "## Summary",
        "",
        direction.summary or "No summary recorded.",
        "",
        "## Links",
        "",
        f"- Gaps: {', '.join(f'`{item}`' for item in direction.linked_gap_ids) or 'none'}",
        f"- Hypotheses: {', '.join(f'`{item}`' for item in direction.linked_hypothesis_ids) or 'none'}",
        f"- Experiments: {', '.join(f'`{item}`' for item in direction.linked_experiment_ids) or 'none'}",
        f"- Novelty dossiers: {', '.join(f'`{item}`' for item in direction.linked_novelty_dossier_ids) or 'none'}",
        f"- Supporting papers: {', '.join(f'`{item}`' for item in direction.supporting_paper_ids) or 'none'}",
        f"- Counterevidence papers: {', '.join(f'`{item}`' for item in direction.counterevidence_paper_ids) or 'none'}",
        "",
        "## Evidence Locators",
        "",
    ]
    lines.extend([f"- `{locator}`" for locator in locators] or ["- none"])
    lines.extend(
        [
            "",
            "## Novelty",
            "",
            novelty_summary or "No novelty summary available.",
            "",
            "## Reviewer Gate",
            "",
            reviewer_summary or "No reviewer summary available.",
            "",
            "## Blocking Issues",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in direction.blocking_issues] or ["- none"])
    lines.extend(["", "## Next Actions", ""])
    lines.extend([f"- {item}" for item in direction.next_actions] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def write_direction_card(
    project_dir: Path,
    direction: ResearchDirection,
    *,
    evidence_locators: list[str] | None = None,
    novelty_summary: str = "",
    reviewer_summary: str = "",
) -> Path:
    cards_dir = project_dir / "direction_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    path = cards_dir / f"{direction.id}.md"
    path.write_text(
        render_direction_card(
            direction,
            evidence_locators=evidence_locators,
            novelty_summary=novelty_summary,
            reviewer_summary=reviewer_summary,
        ),
        encoding="utf-8",
    )
    return path
