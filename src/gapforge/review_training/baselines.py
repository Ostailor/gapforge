"""Deterministic reviewer baselines for calibration."""

from __future__ import annotations

from gapforge.models import Provenance
from gapforge.review_training.schemas import ReviewDatasetPaper
from gapforge.review_training.taxonomy import ReviewIssueLabel
from gapforge.state import slugify, utc_now_iso

GATE_MAP = {
    "novelty weakness": "novelty_gate",
    "insufficient related work": "related_work_gate",
    "weak baselines": "baseline_strength_gate",
    "missing ablation": "experiment_design_gate",
    "poor metric choice": "metric_registry_gate",
    "underpowered statistics": "statistical_power_gate",
    "unclear contribution": "manuscript_clarity_gate",
    "overclaiming": "claim_traceability_gate",
    "dataset limitation": "dataset_validity_gate",
    "reproducibility issue": "reproducibility_gate",
    "ethics/safety issue": "ethics_safety_gate",
    "writing clarity": "manuscript_clarity_gate",
    "theory gap": "theory_assumption_gate",
    "experiment mismatch": "experiment_protocol_gate",
    "artifact weakness": "artifact_evaluation_gate",
}


class HeuristicBaselineReviewer:
    """Generate conservative critique labels from paper metadata only."""

    model_type = "heuristic"

    def predict(self, papers: list[ReviewDatasetPaper], *, model_id: str) -> list[ReviewIssueLabel]:
        labels: list[ReviewIssueLabel] = []
        for paper in papers:
            issue_types = _issue_types_for_paper(paper)
            for issue_type in issue_types:
                labels.append(_label_for_issue(paper, issue_type, model_id=model_id))
        return labels


class RetrievalCalibratedReviewer(HeuristicBaselineReviewer):
    """Heuristic baseline with taxonomy-prior issue expansion."""

    model_type = "retrieval_calibrated"

    def predict(self, papers: list[ReviewDatasetPaper], *, model_id: str) -> list[ReviewIssueLabel]:
        labels = super().predict(papers, model_id=model_id)
        for paper in papers:
            if paper.average_score < 7:
                labels.append(_label_for_issue(paper, "weak baselines", model_id=model_id))
                labels.append(_label_for_issue(paper, "missing ablation", model_id=model_id))
        return _dedupe(labels)


def reviewer_for_mode(mode: str) -> HeuristicBaselineReviewer:
    if mode == "heuristic":
        return HeuristicBaselineReviewer()
    if mode == "retrieval_calibrated":
        return RetrievalCalibratedReviewer()
    return HeuristicBaselineReviewer()


def _issue_types_for_paper(paper: ReviewDatasetPaper) -> list[str]:
    text = f"{paper.title} {paper.abstract} {' '.join(paper.topic_tags)}".lower()
    issues: list[str] = []
    if "benchmark" in text or "dataset" in text or "evaluation" in text:
        issues.extend(["dataset limitation", "experiment mismatch", "reproducibility issue"])
    if "safety" in text or "monitor" in text or "risk" in text:
        issues.append("ethics/safety issue")
    if "broad claim" in text or paper.decision.lower() in {"reject", "rejected"} or paper.average_score <= 4:
        issues.extend(["overclaiming", "novelty weakness", "writing clarity"])
    if paper.average_score > 0 and paper.average_score < 7:
        issues.extend(["weak baselines", "missing ablation"])
    if not paper.pdf_path:
        issues.append("artifact weakness")
    return _unique(issues)


def _label_for_issue(paper: ReviewDatasetPaper, issue_type: str, *, model_id: str) -> ReviewIssueLabel:
    severity = _severity_for_paper(paper, issue_type)
    evidence = (
        f"paper:{paper.id} metadata suggests `{issue_type}` should be checked; decision={paper.decision or 'unknown'}, "
        f"average_score={paper.average_score:.2f}, tags={', '.join(paper.topic_tags) or 'none'}."
    )
    return ReviewIssueLabel(
        id=f"review-label-{slugify(model_id)}-{slugify(paper.id)}-{slugify(issue_type)}",
        review_id=model_id,
        paper_id=paper.id,
        issue_type=issue_type,
        severity=severity,
        evidence_text=evidence,
        mapped_gapforge_gate=GATE_MAP.get(issue_type, "manual_review_gate"),
        provenance=Provenance(
            created_by_skill="reviewer-baseline",
            source_ids=[model_id, paper.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Generated a deterministic reviewer baseline issue label from paper metadata only.",
        ),
    )


def _severity_for_paper(paper: ReviewDatasetPaper, issue_type: str) -> str:
    if paper.average_score > 0 and paper.average_score <= 3:
        return "fatal" if issue_type in {"overclaiming", "reproducibility issue", "experiment mismatch"} else "major"
    if paper.decision.lower() in {"reject", "rejected"} and issue_type in {"overclaiming", "novelty weakness"}:
        return "fatal"
    if paper.average_score and paper.average_score < 7:
        return "major"
    return "minor"


def _dedupe(labels: list[ReviewIssueLabel]) -> list[ReviewIssueLabel]:
    result: list[ReviewIssueLabel] = []
    seen: set[tuple[str, str, str]] = set()
    for label in labels:
        key = (label.review_id, label.paper_id, label.issue_type)
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
