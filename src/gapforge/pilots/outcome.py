"""Final outcome classification for v0.9 pilot runs."""

from __future__ import annotations

import json

from gapforge.models import PilotOutcomeAssessment, PilotRunRecord, PilotSpec, Provenance, to_plain
from gapforge.state import utc_now_iso

DEFENSIBLE_REQUIRED = {
    "evidence_backed_gap": "evidence-backed gap",
    "related_work_matrix": "related-work matrix",
    "novelty_dossiers": "novelty dossier",
    "prior_work_recall_assessment": "prior-work recall gate",
    "experiment_protocol": "experiment protocol",
    "reviewer_panel": "reviewer panel",
    "human_review_acceptance": "human acceptance",
}

REFUSAL_REQUIRED = {
    "explicit_missing_searches_or_experiments": "explicit missing searches or experiments",
    "human_review_acceptance": "human acceptance that refusal is reasonable",
}

PRODUCT_FAILURE_MARKERS = [
    "workflow crash",
    "crash",
    "invalid codex",
    "cannot be validated",
    "not repairable",
    "fake citation",
    "fake result",
    "release gate inconsistency",
    "report overclaim",
    "system bug",
]

INCOMPLETE_MARKERS = [
    "budget exhausted",
    "human review missing",
    "live sources unavailable",
    "codex unavailable",
]


def assess_pilot_outcome(record: PilotRunRecord, spec: PilotSpec) -> PilotOutcomeAssessment:
    product_failures = _product_failures(record)
    if product_failures:
        return _assessment(
            record,
            "product_failure",
            confidence="high",
            supporting_evidence=_supporting_evidence(record),
            blocking_issues=product_failures,
            required_fixes=[_fix_for_product_failure(issue) for issue in product_failures],
            recommended_next_version="v0.9.1",
        )

    incomplete = _incomplete_issues(record)
    if incomplete:
        return _assessment(
            record,
            "incomplete",
            confidence="high",
            supporting_evidence=_supporting_evidence(record),
            blocking_issues=incomplete,
            required_fixes=[_fix_for_incomplete(issue) for issue in incomplete],
            recommended_next_version="v0.9",
        )

    missing_direction = _missing_artifacts(record, DEFENSIBLE_REQUIRED)
    if not missing_direction and _no_fake_or_overclaim(record):
        return _assessment(
            record,
            "defensible_direction",
            confidence="medium",
            supporting_evidence=[DEFENSIBLE_REQUIRED[key] for key in DEFENSIBLE_REQUIRED],
            recommended_next_version="v0.9",
        )

    refusal_blockers = _research_refusal_blockers(record)
    missing_refusal = _missing_artifacts(record, REFUSAL_REQUIRED)
    if refusal_blockers and not missing_refusal and _no_fake_or_overclaim(record):
        return _assessment(
            record,
            "correct_refusal",
            confidence="medium",
            supporting_evidence=refusal_blockers + [REFUSAL_REQUIRED[key] for key in REFUSAL_REQUIRED],
            blocking_issues=refusal_blockers,
            recommended_next_version="v0.9",
        )

    issues = missing_direction + missing_refusal + _research_refusal_blockers(record)
    if not issues:
        issues = ["Pilot has not accumulated enough evidence for direction or refusal classification."]
    return _assessment(
        record,
        "incomplete",
        confidence="medium",
        supporting_evidence=_supporting_evidence(record),
        blocking_issues=issues,
        required_fixes=[_fix_for_incomplete(issue) for issue in issues],
        recommended_next_version=_next_version_for_incomplete(issues),
    )


