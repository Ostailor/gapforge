from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.evals.benchmark import run_evals
from gapforge.evals.fixtures import (
    FIXTURE_NAMES,
    V2_FIXTURE_NAMES,
    V3_FIXTURE_NAMES,
    V4_FIXTURE_NAMES,
    V5_FIXTURE_NAMES,
    V6_FIXTURE_NAMES,
    V7_FIXTURE_NAMES,
    list_fixtures,
    load_fixture,
    load_v3_fixture,
    load_v4_fixture,
    load_v5_fixture,
    load_v6_fixture,
    load_v7_fixture,
)
from gapforge.evals.metrics import (
    actual_run_gate_correctness,
    agent_output_validation_strictness,
    benchmark_execution_integrity,
    benchmark_failure_path_preservation,
    canonicalization_quality,
    direction_maturity_accuracy,
    direction_maturity_gate_accuracy_from_fixture,
    empirical_claim_validity,
    empirical_review_quality,
    error_analysis_quality,
    fake_result_rejection,
    gap_evidence_matrix_score,
    live_source_coverage_score,
    low_fpr_underpowered_warning_score,
    manuscript_package_honesty,
    novelty_research_loop_quality,
    paper_package_honesty,
    prior_work_recall_gate_score,
    quality_review_gate_correctness,
    real_literature_refusal_quality,
    replication_package_quality,
    reproduction_verification_quality,
    result_aggregation_quality,
    retrieval_relevance_at_k,
    rollback_safety,
    search_strategy_completeness,
    source_policy_compliance,
    statistical_caution_score,
    stop_reason_correctness,
    unsupported_claim_rate,
    v5_release_gate_correctness,
    v6_release_gate_correctness,
    v7_release_gate_correctness,
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


def test_v4_eval_fixtures_are_complete_and_offline() -> None:
    for name in V4_FIXTURE_NAMES:
        fixture = load_v4_fixture(name)
        assert fixture.is_v4
        assert fixture.topic
        assert fixture.papers
        assert fixture.known_good_gaps
        assert fixture.campaign_fixture["decisions"]
        assert fixture.campaign_fixture["stop_reason"]
        assert fixture.campaign_fixture["actual_run_gate"]


def test_v5_eval_fixtures_are_complete_and_offline() -> None:
    for name in V5_FIXTURE_NAMES:
        fixture = load_v5_fixture(name)
        payload = fixture.real_literature_fixture
        assert fixture.is_v5
        assert fixture.topic
        assert fixture.papers
        assert payload["source_health"]
        assert payload["search_strategy"]
        assert "papers" in payload
        assert payload["canonical_papers"]
        assert payload["prior_work_recall_assessment"]
        assert payload["novelty_dossiers"]
        assert payload["related_work_matrix"]
        assert payload["human_quality_review"]
        assert payload["expected_release_gate_result"]


def test_v6_eval_fixtures_are_complete_and_offline() -> None:
    for name in V6_FIXTURE_NAMES:
        fixture = load_v6_fixture(name)
        payload = fixture.experiment_fixture
        assert fixture.is_v6
        assert fixture.topic
        assert fixture.papers
        assert payload["execution"]
        assert "executions" in payload["execution"]
        assert payload["result_artifacts"]
        assert payload["result_summary"]
        assert payload["statistics"]
        assert payload["paper_package"]
        assert payload["v6_release_gate"]


def test_v7_eval_fixtures_are_complete_and_offline() -> None:
    for name in V7_FIXTURE_NAMES:
        fixture = load_v7_fixture(name)
        payload = fixture.benchmark_fixture
        assert fixture.is_v7
        assert fixture.topic
        assert fixture.papers
        assert payload["benchmark"]
        assert payload["execution"]
        assert payload["aggregation"]
        assert payload["error_analysis"]
        assert payload["comparison"]
        assert payload["replication"]
        assert payload["reproduction"]
        assert payload["v7_release_gate"]


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


def test_eval_cli_v4_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "fake_agent_campaign", "--v4", "--write-report"],
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
    assert "### v0.4 Scores" in text
    assert "actual_run_gate_correctness" in text
    report_path.unlink()


