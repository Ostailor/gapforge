from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance
from gapforge.review_training import ReviewDatasetBuilder, ReviewerEvaluationManager, ReviewerTrainingManager
from gapforge.review_training.scoring import score_evidence_linkage, score_hallucination_rate
from gapforge.review_training.taxonomy import ReviewIssueLabel


def test_heuristic_reviewer_trains_and_evaluates_on_fixture(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)

    run = ReviewerTrainingManager(config).train(dataset_id, mode="heuristic")
    result = ReviewerEvaluationManager(config).evaluate(dataset_id)

    assert run.status == "complete"
    assert run.model_type == "heuristic"
    assert 0.0 <= float(run.metrics["issue_recall_proxy"]) <= 1.0
    assert result.model_id == run.id
    assert result.issue_recall_proxy >= 0.0
    assert result.hallucination_rate == 0.0


def test_hallucinated_citation_penalized() -> None:
    predicted = [
        _label(
            issue_type="weak baselines",
            evidence_text="paper:paper-1 cites Smith et al. 2099 for an invented result.",
        )
    ]

    assert score_hallucination_rate(predicted) == 1.0


def test_evidence_linkage_scored() -> None:
    linked = [_label(issue_type="dataset limitation", evidence_text="paper:paper-1 lacks deployment evidence.")]
    unlinked = [_label(issue_type="dataset limitation", evidence_text="No linked evidence is provided.")]

    assert score_evidence_linkage(linked) == 1.0
    assert score_evidence_linkage(unlinked) == 0.0


def test_reviewer_calibration_report_renders_and_cli(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)
    report = ReviewerEvaluationManager(config).render_report(dataset_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    train_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reviewer-train", "--dataset-id", dataset_id, "--mode", "heuristic"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    evaluate_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reviewer-evaluate", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reviewer-calibration-report", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Reviewer Evaluation" in report
    assert "does not claim human reviewer equivalence" in report
    assert train_cli.returncode == 0, train_cli.stderr
    assert json.loads(train_cli.stdout)["status"] == "complete"
    assert evaluate_cli.returncode == 0, evaluate_cli.stderr
    assert "issue_recall_proxy" in json.loads(evaluate_cli.stdout)
    assert report_cli.returncode == 0, report_cli.stderr
    assert "Hallucination/fake-citation rate" in report_cli.stdout


def _fixture_dataset(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    return config, dataset.id


def _label(issue_type: str, evidence_text: str) -> ReviewIssueLabel:
    return ReviewIssueLabel(
        id=f"label-{issue_type}",
        review_id="reviewer-model",
        paper_id="paper-1",
        issue_type=issue_type,
        severity="major",
        evidence_text=evidence_text,
        mapped_gapforge_gate="manual_review_gate",
        provenance=Provenance(created_by_skill="test"),
    )
