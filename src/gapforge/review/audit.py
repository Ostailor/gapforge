"""Audit helpers for human review records."""

from __future__ import annotations

from collections import Counter
from typing import Any

from gapforge.models import HumanReviewRecord, ResearchRunState


def reviews_for(state: ResearchRunState, object_type: str, object_id: str) -> list[HumanReviewRecord]:
    return [record for record in state.human_reviews if record.object_type == object_type and record.object_id == object_id]


def latest_action(state: ResearchRunState, object_type: str, object_id: str) -> str:
    records = reviews_for(state, object_type, object_id)
    return records[-1].action if records else ""


def is_rejected(state: ResearchRunState, object_type: str, object_id: str) -> bool:
    action = latest_action(state, object_type, object_id)
    return action == "reject"


def is_locked(state: ResearchRunState, object_type: str, object_id: str) -> bool:
    locked = False
    for record in reviews_for(state, object_type, object_id):
        if record.action == "lock":
            locked = True
        elif record.action == "unlock":
            locked = False
    return locked


def locked_object_ids(state: ResearchRunState, object_type: str) -> set[str]:
    ids = {record.object_id for record in state.human_reviews if record.object_type == object_type}
    return {object_id for object_id in ids if is_locked(state, object_type, object_id)}


def approved_object_ids(state: ResearchRunState, object_type: str) -> set[str]:
    return {
        record.object_id
        for record in state.human_reviews
        if record.object_type == object_type and latest_action(state, object_type, record.object_id) == "approve"
    }


def review_summary(state: ResearchRunState) -> dict[str, Any]:
    action_counts = Counter(record.action for record in state.human_reviews)
    type_counts = Counter(record.object_type for record in state.human_reviews)
    locked = sorted(
        {
            f"{record.object_type}:{record.object_id}"
            for record in state.human_reviews
            if is_locked(state, record.object_type, record.object_id)
        }
    )
    rejected = sorted(
        {
            f"{record.object_type}:{record.object_id}"
            for record in state.human_reviews
            if is_rejected(state, record.object_type, record.object_id)
        }
    )
    return {
        "review_count": len(state.human_reviews),
        "action_counts": dict(sorted(action_counts.items())),
        "object_type_counts": dict(sorted(type_counts.items())),
        "locked_objects": locked,
        "rejected_objects": rejected,
        "recent_reviews": [
            {
                "id": record.id,
                "object_type": record.object_type,
                "object_id": record.object_id,
                "action": record.action,
                "note": record.note,
                "reviewer": record.reviewer,
                "timestamp": record.timestamp,
            }
            for record in state.human_reviews[-10:]
        ],
    }


def render_human_reviews_markdown(state: ResearchRunState) -> str:
    lines = ["# Human Review Audit Log", ""]
    if not state.human_reviews:
        lines.append("No human review records yet.")
        return "\n".join(lines).rstrip() + "\n"

    summary = review_summary(state)
    lines.extend(
        [
            "## Summary",
            "",
            f"- Review records: {summary['review_count']}",
            f"- Actions: {_format_counts(summary['action_counts'])}",
            f"- Object types: {_format_counts(summary['object_type_counts'])}",
            f"- Locked objects: {', '.join(summary['locked_objects']) if summary['locked_objects'] else 'none'}",
            f"- Rejected objects: {', '.join(summary['rejected_objects']) if summary['rejected_objects'] else 'none'}",
            "",
            "## Records",
            "",
        ]
    )
    for record in state.human_reviews:
        lines.extend(
            [
                f"### {record.id}",
                "",
                f"- Object: `{record.object_type}:{record.object_id}`",
                f"- Action: {record.action}",
                f"- Reviewer: {record.reviewer}",
                f"- Timestamp: {record.timestamp or 'unknown'}",
                f"- Note: {record.note or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items()) if counts else "none"
