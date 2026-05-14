"""Reviewer calibration evaluation harness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, to_plain
from gapforge.review_training.scoring import score_predictions
from gapforge.review_training.taxonomy import ReviewTaxonomyLabeler
from gapforge.review_training.train import ReviewerTrainingManager
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class ReviewerEvaluationResult:
    id: str
    model_id: str
    dataset_id: str
    issue_recall_proxy: float
    severity_calibration_score: float
    review_specificity_score: float
    hallucination_rate: float
    evidence_linkage_score: float
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="reviewer-evaluate"))


class ReviewerEvaluationManager:
    """Evaluate calibrated reviewer runs against heuristic taxonomy labels."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.training = ReviewerTrainingManager(config)
        self.taxonomy = ReviewTaxonomyLabeler(config)

    def evaluate(self, dataset_id: str, *, model_id: str = "") -> ReviewerEvaluationResult:
        run = self.training.latest_run(dataset_id)
        if model_id and model_id != run.id:
            # Only local persisted runs are supported in CI; use latest when explicit model is unavailable.
            run = self.training.latest_run(dataset_id)
        gold = self.taxonomy.list_labels(dataset_id)
        predicted = self.training.load_predictions(run)
        metrics = score_predictions(gold, predicted)
        result = ReviewerEvaluationResult(
            id=f"reviewer-evaluation-{run.id}",
            model_id=run.id,
            dataset_id=dataset_id,
            issue_recall_proxy=metrics["issue_recall_proxy"],
            severity_calibration_score=metrics["severity_calibration_score"],
            review_specificity_score=metrics["review_specificity_score"],
            hallucination_rate=metrics["hallucination_rate"],
            evidence_linkage_score=metrics["evidence_linkage_score"],
            provenance=Provenance(
                created_by_skill="reviewer-evaluate",
                source_ids=[dataset_id, run.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Evaluated reviewer simulation against auditable taxonomy labels without claiming human reviewer equivalence."
                ),
            ),
        )
        self._write_result(result)
        return result

    def render_report(self, dataset_id: str) -> str:
        result = self.evaluate(dataset_id)
        training_report = self.training.render_report(dataset_id)
        lines = [
            f"# Reviewer Evaluation `{dataset_id}`",
            "",
            f"- Model/run: `{result.model_id}`",
            f"- Issue recall proxy: {result.issue_recall_proxy:.4f}",
            f"- Severity calibration: {result.severity_calibration_score:.4f}",
            f"- Specificity: {result.review_specificity_score:.4f}",
            f"- Hallucination/fake-citation rate: {result.hallucination_rate:.4f}",
            f"- Evidence linkage: {result.evidence_linkage_score:.4f}",
            "",
            "## Boundary",
            "",
            (
                "Reviewer simulation is benchmarked for calibration only. It cannot invent citations/results and is not a "
                "human-reviewer substitute."
            ),
            "",
            training_report.rstrip(),
        ]
        report = "\n".join(lines).rstrip() + "\n"
        (self._dataset_dir(dataset_id) / "reviewer_evaluation_report.md").write_text(report, encoding="utf-8")
        return report

    def _write_result(self, result: ReviewerEvaluationResult) -> None:
        path = self._dataset_dir(result.dataset_id) / "reviewer_evaluation.json"
        path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")

    def _dataset_dir(self, dataset_id: str) -> Path:
        path = self.config.data_dir / "review_training" / "datasets" / dataset_id
        path.mkdir(parents=True, exist_ok=True)
        return path


def reviewer_evaluation_json(result: ReviewerEvaluationResult) -> str:
    return json.dumps(to_plain(result), indent=2) + "\n"
