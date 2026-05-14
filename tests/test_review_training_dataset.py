from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.review_training import ReviewDatasetBuilder


def test_ingest_synthetic_review_fixture(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    papers = ReviewDatasetBuilder(config).list_papers(dataset.id)
    reviews = ReviewDatasetBuilder(config).list_reviews(dataset.id)

    assert dataset.source == "synthetic_fixture"
    assert dataset.paper_count == 2
    assert dataset.review_count == 3
    assert len(papers) == 2
    assert len(reviews) == 3
    assert all(paper.decision for paper in papers)


def test_scores_parsed(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()

    papers = ReviewDatasetBuilder(config).list_papers(dataset.id)
    reviews = ReviewDatasetBuilder(config).list_reviews(dataset.id)
    score_by_paper = {paper.id: paper.average_score for paper in papers}

    assert sorted(review.score for review in reviews) == [3.0, 6.0, 8.0]
    assert score_by_paper["fixture-paper-calibrated-monitoring"] == 7.0
    assert score_by_paper["fixture-paper-weak-evidence"] == 3.0


def test_weaknesses_extracted(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    reviews = ReviewDatasetBuilder(config).list_reviews(dataset.id)
    weaknesses = [weakness for review in reviews for weakness in review.weaknesses]

    assert "Limited external validity." in weaknesses
    assert "Unsupported claims dominate the paper." in weaknesses
    assert any(review.reproducibility_comments for review in reviews)


def test_reviewer_ids_hashed(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    reviews = ReviewDatasetBuilder(config).list_reviews(dataset.id)
    dataset_dir = config.data_dir / "review_training" / "datasets" / dataset.id
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in dataset_dir.rglob("*.json"))

    assert all(review.reviewer_id_hash.startswith("reviewer-") for review in reviews)
    assert all("@" not in review.reviewer_id_hash for review in reviews)
    assert "reviewer-a@example.invalid" not in serialized
    assert "reviewer-b@example.invalid" not in serialized
    assert "reviewer-c@example.invalid" not in serialized


def test_review_dataset_report_and_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    report = ReviewDatasetBuilder(config).render_report(dataset.id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    create = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-dataset-create", "--name", "openreview_like"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    ingest_fixture = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-dataset-ingest-fixture"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    cli_report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-dataset-report", "--dataset-id", dataset.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Review Dataset" in report
    assert "Reviewer identifiers are hashed" in report
    assert create.returncode == 0, create.stderr
    assert json.loads(create.stdout)["name"] == "openreview_like"
    assert ingest_fixture.returncode == 0, ingest_fixture.stderr
    assert json.loads(ingest_fixture.stdout)["paper_count"] == 2
    assert cli_report.returncode == 0, cli_report.stderr
    assert "Weakness labels" in cli_report.stdout


def test_openreview_live_ingest_is_guarded(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    dataset = ReviewDatasetBuilder(config).ingest_openreview(venue="ICLR", year=2024)
    report = ReviewDatasetBuilder(config).render_report(dataset.id)

    assert dataset.source == "openreview"
    assert dataset.paper_count == 0
    assert dataset.review_count == 0
    assert any("disabled" in warning and "privacy" in warning for warning in dataset.license_warnings)
    assert "No papers ingested" in report
