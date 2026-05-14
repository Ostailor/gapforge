"""Heuristic review issue taxonomy for reviewer calibration."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.review_training.openreview_dataset import ReviewDatasetBuilder
from gapforge.review_training.schemas import ReviewDatasetPaper, ReviewRecord
from gapforge.state import slugify, utc_now_iso

ISSUE_TYPES = {
    "novelty weakness",
    "insufficient related work",
    "weak baselines",
    "missing ablation",
    "poor metric choice",
    "underpowered statistics",
    "unclear contribution",
    "overclaiming",
    "dataset limitation",
    "reproducibility issue",
    "ethics/safety issue",
    "writing clarity",
    "theory gap",
    "experiment mismatch",
    "artifact weakness",
}
SEVERITIES = {"minor", "major", "fatal"}


@dataclass(slots=True)
class ReviewIssueLabel:
    id: str
    review_id: str
    paper_id: str
    issue_type: str
    severity: str
    evidence_text: str
    mapped_gapforge_gate: str
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-taxonomy"))


@dataclass(slots=True)
class ReviewTaxonomyReport:
    dataset_id: str
    issue_counts: dict[str, int] = field(default_factory=dict)
    severity_counts: dict[str, int] = field(default_factory=dict)
    venue_patterns: dict[str, dict[str, int]] = field(default_factory=dict)
    examples: dict[str, list[str]] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="review-taxonomy"))


class ReviewTaxonomyLabeler:
    """Generate auditable heuristic issue labels from structured reviews."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.datasets = ReviewDatasetBuilder(config)

    def generate(self, dataset_id: str) -> list[ReviewIssueLabel]:
        papers = {paper.id: paper for paper in self.datasets.list_papers(dataset_id)}
        labels: list[ReviewIssueLabel] = []
        for review in self.datasets.list_reviews(dataset_id):
            labels.extend(_labels_for_review(review, papers.get(review.paper_id)))
        self._write_labels(dataset_id, labels)
        self._write_report(dataset_id, labels, list(papers.values()))
        return labels

    def list_labels(self, dataset_id: str) -> list[ReviewIssueLabel]:
        labels_dir = self._labels_dir(dataset_id)
        if not labels_dir.exists():
            return self.generate(dataset_id)
        return [
            from_dict(ReviewIssueLabel, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(labels_dir.glob("review-label-*.json"))
        ]

    def build_report(self, dataset_id: str) -> ReviewTaxonomyReport:
        labels = self.list_labels(dataset_id)
        papers = self.datasets.list_papers(dataset_id)
        return _taxonomy_report(dataset_id, labels, papers)

    def render_report(self, dataset_id: str) -> str:
        labels = self.list_labels(dataset_id)
        papers = self.datasets.list_papers(dataset_id)
        report = _taxonomy_report(dataset_id, labels, papers)
        markdown = render_review_taxonomy_report(report)
        report_dir = self._dataset_dir(dataset_id) / "taxonomy"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "review_taxonomy_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (report_dir / "review_taxonomy_report.md").write_text(markdown, encoding="utf-8")
        return markdown

    def _write_labels(self, dataset_id: str, labels: list[ReviewIssueLabel]) -> None:
        labels_dir = self._labels_dir(dataset_id)
        labels_dir.mkdir(parents=True, exist_ok=True)
        for stale in labels_dir.glob("review-label-*.json"):
            stale.unlink()
        for label in labels:
            (labels_dir / f"{label.id}.json").write_text(json.dumps(to_plain(label), indent=2) + "\n", encoding="utf-8")

    def _write_report(self, dataset_id: str, labels: list[ReviewIssueLabel], papers: list[ReviewDatasetPaper]) -> None:
        report = _taxonomy_report(dataset_id, labels, papers)
        report_dir = self._dataset_dir(dataset_id) / "taxonomy"
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "review_taxonomy_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (report_dir / "review_taxonomy_report.md").write_text(render_review_taxonomy_report(report), encoding="utf-8")

    def _dataset_dir(self, dataset_id: str) -> Path:
        path = self.config.data_dir / "review_training" / "datasets" / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _labels_dir(self, dataset_id: str) -> Path:
        return self._dataset_dir(dataset_id) / "taxonomy" / "labels"


def render_review_labels(labels: list[ReviewIssueLabel]) -> str:
    return json.dumps(to_plain(labels), indent=2) + "\n"


def render_review_taxonomy_report(report: ReviewTaxonomyReport) -> str:
    lines = [
        f"# Review Taxonomy Report `{report.dataset_id}`",
        "",
        "## Boundary",
        "",
        "Labels are heuristic and auditable. They are reviewer-calibration signals, not ground truth unless human-verified.",
        "",
        "## Issue Counts",
        "",
    ]
    lines.extend([f"- `{issue}`: {count}" for issue, count in sorted(report.issue_counts.items())] or ["- none"])
    lines.extend(["", "## Severity Counts", ""])
    lines.extend([f"- `{severity}`: {count}" for severity, count in sorted(report.severity_counts.items())] or ["- none"])
    lines.extend(["", "## Venue Patterns", ""])
    if report.venue_patterns:
        for venue, counts in sorted(report.venue_patterns.items()):
            rendered = ", ".join(f"{issue}={count}" for issue, count in sorted(counts.items()))
            lines.append(f"- `{venue}`: {rendered}")
    else:
        lines.append("- none")
    lines.extend(["", "## Examples", ""])
    if report.examples:
        for issue, examples in sorted(report.examples.items()):
            lines.append(f"### {issue}")
            lines.append("")
            lines.extend(f"- {example}" for example in examples)
            lines.append("")
    else:
        lines.append("No examples available.")
    return "\n".join(lines).rstrip() + "\n"


def _labels_for_review(review: ReviewRecord, paper: ReviewDatasetPaper | None) -> list[ReviewIssueLabel]:
    labels: list[ReviewIssueLabel] = []
    candidate_texts = _review_issue_texts(review)
    for text in candidate_texts:
        for issue_type in _issue_types_for_text(text):
            labels.append(
                ReviewIssueLabel(
                    id=_label_id(review.id, issue_type, text),
                    review_id=review.id,
                    paper_id=review.paper_id,
                    issue_type=issue_type,
                    severity=_severity_for_issue(issue_type, text, review, paper),
                    evidence_text=text,
                    mapped_gapforge_gate=_gate_for_issue(issue_type),
                    provenance=Provenance(
                        created_by_skill="review-taxonomy",
                        source_ids=[review.id, review.paper_id],
                        timestamp=utc_now_iso(),
                        reasoning_summary="Heuristically mapped review text to an auditable taxonomy label.",
                    ),
                )
            )
    return _dedupe_labels(labels)


def _review_issue_texts(review: ReviewRecord) -> list[str]:
    return [
        *review.weaknesses,
        *review.questions,
        *review.limitations,
        *review.novelty_comments,
        *review.empirical_comments,
        *review.clarity_comments,
        *review.reproducibility_comments,
        *review.ethics_comments,
    ]


def _issue_types_for_text(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    keyword_map = {
        "novelty weakness": ["novelty", "incremental", "not established", "not novel"],
        "insufficient related work": ["related work", "prior work", "closest prior", "must cite"],
        "weak baselines": ["baseline", "baselines"],
        "missing ablation": ["ablation", "ablations"],
        "poor metric choice": ["metric", "metrics", "threshold"],
        "underpowered statistics": ["underpowered", "statistic", "power", "sample size", "significance"],
        "unclear contribution": ["contribution", "framing", "scope"],
        "overclaiming": ["overstates", "overclaim", "unsupported claim", "claim"],
        "dataset limitation": ["dataset", "data", "external validity", "deployment evidence", "synthetic traces"],
        "reproducibility issue": ["reproducib", "seeds", "splits", "runnable", "artifact checklist"],
        "ethics/safety issue": ["ethics", "safety", "misuse", "risk"],
        "writing clarity": ["clarity", "writing", "definitions", "ambiguous", "clearer"],
        "theory gap": ["theory", "theorem", "proof", "assumption"],
        "experiment mismatch": ["experiment", "empirical", "setup", "evaluation", "auxiliary datasets"],
        "artifact weakness": ["artifact", "code", "replication"],
    }
    for issue_type, keywords in keyword_map.items():
        if any(keyword in lowered for keyword in keywords):
            matches.append(issue_type)
    return matches


def _severity_for_issue(
    issue_type: str,
    text: str,
    review: ReviewRecord,
    paper: ReviewDatasetPaper | None,
) -> str:
    lowered = text.lower()
    if review.score > 0 and review.score <= 3:
        return "fatal" if issue_type in {"reproducibility issue", "overclaiming", "experiment mismatch"} else "major"
    if (
        paper is not None
        and paper.decision.lower() in {"reject", "rejected"}
        and issue_type
        in {
            "novelty weakness",
            "reproducibility issue",
            "overclaiming",
        }
    ):
        return "fatal"
    if any(term in lowered for term in ["not auditable", "unsupported", "not established", "no runnable", "not discussed"]):
        return "fatal"
    if any(term in lowered for term in ["limited", "unclear", "need", "should", "ambiguous", "under"]):
        return "major"
    return "minor"


def _gate_for_issue(issue_type: str) -> str:
    gate_map = {
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
    return gate_map.get(issue_type, "manual_review_gate")


def _taxonomy_report(dataset_id: str, labels: list[ReviewIssueLabel], papers: list[ReviewDatasetPaper]) -> ReviewTaxonomyReport:
    issue_counts = Counter(label.issue_type for label in labels)
    severity_counts = Counter(label.severity for label in labels)
    paper_by_id = {paper.id: paper for paper in papers}
    venue_patterns: dict[str, Counter[str]] = {}
    examples: dict[str, list[str]] = {}
    for label in labels:
        paper = paper_by_id.get(label.paper_id)
        venue = f"{paper.venue} {paper.year}" if paper else "unknown"
        venue_patterns.setdefault(venue, Counter())[label.issue_type] += 1
        examples.setdefault(label.issue_type, [])
        if len(examples[label.issue_type]) < 3:
            examples[label.issue_type].append(
                f"`{label.review_id}` ({label.severity}, {label.mapped_gapforge_gate}): {label.evidence_text}"
            )
    return ReviewTaxonomyReport(
        dataset_id=dataset_id,
        issue_counts=dict(issue_counts),
        severity_counts=dict(severity_counts),
        venue_patterns={venue: dict(counts) for venue, counts in venue_patterns.items()},
        examples=examples,
        provenance=Provenance(
            created_by_skill="review-taxonomy",
            source_ids=[dataset_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Summarized heuristic review issue labels for reviewer calibration; labels are not ground truth.",
        ),
    )


def _label_id(review_id: str, issue_type: str, evidence_text: str) -> str:
    return f"review-label-{slugify(review_id)}-{slugify(issue_type)}-{slugify(evidence_text)[:28]}"


def _dedupe_labels(labels: list[ReviewIssueLabel]) -> list[ReviewIssueLabel]:
    result: list[ReviewIssueLabel] = []
    seen: set[tuple[str, str, str]] = set()
    for label in labels:
        key = (label.review_id, label.issue_type, label.evidence_text)
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result
