"""Manuscript rebuttal item workflow."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import RebuttalItem, RevisionPlan
from gapforge.manuscript.reviewer_panel import ManuscriptReviewPanelBuilder
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso

REBUTTAL_STATUSES = {"open", "addressed", "rejected", "deferred"}


class ManuscriptRebuttalManager:
    """Convert manuscript reviewer objections into persistent rebuttal items."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)

    def build(self, manuscript_id: str) -> RevisionPlan:
        panel = ManuscriptReviewPanelBuilder(self.config).review(manuscript_id)
        existing = _existing_items(self.manuscript_manager.manuscript_root(manuscript_id))
        by_id = {item.id: item for item in existing}
        items = [
            _item_from_review_plan(
                manuscript_id,
                plan,
                by_id.get(_item_id(manuscript_id, plan.target_review_id)),
            )
            for plan in panel.rebuttal_plan
        ]
        revision = RevisionPlan(
            id=f"revision-plan-{manuscript_id}",
            manuscript_id=manuscript_id,
            rebuttal_items=items,
            section_edits=_section_edits(items),
            required_experiments=_unique([experiment for item in items for experiment in item.experiments_needed]),
            required_searches=_unique([citation for item in items for citation in item.citations_needed]),
            required_citations=_unique([citation for item in items for citation in item.citations_needed]),
            status=_revision_status(items),
            provenance=Provenance(
                created_by_skill="manuscript-rebuttal",
                source_ids=[manuscript_id, *[review.reviewer_id for review in panel.reviewer_reports]],
                timestamp=utc_now_iso(),
                reasoning_summary="Converted manuscript reviewer objections into actionable rebuttal items without inventing answers.",
            ),
        )
        _write_revision(self.manuscript_manager.manuscript_root(manuscript_id), revision)
        return revision

    def load_revision(self, manuscript_id: str) -> RevisionPlan:
        path = self.manuscript_manager.manuscript_root(manuscript_id) / "reviews" / "revision_plan.json"
        if not path.exists():
            return self.build(manuscript_id)
        return from_dict(RevisionPlan, json.loads(path.read_text(encoding="utf-8")))

    def mark_item(self, item_id: str, status: str) -> RebuttalItem:
        if status not in REBUTTAL_STATUSES:
            allowed = ", ".join(sorted(REBUTTAL_STATUSES))
            raise ValueError(f"Unsupported rebuttal status: {status}. Expected one of: {allowed}")
        root, revision = _find_revision_for_item(self.config, item_id)
        for item in revision.rebuttal_items:
            if item.id == item_id:
                item.status = status
                item.provenance = Provenance(
                    created_by_skill="manuscript-rebuttal",
                    source_ids=[item.id, item.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary=f"Marked rebuttal item `{item.id}` as `{status}`.",
                )
                revision.status = _revision_status(revision.rebuttal_items)
                _write_revision(root, revision)
                return item
        raise FileNotFoundError(f"No rebuttal item found for {item_id}")

    def render_markdown(self, revision: RevisionPlan) -> str:
        return render_rebuttal_plan_markdown(revision)


def render_rebuttal_plan_markdown(revision: RevisionPlan) -> str:
    lines = [
        f"# Rebuttal Plan `{revision.manuscript_id}`",
        "",
        f"- Status: `{revision.status}`",
        f"- Items: {len(revision.rebuttal_items)}",
        "",
    ]
    for item in revision.rebuttal_items:
        lines.extend(
            [
                f"## `{item.id}`",
                "",
                f"- Reviewer: `{item.reviewer_id}`",
                f"- Status: `{item.status}`",
                f"- Objection: {item.objection}",
                f"- Strategy: {item.response_strategy}",
                f"- Evidence needed: {', '.join(item.evidence_needed) or 'none'}",
                f"- Experiments needed: {', '.join(item.experiments_needed) or 'none'}",
                f"- Citations needed: {', '.join(item.citations_needed) or 'none'}",
                f"- Claim softening needed: {', '.join(item.claim_softening_needed) or 'none'}",
                "",
            ]
        )
    if not revision.rebuttal_items:
        lines.append("No rebuttal items.")
    return "\n".join(lines).rstrip() + "\n"


def _item_from_review_plan(manuscript_id: str, plan, existing: RebuttalItem | None) -> RebuttalItem:
    reviewer_id = plan.target_review_id
    item_id = _item_id(manuscript_id, reviewer_id)
    status = existing.status if existing else "open"
    experiments = _unique([*plan.experiments_to_add, *[item for item in plan.evidence_needed if _experiment_like(item)]])
    citations = _unique([*plan.citations_to_add, *[item for item in plan.evidence_needed if _citation_like(item)]])
    softening = _unique([*plan.claims_to_soften, *[item for item in plan.evidence_needed if _softening_like(item)]])
    return RebuttalItem(
        id=item_id,
        manuscript_id=manuscript_id,
        reviewer_id=reviewer_id,
        objection="; ".join(plan.risks) or "Reviewer requested additional evidence or revision.",
        response_strategy=plan.response_strategy,
        evidence_needed=list(plan.evidence_needed),
        experiments_needed=experiments,
        citations_needed=citations,
        claim_softening_needed=softening,
        status=status,
        provenance=Provenance(
            created_by_skill="manuscript-rebuttal",
            source_ids=[manuscript_id, reviewer_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Created rebuttal item from manuscript reviewer plan; no response was invented.",
        ),
    )


def _write_revision(root: Path, revision: RevisionPlan) -> None:
    reviews_dir = root / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / "rebuttal_items.json").write_text(json.dumps(to_plain(revision.rebuttal_items), indent=2) + "\n", encoding="utf-8")
    (reviews_dir / "revision_plan.json").write_text(json.dumps(to_plain(revision), indent=2) + "\n", encoding="utf-8")
    (reviews_dir / "rebuttal_plan_actionable.md").write_text(render_rebuttal_plan_markdown(revision), encoding="utf-8")


def _existing_items(root: Path) -> list[RebuttalItem]:
    path = root / "reviews" / "rebuttal_items.json"
    if not path.exists():
        return []
    return [from_dict(RebuttalItem, item) for item in json.loads(path.read_text(encoding="utf-8"))]


def _find_revision_for_item(config: GapForgeConfig, item_id: str) -> tuple[Path, RevisionPlan]:
    for path in config.project_root.glob("*/manuscripts/*/reviews/revision_plan.json"):
        revision = from_dict(RevisionPlan, json.loads(path.read_text(encoding="utf-8")))
        if any(item.id == item_id for item in revision.rebuttal_items):
            return path.parents[1], revision
    raise FileNotFoundError(f"No rebuttal item found for {item_id}")


def _revision_status(items: list[RebuttalItem]) -> str:
    if any(item.status == "open" for item in items):
        return "open"
    if any(item.status == "deferred" for item in items):
        return "deferred"
    if items and all(item.status == "addressed" for item in items):
        return "addressed"
    return "open" if items else "addressed"


def _section_edits(items: list[RebuttalItem]) -> list[str]:
    edits: list[str] = []
    for item in items:
        if item.claim_softening_needed:
            edits.append(f"Soften manuscript claims for `{item.reviewer_id}`: {', '.join(item.claim_softening_needed)}")
        if item.citations_needed:
            edits.append(f"Update citations/related work for `{item.reviewer_id}`.")
        if item.experiments_needed:
            edits.append(f"Update experiments/results text after completing `{item.reviewer_id}` experiment requests.")
    return _unique(edits)


def _item_id(manuscript_id: str, reviewer_id: str) -> str:
    return f"rebuttal-{slugify(manuscript_id)}-{slugify(reviewer_id)}"


def _experiment_like(value: str) -> bool:
    lowered = value.lower()
    return "experiment" in lowered or "run " in lowered or "baseline comparison" in lowered or "result artifact" in lowered


def _citation_like(value: str) -> bool:
    lowered = value.lower()
    return "citation" in lowered or "bibliography" in lowered or "related-work" in lowered or "related work" in lowered


def _softening_like(value: str) -> bool:
    lowered = value.lower()
    return "soften" in lowered or "remove" in lowered or "claim" in lowered


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
