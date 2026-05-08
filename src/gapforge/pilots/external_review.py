"""External human review capture for v0.9 pilot outcomes."""

from __future__ import annotations

from collections.abc import Iterable

from gapforge.config import GapForgeConfig
from gapforge.models import ExternalPilotReview, PilotRunRecord, Provenance
from gapforge.pilots.status import PilotStore, build_acceptance_summary
from gapforge.state import utc_now_iso

REVIEWER_ROLES = {"user", "domain_expert", "engineer", "external_reviewer", "unknown"}
PRODUCT_FAILURE_MARKERS = ["product failure", "workflow crash", "invalid codex", "fake citation", "fake result", "overclaim"]


class ExternalPilotReviewManager:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = PilotStore(config)

    def create_review(
        self,
        pilot_id: str,
        *,
        reviewer_name: str = "human reviewer",
        reviewer_role: str = "unknown",
        review_scope: list[str] | None = None,
        novelty_assessment: str = "",
        evidence_assessment: str = "",
        experiment_assessment: str = "",
        manuscript_assessment: str = "",
        artifact_assessment: str = "",
        major_concerns: list[str] | None = None,
        accept_outcome: bool = False,
        reject_outcome: bool = False,
        reason: str = "",
        required_fixes: list[str] | None = None,
        notes: str = "",
    ) -> ExternalPilotReview:
        record = self.store.load_record(pilot_id)
        role = reviewer_role if reviewer_role in REVIEWER_ROLES else "unknown"
        concerns = _dedupe((major_concerns or []) + _classified_concerns(record, reason, accept_outcome, reject_outcome))
        fixes = _dedupe((required_fixes or []) + _required_fixes(record, concerns, accept_outcome, reject_outcome, reason))
        blocked_by_fake_result = _has_fake_citation_or_result(record, concerns, fixes)
        accepted_outcome = (
            accept_outcome and not reject_outcome and not blocked_by_fake_result and not _is_product_failure(record, concerns)
        )
        review = ExternalPilotReview(
            id=f"review-{record.id}-{utc_now_iso().replace(':', '').replace('.', '')}",
            pilot_id=record.id,
            reviewer_name=reviewer_name,
            reviewer_role=role,
            reviewed_at=utc_now_iso(),
            review_scope=review_scope or _default_scope(record),
            novelty_assessment=novelty_assessment,
            evidence_assessment=evidence_assessment,
            experiment_assessment=experiment_assessment,
            manuscript_assessment=manuscript_assessment,
            artifact_assessment=artifact_assessment,
            major_concerns=concerns,
            accepted_outcome=accepted_outcome,
            required_fixes=fixes,
            notes=notes or reason,
            provenance=Provenance(
                created_by_skill="external-pilot-review",
                source_ids=[record.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Captured human pilot review separately from automated outcome classification.",
            ),
        )
        review_path = self.store.save_external_review(record, review)
        _apply_review_to_record(record, review, str(review_path))
        self.store.save_record(record)
        summary = build_acceptance_summary(record, reviews=self.store.load_external_reviews(record.id))
        self.store.save_acceptance(record, summary)
        return review

    def load_reviews(self, pilot_id: str) -> list[ExternalPilotReview]:
        return self.store.load_external_reviews(pilot_id)

    def render_report(self, pilot_id: str) -> str:
        record = self.store.load_record(pilot_id)
        return render_external_review_report(record, self.store.load_external_reviews(record.id))


def render_external_review_report(record: PilotRunRecord, reviews: list[ExternalPilotReview]) -> str:
    lines = [
        f"# External Pilot Review: {record.id}",
        "",
        f"- Pilot: `{record.pilot_id}`",
        f"- Status: `{record.status}`",
        f"- Outcome: `{record.outcome_type}`",
        f"- Review count: {len(reviews)}",
        "",
    ]
    if not reviews:
        lines.extend(["No external pilot review has been recorded.", ""])
        return "\n".join(lines)
    for review in reviews:
        lines.extend(
            [
                f"## Review `{review.id}`",
                "",
                f"- Reviewer: {review.reviewer_name or 'unknown'}",
                f"- Role: `{review.reviewer_role}`",
                f"- Reviewed at: `{review.reviewed_at}`",
                f"- Accepted outcome: {str(review.accepted_outcome).lower()}",
                f"- Scope: {', '.join(review.review_scope) or 'unspecified'}",
                "",
                "### Assessments",
                "",
                f"- Novelty: {review.novelty_assessment or 'not recorded'}",
                f"- Evidence: {review.evidence_assessment or 'not recorded'}",
                f"- Experiment: {review.experiment_assessment or 'not recorded'}",
                f"- Manuscript: {review.manuscript_assessment or 'not recorded'}",
                f"- Artifact: {review.artifact_assessment or 'not recorded'}",
                "",
                "### Major Concerns",
                "",
            ]
        )
        lines.extend([f"- {concern}" for concern in review.major_concerns] or ["- none"])
        lines.extend(["", "### Required Fixes", ""])
        lines.extend([f"- {fix}" for fix in review.required_fixes] or ["- none"])
        lines.extend(["", "### Notes", "", review.notes or "none", ""])
    return "\n".join(lines).rstrip() + "\n"


def _apply_review_to_record(record: PilotRunRecord, review: ExternalPilotReview, review_path: str) -> None:
    record.artifact_paths["external_pilot_review"] = review_path
    if review.accepted_outcome:
        record.artifact_paths["external_review_acceptance"] = review_path
        record.artifact_paths["human_review_acceptance"] = review_path
        if record.outcome_type in {"defensible_direction", "correct_refusal"}:
            record.status = "accepted"
    else:
        record.artifact_paths.pop("external_review_acceptance", None)
        record.artifact_paths.pop("human_review_acceptance", None)
        if _is_product_failure(record, review.major_concerns) or _has_fake_citation_or_result(
            record, review.major_concerns, review.required_fixes
        ):
            record.status = "product_failure"
            record.outcome_type = "product_failure"
        elif record.status == "accepted":
            record.status = "rejected"
        if review.required_fixes:
            for fix in review.required_fixes:
                blocker = f"external_review: {fix}"
                if blocker not in record.blockers:
                    record.blockers.append(blocker)


def _classified_concerns(record: PilotRunRecord, reason: str, accept_outcome: bool, reject_outcome: bool) -> list[str]:
    concerns: list[str] = []
    reason_text = reason.strip()
    if _is_product_failure(record, [reason_text]) or _has_fake_citation_or_result(record, [reason_text], []):
        concerns.append(f"product_failure: {reason_text or 'product failure blocks pilot acceptance'}")
    elif reject_outcome:
        if "disagree" in reason_text.lower():
            concerns.append(f"research_disagreement: {reason_text}")
        elif "evidence" in reason_text.lower() or "insufficient" in reason_text.lower():
            concerns.append(f"insufficient_evidence: {reason_text}")
        else:
            concerns.append(f"research_disagreement: {reason_text or 'reviewer rejected the pilot outcome'}")
    elif accept_outcome and record.outcome_type == "correct_refusal":
        concerns.append("accepted_refusal: reviewer accepts the refusal as the correct pilot outcome")
    elif accept_outcome and record.outcome_type == "defensible_direction":
        concerns.append("accepted_direction: reviewer accepts the direction as the correct pilot outcome")
    elif not accept_outcome:
        concerns.append("insufficient_evidence: outcome has not been accepted by human review")
    return concerns


def _required_fixes(
    record: PilotRunRecord,
    concerns: list[str],
    accept_outcome: bool,
    reject_outcome: bool,
    reason: str,
) -> list[str]:
    fixes: list[str] = []
    if _has_fake_citation_or_result(record, concerns, []):
        fixes.append("Resolve fake citation/result validation before accepting the pilot outcome.")
    if _is_product_failure(record, concerns):
        fixes.append("Fix the product failure and rerun or repair the pilot before acceptance.")
    if reject_outcome and reason:
        fixes.append(reason)
    if not accept_outcome and not reject_outcome:
        fixes.append("Record explicit acceptance or rejection from a human reviewer.")
    return fixes


def _default_scope(record: PilotRunRecord) -> list[str]:
    if record.outcome_type == "defensible_direction":
        return ["novelty", "evidence", "experiment", "manuscript", "artifact"]
    if record.outcome_type == "correct_refusal":
        return ["source_coverage", "novelty", "experiment_tractability", "refusal"]
    if record.outcome_type == "product_failure":
        return ["product_failure", "artifact", "report"]
    return ["pilot_outcome"]


def _is_product_failure(record: PilotRunRecord, concerns: Iterable[str]) -> bool:
    text = " ".join([record.status, record.outcome_type, *record.blockers, *concerns]).lower()
    return any(marker in text for marker in PRODUCT_FAILURE_MARKERS) or "product_failure:" in text


def _has_fake_citation_or_result(record: PilotRunRecord, concerns: Iterable[str], fixes: Iterable[str]) -> bool:
    text = " ".join([*record.blockers, *concerns, *fixes]).lower()
    return "fake citation" in text or "fake result" in text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
