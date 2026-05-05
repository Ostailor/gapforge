"""Apply auditable human edits to a research run state."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from gapforge.models import Evidence, HumanReviewRecord, Provenance, ResearchRunState, to_plain
from gapforge.review.audit import is_locked
from gapforge.state import utc_now_iso

VALID_OBJECT_TYPES = {"paper", "claim", "gap", "novelty_assessment", "experiment", "reviewer_objection"}
VALID_ACTIONS = {"approve", "reject", "revise", "annotate", "lock", "unlock"}
VALID_CLAIM_STATUSES = {"supported", "contested", "uncertain", "falsified"}


class HumanReviewEditor:
    """Small command-oriented editor for human review actions."""

    def approve_gap(self, state: ResearchRunState, gap_id: str, *, note: str = "", reviewer: str = "human") -> HumanReviewRecord:
        self._require_object(state, "gap", gap_id)
        return self._record(state, "gap", gap_id, "approve", note=note, reviewer=reviewer)

    def reject_gap(self, state: ResearchRunState, gap_id: str, *, reason: str, reviewer: str = "human") -> HumanReviewRecord:
        gap = self._require_object(state, "gap", gap_id)
        before = self._snapshot(state, "gap", gap_id)
        if reason and hasattr(gap, "risk_that_gap_is_fake") and not gap.risk_that_gap_is_fake:
            gap.risk_that_gap_is_fake = reason
        return self._record(state, "gap", gap_id, "reject", note=reason, reviewer=reviewer, before_snapshot=before)

    def annotate_claim(self, state: ResearchRunState, claim_id: str, *, note: str, reviewer: str = "human") -> HumanReviewRecord:
        claim = self._require_object(state, "claim", claim_id)
        before = self._snapshot(state, "claim", claim_id)
        claim.notes = f"{claim.notes}\nHuman note: {note}".strip() if note else claim.notes
        return self._record(state, "claim", claim_id, "annotate", note=note, reviewer=reviewer, before_snapshot=before)

    def mark_claim(self, state: ResearchRunState, claim_id: str, *, status: str, reviewer: str = "human") -> HumanReviewRecord:
        if status not in VALID_CLAIM_STATUSES:
            raise ValueError(f"Unsupported claim status: {status}")
        claim = self._require_object(state, "claim", claim_id)
        before = self._snapshot(state, "claim", claim_id)
        claim.status = status
        claim.needs_verification = status != "supported"
        return self._record(
            state,
            "claim",
            claim_id,
            "revise",
            note=f"Marked claim as {status}.",
            reviewer=reviewer,
            before_snapshot=before,
        )

    def add_evidence(
        self,
        state: ResearchRunState,
        claim_id: str,
        *,
        paper_id: str,
        quote: str,
        locator: str,
        reviewer: str = "human",
    ) -> HumanReviewRecord:
        if not quote.strip():
            raise ValueError("Manual evidence requires a non-empty quote.")
        if paper_id not in {paper.id for paper in state.papers}:
            raise KeyError(f"Unknown paper: {paper_id}")
        claim = self._require_object(state, "claim", claim_id)
        before = self._snapshot(state, "claim", claim_id)
        evidence = Evidence(
            source_id=paper_id,
            source_paper_id=paper_id,
            quote=quote,
            locator=locator or paper_id,
            confidence="medium",
            notes="Manually supplied evidence.",
        )
        claim.supporting_evidence.append(evidence)
        if paper_id not in claim.source_paper_ids:
            claim.source_paper_ids.append(paper_id)
        claim.status = "supported"
        claim.needs_verification = False
        return self._record(
            state,
            "claim",
            claim_id,
            "revise",
            note=f"Added manual evidence from {paper_id}: {locator or paper_id}",
            reviewer=reviewer,
            before_snapshot=before,
        )

    def lock_object(
        self,
        state: ResearchRunState,
        object_type: str,
        object_id: str,
        *,
        note: str = "",
        reviewer: str = "human",
        force: bool = False,
    ) -> HumanReviewRecord:
        self._validate_object_type(object_type)
        self._require_object(state, object_type, object_id)
        if is_locked(state, object_type, object_id) and not force:
            raise ValueError(f"{object_type}:{object_id} is already locked. Use --force to record another lock.")
        return self._record(state, object_type, object_id, "lock", note=note, reviewer=reviewer)

    def unlock_object(
        self,
        state: ResearchRunState,
        object_type: str,
        object_id: str,
        *,
        note: str = "",
        reviewer: str = "human",
    ) -> HumanReviewRecord:
        self._validate_object_type(object_type)
        self._require_object(state, object_type, object_id)
        return self._record(state, object_type, object_id, "unlock", note=note, reviewer=reviewer)

    def _record(
        self,
        state: ResearchRunState,
        object_type: str,
        object_id: str,
        action: str,
        *,
        note: str,
        reviewer: str,
        before_snapshot: dict[str, Any] | None = None,
    ) -> HumanReviewRecord:
        self._validate_object_type(object_type)
        if action not in VALID_ACTIONS:
            raise ValueError(f"Unsupported human review action: {action}")
        before = before_snapshot if before_snapshot is not None else self._snapshot(state, object_type, object_id)
        after = self._snapshot(state, object_type, object_id)
        record = HumanReviewRecord(
            id=f"review-{len(state.human_reviews) + 1}",
            object_type=object_type,
            object_id=object_id,
            action=action,
            note=note,
            reviewer=reviewer,
            timestamp=utc_now_iso(),
            before_snapshot=before,
            after_snapshot=after,
            provenance=Provenance(
                created_by_skill="human-review",
                source_ids=[object_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Human review action recorded as an auditable public edit summary.",
            ),
        )
        state.human_reviews.append(record)
        return record

    def _require_object(self, state: ResearchRunState, object_type: str, object_id: str) -> Any:
        obj = self._find_object(state, object_type, object_id)
        if obj is None:
            raise KeyError(f"Unknown {object_type}: {object_id}")
        return obj

    def _snapshot(self, state: ResearchRunState, object_type: str, object_id: str) -> dict[str, Any]:
        obj = self._find_object(state, object_type, object_id)
        return to_plain(obj) if obj is not None else {}

    def _find_object(self, state: ResearchRunState, object_type: str, object_id: str) -> Any:
        self._validate_object_type(object_type)
        collections: dict[str, Sequence[Any]] = {
            "paper": state.papers,
            "claim": state.claims,
            "gap": state.gaps,
            "novelty_assessment": state.novelty_assessments,
            "experiment": state.experiments,
            "reviewer_objection": state.reviewer_objections,
        }
        id_attrs = {
            "paper": "id",
            "claim": "id",
            "gap": "id",
            "novelty_assessment": "target_gap_or_hypothesis_id",
            "experiment": "id",
            "reviewer_objection": "id",
        }
        attr = id_attrs[object_type]
        for item in collections[object_type]:
            if getattr(item, attr) == object_id:
                return item
        return None

    def _validate_object_type(self, object_type: str) -> None:
        if object_type not in VALID_OBJECT_TYPES:
            raise ValueError(f"Unsupported object type: {object_type}")
