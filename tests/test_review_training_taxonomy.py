from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.review_training import ReviewDatasetBuilder, ReviewTaxonomyLabeler


def test_label_synthetic_review_issues(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)

    labels = ReviewTaxonomyLabeler(config).generate(dataset_id)
    issue_types = {label.issue_type for label in labels}

    assert "dataset limitation" in issue_types
    assert "reproducibility issue" in issue_types
    assert "overclaiming" in issue_types
    assert "writing clarity" in issue_types


def test_severity_mapped(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)

    labels = ReviewTaxonomyLabeler(config).generate(dataset_id)
    severity_by_issue = {(label.paper_id, label.issue_type): label.severity for label in labels}

    assert severity_by_issue[("fixture-paper-weak-evidence", "overclaiming")] == "fatal"
    assert any(label.severity == "major" for label in labels)
    assert all(label.severity in {"minor", "major", "fatal"} for label in labels)


def test_gate_mapping_works(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)

    labels = ReviewTaxonomyLabeler(config).generate(dataset_id)
    gate_by_issue = {label.issue_type: label.mapped_gapforge_gate for label in labels}

    assert gate_by_issue["weak baselines"] == "baseline_strength_gate"
    assert gate_by_issue["missing ablation"] == "experiment_design_gate"
    assert gate_by_issue["reproducibility issue"] == "reproducibility_gate"
    assert gate_by_issue["ethics/safety issue"] == "ethics_safety_gate"


def test_taxonomy_report_renders_and_cli(tmp_path: Path) -> None:
    config, dataset_id = _fixture_dataset(tmp_path)
    report = ReviewTaxonomyLabeler(config).render_report(dataset_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    labels_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-labels-generate", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-taxonomy-report", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Review Taxonomy Report" in report
    assert "not ground truth unless human-verified" in report
    assert labels_cli.returncode == 0, labels_cli.stderr
    assert any(item["issue_type"] == "dataset limitation" for item in json.loads(labels_cli.stdout))
    assert report_cli.returncode == 0, report_cli.stderr
    assert "GapForge" not in report_cli.stderr
    assert "Venue Patterns" in report_cli.stdout


def _fixture_dataset(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    dataset = ReviewDatasetBuilder(config).ingest_fixture()
    return config, dataset.id