def render_pilot_outcome(assessment: PilotOutcomeAssessment, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(to_plain(assessment), indent=2) + "\n"
    lines = [
        f"# Pilot Outcome: {assessment.pilot_id}",
        "",
        f"- Outcome: `{assessment.outcome_type}`",
        f"- Confidence: `{assessment.confidence}`",
        f"- Recommended next version: `{assessment.recommended_next_version}`",
        "",
        "## Supporting Evidence",
        "",
    ]
    lines.extend([f"- {item}" for item in assessment.supporting_evidence] or ["- none"])
    lines.extend(["", "## Blocking Issues", ""])
    lines.extend([f"- {item}" for item in assessment.blocking_issues] or ["- none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend([f"- {item}" for item in assessment.required_fixes] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _assessment(
    record: PilotRunRecord,
    outcome_type: str,
    *,
    confidence: str,
    supporting_evidence: list[str] | None = None,
    blocking_issues: list[str] | None = None,
    required_fixes: list[str] | None = None,
    recommended_next_version: str,
) -> PilotOutcomeAssessment:
    return PilotOutcomeAssessment(
        pilot_id=record.id,
        outcome_type=outcome_type,
        confidence=confidence,
        supporting_evidence=supporting_evidence or [],
        blocking_issues=blocking_issues or [],
        required_fixes=required_fixes or [],
        recommended_next_version=recommended_next_version,
        provenance=Provenance(
            created_by_skill="pilot-outcome",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Classified the pilot outcome using explicit v0.9 evidence and failure rules.",
        ),
    )


def _supporting_evidence(record: PilotRunRecord) -> list[str]:
    evidence = sorted(key for key in record.artifact_paths if key not in {"accepted_direction_id"})
    return evidence + [blocker for blocker in record.blockers if blocker.startswith("research_refusal:")]


def _missing_artifacts(record: PilotRunRecord, required: dict[str, str]) -> list[str]:
    return [f"missing {label}" for key, label in required.items() if key not in record.artifact_paths]


def _product_failures(record: PilotRunRecord) -> list[str]:
    issues: list[str] = []
    if record.status == "product_failure" or record.outcome_type == "product_failure":
        issues.extend(record.blockers or ["product failure recorded"])
    for blocker in record.blockers:
        normalized = blocker.lower()
        if blocker.startswith("product_failure:") or any(marker in normalized for marker in PRODUCT_FAILURE_MARKERS):
            issues.append(blocker.removeprefix("product_failure:").strip())
    return _dedupe(issues)


def _incomplete_issues(record: PilotRunRecord) -> list[str]:
    issues: list[str] = []
    if record.status in {"planned", "running"} or record.outcome_type == "unknown":
        issues.append("pilot is still planned or running")
    for blocker in record.blockers:
        normalized = blocker.lower()
        if any(marker in normalized for marker in INCOMPLETE_MARKERS):
            issues.append(blocker.removeprefix("incomplete:").strip())
    if "human_review_acceptance" not in record.artifact_paths and not _product_failures(record):
        issues.append("human review missing")
    return _dedupe(issues)


def _research_refusal_blockers(record: PilotRunRecord) -> list[str]:
    blockers = []
    for blocker in record.blockers:
        normalized = blocker.lower()
        if blocker.startswith("research_refusal:") or any(term in normalized for term in ["source coverage", "novelty", "experiment"]):
            blockers.append(blocker.removeprefix("research_refusal:").strip())
    return _dedupe(blockers)


def _no_fake_or_overclaim(record: PilotRunRecord) -> bool:
    text = " ".join(record.blockers).lower()
    return not any(marker in text for marker in ["fake citation", "fake result", "overclaim", "report overclaim"])


def _fix_for_product_failure(issue: str) -> str:
    normalized = issue.lower()
    if "fake citation" in normalized:
        return "Fix citation validation so fake citations cannot pass."
    if "fake result" in normalized:
        return "Fix result validation so fake results cannot pass."
    if "codex" in normalized or "validated" in normalized:
        return "Repair Codex validation/import flow before rerunning the pilot."
    if "overclaim" in normalized:
        return "Fix report language and gates so unsupported claims cannot pass."
    return "Fix the product failure and rerun the pilot."


def _fix_for_incomplete(issue: str) -> str:
    normalized = issue.lower()
    if "human review" in normalized:
        return "Record human review acceptance or rejection."
    if "live sources" in normalized:
        return "Retry live sources or record a source-coverage refusal."
    if "codex unavailable" in normalized:
        return "Use task-pack/manual handoff or record Codex unavailability."
    if "budget" in normalized:
        return "Increase budget or record refusal based on exhausted budget."
    return "Complete missing pilot evidence or record an explicit refusal blocker."


def _next_version_for_incomplete(issues: list[str]) -> str:
    joined = " ".join(issues).lower()
    if "system bug" in joined or "missing required artifacts due to system bug" in joined:
        return "v0.9.1"
    if "human review" in joined or "live sources" in joined or "codex unavailable" in joined or "budget" in joined:
        return "v0.9"
    return "v1_blocker"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
