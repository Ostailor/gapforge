from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from test_release_gate_v26 import _v26_fixture

from gapforge.config import GapForgeConfig
from gapforge.evals.fixtures import load_v26_fixture
from gapforge.evals.paper_quality import PaperQualityEvaluator, assess_paper_quality_from_payload


def test_paper_quality_scores_workshop_candidate_as_workshop_not_conference() -> None:
    payload = load_v26_fixture("matrix_package_resolved_workshop_candidate").selected_benchmark_v26_fixture

    assessment = assess_paper_quality_from_payload(
        payload,
        benchmark_id="benchmark-v26-workshop",
        manuscript_id="manuscript-v26-workshop",
    )

    assert assessment.workshop_readiness is True
    assert assessment.top_conference_readiness is False
    assert assessment.benchmark_fit_score <= 0.55
    assert any("auxiliary-only" in warning for warning in assessment.warnings)


def test_paper_quality_borderline_reject_blocks_top_conference() -> None:
    payload = deepcopy(load_v26_fixture("fatal_reviewers_remain_revise").selected_benchmark_v26_fixture)
    payload["drastic_review_rerun"]["likely_decision"] = "borderline_reject"

    assessment = assess_paper_quality_from_payload(
        payload,
        benchmark_id="benchmark-v26-borderline",
        manuscript_id="manuscript-v26-borderline",
    )

    assert assessment.top_conference_readiness is False
    assert assessment.reviewer_likelihood_score <= 0.4
    assert any("borderline reject" in warning for warning in assessment.warnings)


def test_paper_quality_scores_conference_candidate_ready() -> None:
    payload = load_v26_fixture("conference_candidate_no_fatal_blockers").selected_benchmark_v26_fixture

    assessment = assess_paper_quality_from_payload(
        payload,
        benchmark_id="benchmark-v26-conference",
        manuscript_id="manuscript-v26-conference",
    )

    assert assessment.top_conference_readiness is True
    assert assessment.workshop_readiness is True
    assert assessment.related_work_score >= 0.7
    assert assessment.benchmark_fit_score >= 0.7


def test_paper_quality_fake_citation_blocks_readiness() -> None:
    payload = deepcopy(load_v26_fixture("conference_candidate_no_fatal_blockers").selected_benchmark_v26_fixture)
    payload["safety"]["fake_citation_present"] = True

    assessment = assess_paper_quality_from_payload(
        payload,
        benchmark_id="benchmark-v26-fake-citation",
        manuscript_id="manuscript-v26-fake-citation",
    )

    assert assessment.claim_honesty_score == 0.0
    assert assessment.top_conference_readiness is False
    assert assessment.workshop_readiness is False
    assert any("safety:" in blocker for blocker in assessment.blockers)


def test_paper_quality_missing_related_work_score_zero() -> None:
    payload = load_v26_fixture("matrix_missing_blocked").selected_benchmark_v26_fixture

    assessment = assess_paper_quality_from_payload(
        payload,
        benchmark_id="benchmark-v26-missing-matrix",
        manuscript_id="manuscript-v26-missing-matrix",
    )

    assert assessment.related_work_score == 0.0
    assert assessment.novelty_score == 0.0
    assert any("related_work:" in blocker for blocker in assessment.blockers)


def test_paper_quality_cli_by_benchmark_and_manuscript(tmp_path: Path) -> None:
    _v26_fixture(tmp_path)
    project_root = next((tmp_path / "projects").glob("*"))
    matrix_path = project_root / "selected_benchmark" / "related_work_matrix_loader" / "related_work_matrix_load_result.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix["entry_count"] = 8
    matrix["must_cite_count"] = 3
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    by_benchmark = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "paper-quality", "--benchmark-id", "benchmark-v26-fixture"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    by_manuscript = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "paper-quality", "--manuscript-id", "manuscript-v26-fixture"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "paper-quality-report", "--benchmark-id", "benchmark-v26-fixture"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert by_benchmark.returncode == 0, by_benchmark.stderr
    assert by_manuscript.returncode == 0, by_manuscript.stderr
    assert json.loads(by_benchmark.stdout)["workshop_readiness"] is True
    assert "Paper Quality Assessment" in report.stdout
    assert (project_root / "selected_benchmark" / "paper_quality" / "paper_quality_assessment.json").exists()


def test_paper_quality_cli_fake_citation_blocks(tmp_path: Path) -> None:
    _v26_fixture(tmp_path, fake_citation=True)
    assessment = PaperQualityEvaluator(GapForgeConfig.from_cwd(tmp_path)).assess(benchmark_id="benchmark-v26-fixture")

    assert assessment.claim_honesty_score == 0.0
    assert any("safety:" in blocker for blocker in assessment.blockers)
