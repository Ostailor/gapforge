from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.evals.benchmark import run_evals
from gapforge.evals.fixtures import FIXTURE_NAMES, V2_FIXTURE_NAMES, V3_FIXTURE_NAMES, list_fixtures, load_fixture, load_v3_fixture
from gapforge.evals.metrics import (
    direction_maturity_accuracy,
    gap_evidence_matrix_score,
    manuscript_package_honesty,
    retrieval_relevance_at_k,
    source_policy_compliance,
    unsupported_claim_rate,
)
from gapforge.models import Claim, ResearchRunState, ResearchTopic, SourceCoverageReport


def test_eval_fixtures_are_complete() -> None:
    names = list_fixtures()
    assert set(FIXTURE_NAMES).issubset(names)
    for name in FIXTURE_NAMES:
        fixture = load_fixture(name)
        assert fixture.topic
        assert fixture.papers
        assert fixture.paper_notes
        assert fixture.known_good_gaps
        assert fixture.known_bad_gaps
        assert fixture.duplicate_ideas
        assert fixture.expected_reviewer_objections


def test_v2_eval_fixtures_are_complete_and_offline() -> None:
    names = list_fixtures()
    assert set(V2_FIXTURE_NAMES).issubset(names)
    for name in V2_FIXTURE_NAMES:
        fixture = load_fixture(name)
        assert fixture.is_v2
        assert fixture.paper_sections
        assert fixture.evidence_spans
        assert fixture.expected_novelty_dossiers
        assert fixture.expected_gap_evidence_matrix
        assert fixture.expected_source_coverage is not None
        assert fixture.expected_source_coverage.searched_sources == ["fixture-source"]


def test_v3_eval_fixtures_are_complete_and_offline() -> None:
    for name in V3_FIXTURE_NAMES:
        fixture = load_v3_fixture(name)
        assert fixture.is_v3
        assert fixture.topic
        assert fixture.papers
        assert fixture.paper_sections
        assert fixture.evidence_spans
        assert fixture.known_good_gaps
        assert fixture.human_gold_prior_work
        assert fixture.human_gold_related_work_matrix
        assert fixture.human_gold_reviewer_objections
        assert fixture.expected_source_coverage is not None
        assert fixture.expected_source_coverage.searched_sources == ["fixture-source"]


def test_run_evals_single_fixture_writes_report(tmp_path: Path) -> None:
    report = run_evals(fixture="low_fpr_collusion", output_dir=tmp_path, write_report=True)

    assert report.report_path == tmp_path / "eval_report.md"
    assert report.report_path.exists()
    text = report.report_path.read_text(encoding="utf-8")
    assert "gap_specificity_score" in text
    assert "Unsupported Claims" in text
    assert "Novelty Gate Failures" in text
    assert len(report.results) == 1
    result = report.results[0]
    assert result.scores.novelty_gate_accuracy == 1.0
    assert result.scores.duplicate_detection_rate > 0
    assert result.unsupported_claims
    assert result.missing_baselines


def test_run_evals_all_fixtures_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(output_dir=tmp_path, write_report=True)

    assert len(report.results) >= 4
    assert report.overall_score > 0
    assert all(result.accepted_gaps for result in report.results)
    assert any(result.rejected_gaps for result in report.results)


def test_eval_cli_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "low_fpr_collusion", "--write-report"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "eval_report.md" in result.stdout
    report_path = Path.cwd() / "eval_report.md"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "low_fpr_collusion" in text
    report_path.unlink()


def test_eval_cli_v3_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "low_fpr_collusion", "--v3", "--write-report"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "eval_report.md" in result.stdout
    report_path = Path.cwd() / "eval_report.md"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")
    assert "### v0.3 Scores" in text
    assert "retrieval_relevance_at_k" in text
    report_path.unlink()


def test_fixture_duplicate_ideas_are_intentionally_rejected() -> None:
    report = run_evals(fixture="quantum_portfolio_optimization", write_report=False)
    result = report.results[0]

    assert result.scores.novelty_gate_accuracy == 1.0
    assert "dup-qpo-1" in result.rejected_gaps


def test_run_v2_evals_includes_v2_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v2=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V2_FIXTURE_NAMES)
    assert all(result.scores.full_text_coverage_score is not None for result in report.results)
    assert all(result.scores.novelty_dossier_completeness_score is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.1 Scores" in text
    assert "### v0.2 Scores" in text
    assert "Failed Checks And Suggested Improvements" in text


def test_run_v3_evals_includes_v3_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v3=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V3_FIXTURE_NAMES)
    assert all(result.scores.retrieval_relevance_at_k is not None for result in report.results)
    assert all(result.scores.related_work_matrix_quality is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.1 Scores" in text
    assert "### v0.2 Scores" in text
    assert "### v0.3 Scores" in text
    assert "source_policy_compliance" in text


def test_v2_duplicate_ideas_are_rejected_by_dossier_aware_novelty_gate() -> None:
    report = run_evals(fixture="ai_agent_covert_channels_v2", write_report=False)
    result = report.results[0]

    assert result.scores.novelty_gate_accuracy == 1.0
    assert any(item.startswith("dup-acc") for item in result.rejected_gaps)


def test_unsupported_high_confidence_full_text_claim_is_caught() -> None:
    fixture = load_fixture("low_fpr_collusion_v2")
    from gapforge.evals.benchmark import _state_from_fixture

    state = _state_from_fixture(fixture)
    state.claims.append(
        Claim(
            id="claim-high-fulltext-no-span",
            text="Unsupported high-confidence full-text claim.",
            type="result",
            status="supported",
            confidence="high",
            source_paper_ids=[fixture.papers[0].id],
            needs_verification=False,
        )
    )

    assert unsupported_claim_rate(state.claims, state) > 0


def test_gap_evidence_matrix_scoring_works() -> None:
    fixture = load_fixture("medical_screening_false_positives_v2")
    score = gap_evidence_matrix_score(fixture.known_good_gaps, fixture.expected_gap_evidence_matrix)

    assert score > 0.5


def test_v3_retrieval_relevance_metric_works() -> None:
    assert retrieval_relevance_at_k(["p1", "p2", "p3"], ["p2", "p4"], k=2) == 0.5
    assert retrieval_relevance_at_k(["p4", "p2"], ["p2", "p4"], k=2) == 1.0


def test_v3_direction_maturity_metric_penalizes_premature_readiness() -> None:
    assert direction_maturity_accuracy("candidate", ["missing coverage"]) == 1.0
    assert direction_maturity_accuracy("experiment_ready", ["missing coverage"]) == 0.5
    assert direction_maturity_accuracy("experiment_ready", []) == 1.0


def test_v3_manuscript_package_honesty_catches_fake_results() -> None:
    honest = manuscript_package_honesty(["Expected results are hypothetical; experiments are not run and evidence remains uncertain."])
    fake = manuscript_package_honesty(["Our results show the method significantly outperforms all baselines."])

    assert honest > fake
    assert fake < 0.5


def test_v3_source_policy_compliance_catches_insufficient_coverage(tmp_path: Path) -> None:
    state = ResearchRunState(
        run_id="policy-check",
        topic=ResearchTopic(text="medical screening specificity", slug="policy-check", created_at="2026-01-01T00:00:00+00:00"),
        run_dir=str(tmp_path),
        source_coverage=SourceCoverageReport(
            run_id="policy-check",
            topic="medical screening specificity",
            searched_sources=["fixture-source"],
            papers_with_full_text=["p1"],
            coverage_warnings=["offline fixture"],
            confidence="low",
        ),
    )

    assert source_policy_compliance(state, ["fixture-source", "pubmed"]) < 0.8