def test_eval_cli_v6_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "smoke_success", "--v6", "--write-report"],
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
    assert "### v0.6 Scores" in text
    assert "experiment_execution_integrity" in text
    report_path.unlink()


def test_eval_cli_v7_writes_report(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "eval", "--fixture", "fixture_benchmark_success", "--v7", "--write-report"],
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
    assert "### v0.7 Scores" in text
    assert "benchmark_execution_integrity" in text
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


def test_run_v4_evals_includes_campaign_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v4=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V4_FIXTURE_NAMES)
    assert all(result.scores.campaign_decision_quality is not None for result in report.results)
    assert all(result.scores.actual_run_gate_correctness is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.1 Scores" in text
    assert "### v0.4 Scores" in text
    assert "v0.4 overall score" in text


def test_run_v5_evals_includes_real_literature_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v5=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V5_FIXTURE_NAMES)
    assert all(result.scores.live_source_coverage_score is not None for result in report.results)
    assert all(result.scores.quality_review_gate_correctness is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.5 Scores" in text
    assert "v0.5 overall score" in text
    assert "quality_review_gate_correctness" in text


def test_run_v6_evals_includes_experiment_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v6=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V6_FIXTURE_NAMES)
    assert all(result.scores.experiment_execution_integrity is not None for result in report.results)
    assert all(result.scores.v6_release_gate_correctness is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.6 Scores" in text
    assert "v0.6 overall score" in text
    assert "paper_package_honesty" in text


def test_run_v7_evals_includes_benchmark_metrics_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    report = run_evals(v7=True, output_dir=tmp_path, write_report=True)

    assert len(report.results) == len(V7_FIXTURE_NAMES)
    assert all(result.scores.benchmark_execution_integrity is not None for result in report.results)
    assert all(result.scores.v7_release_gate_correctness is not None for result in report.results)
    text = (tmp_path / "eval_report.md").read_text(encoding="utf-8")
    assert "### v0.7 Scores" in text
    assert "v0.7 overall score" in text
    assert "replication_package_quality" in text


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


def test_v4_invalid_agent_output_is_rejected() -> None:
    fixture = load_v4_fixture("invalid_agent_output").campaign_fixture

    assert agent_output_validation_strictness(fixture) == 1.0


def test_v4_undercovered_campaign_refuses_recommendation() -> None:
    fixture = load_v4_fixture("undercovered_refusal").campaign_fixture

    assert stop_reason_correctness(fixture) == 1.0


def test_v4_duplicate_prior_work_rejects_direction() -> None:
    fixture = load_v4_fixture("novelty_research_loop").campaign_fixture

    assert novelty_research_loop_quality(fixture) == 1.0


def test_v4_experiment_ready_requires_protocol_novelty_and_related_work() -> None:
    ready = load_v4_fixture("experiment_ready_direction").campaign_fixture
    fatal = load_v4_fixture("reviewer_fatal_flaw").campaign_fixture

    assert direction_maturity_gate_accuracy_from_fixture(ready) == 1.0
    assert direction_maturity_gate_accuracy_from_fixture(fatal) == 1.0
    broken = {
        "directions": [
            {
                "id": "premature",
                "maturity": "experiment_ready",
                "has_protocol": True,
                "has_novelty_dossier": False,
                "has_related_work_matrix": True,
                "rejected": False,
            }
        ]
    }
    assert direction_maturity_gate_accuracy_from_fixture(broken) == 0.0


def test_v4_release_gate_fails_fake_only_campaigns() -> None:
    fixture = load_v4_fixture("fake_agent_campaign").campaign_fixture

    assert actual_run_gate_correctness(fixture) == 1.0


def test_v4_rollback_safety_metric_works() -> None:
    fixture = load_v4_fixture("invalid_agent_output").campaign_fixture
    unsafe = {
        "rollback": {
            "snapshot_created": True,
            "rollback_exercised": False,
            "state_restored": False,
            "unsafe_mutation_after_reject": True,
        }
    }

    assert rollback_safety(fixture) == 1.0
    assert rollback_safety(unsafe) < 0.6


def test_v5_duplicate_prior_work_rejected() -> None:
    fixture = load_v5_fixture("live_like_prior_work_duplicate").real_literature_fixture

    assert prior_work_recall_gate_score(fixture) == 1.0
    assert quality_review_gate_correctness(fixture) == 1.0
    assert v5_release_gate_correctness(fixture) == 1.0


def test_v5_undercovered_refusal_accepted() -> None:
    fixture = load_v5_fixture("live_like_undercovered_refusal").real_literature_fixture

    assert real_literature_refusal_quality(fixture) == 1.0
    assert quality_review_gate_correctness(fixture) == 1.0
    assert v5_release_gate_correctness(fixture) == 1.0


def test_v5_missing_prior_work_recall_blocks_release_gate() -> None:
    fixture = load_v5_fixture("live_like_monitor_evasion").real_literature_fixture
    fixture["prior_work_recall_assessment"]["missing_required_searches"] = ["novelty"]
    fixture["expected_release_gate_result"]["prior_work_recall_should_block"] = True
    fixture["expected_release_gate_result"]["passed"] = False
    fixture["expected_release_gate_result"]["expected_blockers"] = ["missing prior-work recall"]

    assert prior_work_recall_gate_score(fixture) < 1.0
    assert v5_release_gate_correctness(fixture) == 1.0


def test_v5_quality_review_metrics_work() -> None:
    good = load_v5_fixture("live_like_low_fpr_collusion").real_literature_fixture

    assert live_source_coverage_score(good) > 0.7
    assert search_strategy_completeness(good) == 1.0
    assert canonicalization_quality(good) == 1.0
    assert quality_review_gate_correctness(good) == 1.0


def test_v6_fake_result_rejected() -> None:
    fixture = load_v6_fixture("fake_result_rejected").experiment_fixture

    assert fake_result_rejection(fixture) == 1.0
    assert v6_release_gate_correctness(fixture) == 1.0


def test_v6_failed_run_preserved() -> None:
    fixture = load_v6_fixture("failed_run").experiment_fixture

    assert paper_package_honesty(fixture) == 1.0
    assert v6_release_gate_correctness(fixture) == 1.0


def test_v6_low_fpr_warning_works() -> None:
    fixture = load_v6_fixture("low_fpr_underpowered").experiment_fixture

    assert statistical_caution_score(fixture) == 1.0


def test_v6_paper_package_labels_results_correctly() -> None:
    fixture = load_v6_fixture("paper_package_result_labels").experiment_fixture

    assert empirical_claim_validity(fixture) == 1.0
    assert empirical_review_quality(fixture) == 1.0
    assert paper_package_honesty(fixture) == 1.0


def test_v7_fixture_benchmark_success_path() -> None:
    fixture = load_v7_fixture("fixture_benchmark_success").benchmark_fixture

    assert benchmark_execution_integrity(fixture) == 1.0
    assert result_aggregation_quality(fixture) == 1.0
    assert error_analysis_quality(fixture) == 1.0
    assert v7_release_gate_correctness(fixture) == 1.0


def test_v7_failed_benchmark_path_preserved() -> None:
    fixture = load_v7_fixture("fixture_benchmark_failure").benchmark_fixture

    assert benchmark_failure_path_preservation(fixture) == 1.0
    assert v7_release_gate_correctness(fixture) == 1.0


def test_v7_low_fpr_warning_and_replication_metrics_work() -> None:
    low_fpr = load_v7_fixture("low_fpr_underpowered_benchmark").benchmark_fixture
    replication = load_v7_fixture("replication_package_canary").benchmark_fixture

    assert low_fpr_underpowered_warning_score(low_fpr) == 1.0
    assert replication_package_quality(replication) == 1.0
    assert reproduction_verification_quality(replication) == 1.0
