"""Issue-level tracking for harsh reviewer blockers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import Provenance, ReviewerReview, from_dict, to_plain
from gapforge.reviewers.drastic_panel import DrasticReviewPanel, DrasticReviewPanelBuilder
from gapforge.state import utc_now_iso

REVIEW_ISSUE_STATUSES = {"open", "in_progress", "resolved", "waived", "impossible"}
EVIDENCE_LINK_RE = re.compile(r"\b(?:artifact|manuscript|search|experiment):[^\s]+", re.IGNORECASE)
HUMAN_REVIEW_RE = re.compile(r"\b(?:human_review|human-review):[^\s]+", re.IGNORECASE)


@dataclass(slots=True)
class ReviewIssue:
    id: str
    source_review_id: str
    issue_type: str
    severity: str
    text: str
    affected_sections: list[str] = field(default_factory=list)
    required_fix: str = ""
    status: str = "open"
    resolution_evidence: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-issue-tracker"))


class ReviewIssueTracker:
    """Convert drastic-review outputs into a durable issue checklist."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscripts = ManuscriptManager(config)

    def build_from_drastic_review(self, manuscript_id: str) -> list[ReviewIssue]:
        panel = self._load_or_create_panel(manuscript_id)
        existing = {issue.id: issue for issue in self.load(manuscript_id)}
        issues: list[ReviewIssue] = []
        for review in panel.reviewer_reports:
            issues.extend(_issues_from_review(review, manuscript_id=manuscript_id, panel_id=panel.id))
        merged = [_merge_existing(issue, existing.get(issue.id)) for issue in _dedupe_issues(issues)]
        self.save(manuscript_id, merged)
        return merged

    def load(self, manuscript_id: str) -> list[ReviewIssue]:
        path = self.issue_path(manuscript_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [_issue_from_dict(item) for item in payload.get("issues", [])]

    def save(self, manuscript_id: str, issues: list[ReviewIssue]) -> None:
        path = self.issue_path(manuscript_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"manuscript_id": manuscript_id, "issues": [to_plain(issue) for issue in issues]}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.report_path(manuscript_id).write_text(render_review_issues(manuscript_id, issues), encoding="utf-8")

    def resolve_issue(self, issue_id: str, *, evidence: str, status: str = "resolved") -> ReviewIssue:
        if status not in REVIEW_ISSUE_STATUSES - {"open"}:
            raise ValueError(f"Unsupported review issue status: {status}")
        _validate_resolution_evidence(evidence)
        manuscript_id, issues = self._find_issue(issue_id)
        updated: ReviewIssue | None = None
        for issue in issues:
            if issue.id != issue_id:
                continue
            if issue.severity == "fatal" and status == "waived" and not HUMAN_REVIEW_RE.search(evidence):
                raise ValueError("Waiving a fatal review issue requires human_review:<id> evidence.")
            issue.status = status
            issue.resolution_evidence = _unique([*issue.resolution_evidence, evidence])
            issue.provenance = Provenance(
                created_by_skill="review-issue-tracker",
                source_ids=_unique([issue.source_review_id, issue.id, evidence]),
                timestamp=utc_now_iso(),
                reasoning_summary="Updated review issue status with linked artifact/manuscript/search/experiment evidence.",
            )
            updated = issue
        if updated is None:
            raise FileNotFoundError(f"No review issue found for {issue_id}")
        self.save(manuscript_id, issues)
        return updated

    def status(self, manuscript_id: str) -> dict[str, Any]:
        issues = self.load(manuscript_id)
        return review_issue_status(manuscript_id, issues)

    def issue_path(self, manuscript_id: str) -> Path:
        return self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic" / "review_issues.json"

    def report_path(self, manuscript_id: str) -> Path:
        return self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic" / "review_issues.md"

    def _load_or_create_panel(self, manuscript_id: str) -> DrasticReviewPanel:
        path = self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic" / "drastic_review_panel.json"
        if path.exists():
            return from_dict(DrasticReviewPanel, json.loads(path.read_text(encoding="utf-8")))
        return DrasticReviewPanelBuilder(self.config).review_manuscript(manuscript_id)

    def _find_issue(self, issue_id: str) -> tuple[str, list[ReviewIssue]]:
        for path in sorted(self.config.project_root.glob("*/manuscripts/*/reviews/drastic/review_issues.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            issues = [_issue_from_dict(item) for item in payload.get("issues", [])]
            if any(issue.id == issue_id for issue in issues):
                return str(payload.get("manuscript_id") or path.parents[2].name), issues
        raise FileNotFoundError(f"No review issue found for {issue_id}")


def review_issue_status(manuscript_id: str, issues: list[ReviewIssue]) -> dict[str, Any]:
    open_fatal = [issue.id for issue in issues if issue.severity == "fatal" and issue.status in {"open", "in_progress"}]
    impossible_fatal = [issue.id for issue in issues if issue.severity == "fatal" and issue.status == "impossible"]
    waived_fatal = [issue.id for issue in issues if issue.severity == "fatal" and issue.status == "waived"]
    unjustified_waived_fatal = [
        issue.id
        for issue in issues
        if issue.severity == "fatal"
        and issue.status == "waived"
        and not any(HUMAN_REVIEW_RE.search(evidence) for evidence in issue.resolution_evidence)
    ]
    closed = [issue.id for issue in issues if issue.status in {"resolved", "waived"}]
    open_issues = [issue.id for issue in issues if issue.status in {"open", "in_progress"}]
    impossible_issues = [issue.id for issue in issues if issue.status == "impossible"]
    conference_ready_allowed = bool(issues) and not open_issues and not impossible_issues and not unjustified_waived_fatal
    return {
        "manuscript_id": manuscript_id,
        "total_issues": len(issues),
        "open_issue_ids": open_issues,
        "open_fatal_issue_ids": open_fatal,
        "impossible_issue_ids": impossible_issues,
        "impossible_fatal_issue_ids": impossible_fatal,
        "waived_fatal_issue_ids": waived_fatal,
        "unjustified_waived_fatal_issue_ids": unjustified_waived_fatal,
        "closed_issue_ids": closed,
        "conference_ready_allowed": conference_ready_allowed,
    }


def render_review_issues(manuscript_id: str, issues: list[ReviewIssue]) -> str:
    lines = [
        f"# Review Issues `{manuscript_id}`",
        "",
        "Harsh review checklist. Fatal issues must be resolved or explicitly waived/no-go before conference candidacy.",
        "",
    ]
    for issue in issues:
        lines.extend(
            [
                f"## {issue.id}",
                "",
                f"- Source review: `{issue.source_review_id}`",
                f"- Type: `{issue.issue_type}`",
                f"- Severity: `{issue.severity}`",
                f"- Status: `{issue.status}`",
                f"- Affected sections: {', '.join(issue.affected_sections) or 'unknown'}",
                f"- Required fix: {issue.required_fix or 'unspecified'}",
                f"- Text: {issue.text}",
                "- Resolution evidence:",
            ]
        )
        lines.extend([f"  - {item}" for item in issue.resolution_evidence] or ["  - none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_review_issue_status(status: dict[str, Any]) -> str:
    lines = [
        f"# Review Issue Status `{status['manuscript_id']}`",
        "",
        f"- total_issues: {status['total_issues']}",
        f"- open_issues: {len(status['open_issue_ids'])}",
        f"- open_fatal_issues: {len(status['open_fatal_issue_ids'])}",
        f"- impossible_fatal_issues: {len(status['impossible_fatal_issue_ids'])}",
        f"- waived_fatal_issues: {len(status['waived_fatal_issue_ids'])}",
        f"- unjustified_waived_fatal_issues: {len(status['unjustified_waived_fatal_issue_ids'])}",
        f"- conference_ready_allowed: {str(status['conference_ready_allowed']).lower()}",
        "",
        "## Open Fatal Issues",
        "",
    ]
    lines.extend([f"- `{item}`" for item in status["open_fatal_issue_ids"]] or ["- none"])
    lines.extend(["", "## Unjustified Waived Fatal Issues", ""])
    lines.extend([f"- `{item}`" for item in status["unjustified_waived_fatal_issue_ids"]] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _issues_from_review(review: ReviewerReview, *, manuscript_id: str, panel_id: str) -> list[ReviewIssue]:
    issues = []
    for index, text in enumerate(review.fatal_flaws):
        issues.append(_new_issue(review, manuscript_id, panel_id, text, severity="fatal", index=index))
    for index, text in enumerate(review.weaknesses):
        issues.append(_new_issue(review, manuscript_id, panel_id, text, severity="major", index=index))
    return issues


def _new_issue(
    review: ReviewerReview,
    manuscript_id: str,
    panel_id: str,
    text: str,
    *,
    severity: str,
    index: int,
) -> ReviewIssue:
    source_review_id = f"{panel_id}:{review.reviewer_id}"
    issue_type = _issue_type(review, text)
    issue_id = _issue_id(manuscript_id, source_review_id, severity, text)
    return ReviewIssue(
        id=issue_id,
        source_review_id=source_review_id,
        issue_type=issue_type,
        severity=severity,
        text=text,
        affected_sections=_affected_sections(text, review.required_fixes),
        required_fix=_required_fix(text, review.required_fixes, index),
        status="open",
        resolution_evidence=[],
        provenance=Provenance(
            created_by_skill="review-issue-tracker",
            source_ids=_unique([manuscript_id, panel_id, review.reviewer_id]),
            timestamp=utc_now_iso(),
            reasoning_summary="Converted harsh reviewer finding into an issue-level checklist item.",
        ),
    )


def _issue_id(manuscript_id: str, source_review_id: str, severity: str, text: str) -> str:
    digest = hashlib.sha1(f"{manuscript_id}|{source_review_id}|{severity}|{text}".encode()).hexdigest()[:10]
    return f"review-issue-{digest}"


def _issue_type(review: ReviewerReview, text: str) -> str:
    lower = f"{review.role} {text}".lower()
    if "benchmark" in lower or "synthetic" in lower:
        return "benchmark_validity"
    if "baseline" in lower or "empirical" in lower or "underpowered" in lower:
        return "baseline_or_empirical"
    if "artifact" in lower or "reproduc" in lower:
        return "artifact_reproducibility"
    if "related" in lower or "novelty" in lower or "prior work" in lower:
        return "novelty_related_work"
    if "clarity" in lower or "framing" in lower or "contribution" in lower:
        return "contribution_framing"
    return "review_objection"


def _affected_sections(text: str, required_fixes: list[str]) -> list[str]:
    combined = " ".join([text, *required_fixes]).lower()
    sections = []
    for section in ["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations", "artifact_appendix"]:
        if section in combined or section.replace("_", " ") in combined:
            sections.append(section)
    if "benchmark" in combined and "experiments" not in sections:
        sections.append("experiments")
    if "artifact" in combined and "artifact_appendix" not in sections:
        sections.append("artifact_appendix")
    if "baseline" in combined and "experiments" not in sections:
        sections.append("experiments")
    if "synthetic" in combined and "limitations" not in sections:
        sections.append("limitations")
    return _unique(sections) or ["manuscript"]


def _required_fix(text: str, required_fixes: list[str], index: int) -> str:
    if not required_fixes:
        return "manuscript: add evidence-linked revision or preserve as blocker."
    text_tokens = _tokens(text)
    ranked = sorted(required_fixes, key=lambda fix: len(text_tokens & _tokens(fix)), reverse=True)
    best = ranked[0]
    if len(text_tokens & _tokens(best)) > 0:
        return best
    return required_fixes[min(index, len(required_fixes) - 1)]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_:-]+", text.lower()) if len(token) > 3}


def _merge_existing(issue: ReviewIssue, existing: ReviewIssue | None) -> ReviewIssue:
    if existing is None:
        return issue
    issue.status = existing.status
    issue.resolution_evidence = list(existing.resolution_evidence)
    issue.provenance = existing.provenance
    return issue


def _dedupe_issues(issues: list[ReviewIssue]) -> list[ReviewIssue]:
    seen = set()
    unique = []
    for issue in issues:
        if issue.id in seen:
            continue
        seen.add(issue.id)
        unique.append(issue)
    return unique


def _issue_from_dict(data: dict[str, Any]) -> ReviewIssue:
    payload = dict(data)
    provenance = payload.get("provenance")
    if isinstance(provenance, dict):
        payload["provenance"] = from_dict(Provenance, provenance)
    elif provenance is None:
        payload["provenance"] = Provenance(created_by_skill="review-issue-tracker")
    return ReviewIssue(**payload)


def _validate_resolution_evidence(evidence: str) -> None:
    if not EVIDENCE_LINK_RE.search(evidence):
        raise ValueError("Issue resolution must link to artifact/manuscript/search/experiment evidence.")


def _unique(items) -> list[str]:  # noqa: ANN001
    seen = set()
    result: list[str] = []
    for item in items:
        value = str(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
