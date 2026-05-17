"""External expert review capture for selected paper packages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso

EXTERNAL_REVIEW_RECOMMENDATIONS = {"accept", "weak_accept", "borderline", "weak_reject", "reject"}
EXTERNAL_REVIEW_SOURCES = {"human", "simulated"}


@dataclass(slots=True)
class ExternalExpertReview:
    id: str
    manuscript_id: str
    reviewer_role: str
    expertise_area: str
    overall_recommendation: str
    key_strengths: list[str] = field(default_factory=list)
    key_weaknesses: list[str] = field(default_factory=list)
    missing_related_work: list[str] = field(default_factory=list)
    missing_experiments: list[str] = field(default_factory=list)
    claim_overreach: list[str] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="external-expert-review-human"))


class ExternalExpertReviewManager:
    """Persist human or simulated external expert critique without conflating sources."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.manuscripts = ManuscriptManager(config)

    def add_review(
        self,
        manuscript_id: str,
        *,
        reviewer_role: str = "external expert",
        expertise_area: str = "unspecified",
        overall_recommendation: str = "borderline",
        key_strengths: list[str] | None = None,
        key_weaknesses: list[str] | None = None,
        missing_related_work: list[str] | None = None,
        missing_experiments: list[str] | None = None,
        claim_overreach: list[str] | None = None,
        required_revisions: list[str] | None = None,
        notes: list[str] | None = None,
        source: str = "human",
    ) -> ExternalExpertReview:
        if overall_recommendation not in EXTERNAL_REVIEW_RECOMMENDATIONS:
            allowed = ", ".join(sorted(EXTERNAL_REVIEW_RECOMMENDATIONS))
            raise ValueError(f"Unsupported external review recommendation `{overall_recommendation}`. Expected one of: {allowed}")
        if source not in EXTERNAL_REVIEW_SOURCES:
            raise ValueError("External review source must be `human` or `simulated`.")
        reviews = self.load(manuscript_id)
        review = ExternalExpertReview(
            id=_next_review_id(manuscript_id, reviews),
            manuscript_id=manuscript_id,
            reviewer_role=reviewer_role,
            expertise_area=expertise_area,
            overall_recommendation=overall_recommendation,
            key_strengths=_unique(key_strengths or []),
            key_weaknesses=_unique(key_weaknesses or []),
            missing_related_work=_unique(missing_related_work or []),
            missing_experiments=_unique(missing_experiments or []),
            claim_overreach=_unique(claim_overreach or []),
            required_revisions=_unique(required_revisions or []),
            notes=_unique(notes or []),
            provenance=Provenance(
                created_by_skill=f"external-expert-review-{source}",
                source_ids=[manuscript_id],
                timestamp=utc_now_iso(),
                reasoning_summary=(f"Captured {source} external expert review. Human and simulated reviews are reported separately."),
            ),
        )
        reviews.append(review)
        self.save(manuscript_id, reviews)
        return review

    def load(self, manuscript_id: str) -> list[ExternalExpertReview]:
        path = self.review_path(manuscript_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(ExternalExpertReview, item) for item in payload.get("reviews", [])]

    def save(self, manuscript_id: str, reviews: list[ExternalExpertReview]) -> None:
        path = self.review_path(manuscript_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"manuscript_id": manuscript_id, "reviews": [to_plain(review) for review in reviews]}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.report_path(manuscript_id).write_text(render_external_review_report(manuscript_id, reviews), encoding="utf-8")

    def status(self, manuscript_id: str) -> dict[str, Any]:
        return external_review_status(manuscript_id, self.load(manuscript_id))

    def report(self, manuscript_id: str) -> str:
        reviews = self.load(manuscript_id)
        report = render_external_review_report(manuscript_id, reviews)
        report_path = self.report_path(manuscript_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        return report

    def review_path(self, manuscript_id: str) -> Path:
        return self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "external" / "external_expert_reviews.json"

    def report_path(self, manuscript_id: str) -> Path:
        return self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "external" / "external_expert_reviews.md"


def external_review_status(manuscript_id: str, reviews: list[ExternalExpertReview]) -> dict[str, Any]:
    human_reviews = [review for review in reviews if _review_source(review) == "human"]
    simulated_reviews = [review for review in reviews if _review_source(review) == "simulated"]
    unresolved_fatal = [review for review in human_reviews if _is_unresolved_fatal(review)]
    blockers = [_fatal_blocker(review) for review in unresolved_fatal]
    return {
        "manuscript_id": manuscript_id,
        "review_count": len(reviews),
        "human_review_count": len(human_reviews),
        "simulated_review_count": len(simulated_reviews),
        "unresolved_fatal_external_review_count": len(unresolved_fatal),
        "unresolved_fatal_external_review_ids": [review.id for review in unresolved_fatal],
        "conference_candidate_allowed": not unresolved_fatal,
        "blockers": blockers,
    }


def render_external_review_report(manuscript_id: str, reviews: list[ExternalExpertReview]) -> str:
    status = external_review_status(manuscript_id, reviews)
    human_reviews = [review for review in reviews if _review_source(review) == "human"]
    simulated_reviews = [review for review in reviews if _review_source(review) == "simulated"]
    lines = [
        f"# External Expert Review Report `{manuscript_id}`",
        "",
        "External reviews can include real human critique. Human and simulated reviews are not conflated.",
        "",
        f"- Total reviews: {len(reviews)}",
        f"- Human external reviews: {len(human_reviews)}",
        f"- Simulated external reviews: {len(simulated_reviews)}",
        f"- Unresolved fatal external reviews: {status['unresolved_fatal_external_review_count']}",
        f"- Conference candidate allowed by external review: `{str(status['conference_candidate_allowed']).lower()}`",
        "",
        "## Human External Reviews",
        "",
    ]
    lines.extend(_render_review(review) for review in human_reviews)
    if not human_reviews:
        lines.append("- none")
    lines.extend(["", "## Simulated External Reviews", ""])
    lines.extend(_render_review(review) for review in simulated_reviews)
    if not simulated_reviews:
        lines.append("- none")
    lines.extend(["", "## External Review Blockers", ""])
    lines.extend([f"- {item}" for item in status["blockers"]] or ["- none"])
    lines.extend(
        [
            "",
            "## Readiness Rule",
            "",
            "- If external review exists, conference_candidate requires no unresolved fatal human external review issue.",
            "- Simulated review can inform revision, but it is reported separately from real human critique.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_review(review: ExternalExpertReview) -> str:
    lines = [
        f"### `{review.id}`",
        "",
        f"- Source: `{_review_source(review)}`",
        f"- Reviewer role: {review.reviewer_role}",
        f"- Expertise area: {review.expertise_area}",
        f"- Overall recommendation: `{review.overall_recommendation}`",
        f"- Fatal unresolved: `{str(_is_unresolved_fatal(review)).lower()}`",
        "- Key strengths:",
        *_list_lines(review.key_strengths),
        "- Key weaknesses:",
        *_list_lines(review.key_weaknesses),
        "- Missing related work:",
        *_list_lines(review.missing_related_work),
        "- Missing experiments:",
        *_list_lines(review.missing_experiments),
        "- Claim overreach:",
        *_list_lines(review.claim_overreach),
        "- Required revisions:",
        *_list_lines(review.required_revisions),
        "- Notes:",
        *_list_lines(review.notes),
        "",
    ]
    return "\n".join(lines)


def _is_unresolved_fatal(review: ExternalExpertReview) -> bool:
    if _review_source(review) != "human":
        return False
    if _has_resolution_note(review):
        return False
    reject_like = review.overall_recommendation in {"weak_reject", "reject"}
    fatal_content = bool(review.claim_overreach or review.missing_experiments or review.required_revisions)
    explicit_fatal = any("fatal" in item.lower() for item in [*review.notes, *review.key_weaknesses, *review.required_revisions])
    return (reject_like and fatal_content) or explicit_fatal


def _has_resolution_note(review: ExternalExpertReview) -> bool:
    return any("resolved:" in note.lower() or "external-review-resolved" in note.lower() for note in review.notes)


def _fatal_blocker(review: ExternalExpertReview) -> str:
    return (
        f"External human review `{review.id}` is `{review.overall_recommendation}` with unresolved fatal issues: "
        f"{'; '.join(_unique([*review.claim_overreach, *review.missing_experiments, *review.required_revisions])) or 'see notes'}."
    )


def _review_source(review: ExternalExpertReview) -> str:
    skill = review.provenance.created_by_skill
    if skill.endswith("-simulated") or "simulated" in skill:
        return "simulated"
    return "human"


def _next_review_id(manuscript_id: str, reviews: list[ExternalExpertReview]) -> str:
    base = f"external-review-{slugify(manuscript_id)}"
    ids = {review.id for review in reviews}
    index = len(reviews) + 1
    candidate = f"{base}-{index:03d}"
    while candidate in ids:
        index += 1
        candidate = f"{base}-{index:03d}"
    return candidate


def _list_lines(values: list[str]) -> list[str]:
    return [f"  - {value}" for value in values] if values else ["  - none"]


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
