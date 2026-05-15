from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.models import Provenance
from gapforge.selected_benchmark import SelectedBenchmarkManager, SelectedVettedBenchmarkExperimentManager
from gapforge.selected_benchmark.real_benchmark_search import RealBenchmarkCandidate, RealBenchmarkSearchManager
from gapforge.vetted_benchmarks import render_real_benchmark_adapter_assessment


def test_real_adapter_assessment_for_primary_fit(tmp_path: Path) -> None:
    config, benchmark_id, candidate = _fixture_with_candidate(tmp_path, _primary_candidate())

    assessment = SelectedVettedBenchmarkExperimentManager(config).assess_real_candidate(benchmark_id, candidate.id)

    assert assessment.adapter_possible is True
    assert assessment.adapter_type == "direct"
    assert assessment.expected_claim_support == "primary"
    assert assessment.blockers == []
    assert assessment.sequentialization_needed is False


def test_real_adapter_assessment_for_sanity_check(tmp_path: Path) -> None:
    config, benchmark_id, candidate = _fixture_with_candidate(tmp_path, _sanity_candidate())

    assessment = SelectedVettedBenchmarkExperimentManager(config).assess_real_candidate(benchmark_id, candidate.id)

    assert assessment.adapter_possible is True
    assert assessment.adapter_type == "sanity_check"
    assert assessment.expected_claim_support == "sanity_check"
    assert any("sanity-check" in blocker for blocker in assessment.blockers)
    assert any("collusion" in mismatch for mismatch in assessment.label_mismatches)


def test_impossible_real_adapter_produces_no_fit(tmp_path: Path) -> None:
    config, benchmark_id, candidate = _fixture_with_candidate(tmp_path, _no_fit_candidate())

    assessment = SelectedVettedBenchmarkExperimentManager(config).assess_real_candidate(benchmark_id, candidate.id)

    assert assessment.adapter_possible is False
    assert assessment.expected_claim_support == "no_fit"
    assert any("honest adapter path" in blocker for blocker in assessment.blockers)


def test_real_adapter_outputs_are_labeled_correctly(tmp_path: Path) -> None:
    config, benchmark_id, candidate = _fixture_with_candidate(tmp_path, _sanity_candidate())
    manager = SelectedVettedBenchmarkExperimentManager(config)

    adapter = manager.create_real_candidate_adapter(benchmark_id, candidate.id)
    run = manager.run_real_candidate_adapter(adapter.id)
    output_path = config.data_dir / "vetted_benchmarks" / "adapter_runs" / run.id / "adapted_trace_units.json"
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert adapter.evidence_label == "sanity_check"
    assert run.status == "complete"
    assert output["evidence_label"] == "sanity_check"
    assert output["strong_claims_allowed"] is False
    assert output["downloaded_dataset"] is False
    assert any("sanity-check only" in warning for warning in run.warnings)


def test_real_adapter_report_renders_and_cli(tmp_path: Path) -> None:
    config, benchmark_id, candidate = _fixture_with_candidate(tmp_path, _primary_candidate())
    assessment = SelectedVettedBenchmarkExperimentManager(config).assess_real_candidate(benchmark_id, candidate.id)

    rendered = render_real_benchmark_adapter_assessment(assessment)
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-real-benchmark-adapter-assess",
            "--benchmark-id",
            benchmark_id,
            "--candidate-id",
            candidate.id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Real Benchmark Adapter Assessment" in rendered
    assert "Claim Boundary" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Expected claim support: `primary`" in cli.stdout


def _fixture_with_candidate(tmp_path: Path, candidate: RealBenchmarkCandidate):
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    RealBenchmarkSearchManager(config).search(spec.id, candidates=[candidate])
    return config, spec.id, candidate


def _primary_candidate() -> RealBenchmarkCandidate:
    return RealBenchmarkCandidate(
        id="real-benchmark-primary-collusion-monitor",
        name="Sequential Low-FPR Collusion Monitor Benchmark",
        source_url="https://example.test/primary-collusion-monitor",
        benchmark_type="benchmark",
        domain="multi-agent collusion monitoring",
        task_type="sequential low-FPR monitor audit with collusion labels and false-positive specificity",
        license="MIT",
        dataset_access="public metadata fixture",
        relevance_to_selected_benchmark="Directly contains sequential collusion monitoring labels for low false-positive specificity.",
        fit_status="unknown",
        fit_reason="Candidate metadata indicates primary fit, but adapter assessment must verify blockers.",
        adaptation_required=["Preserve collusion labels, monitor decisions, and sequential windows."],
        provenance=Provenance(created_by_skill="fixture"),
    )


def _sanity_candidate() -> RealBenchmarkCandidate:
    return RealBenchmarkCandidate(
        id="real-benchmark-streaming-anomaly-sanity",
        name="Streaming Anomaly Specificity Benchmark",
        source_url="https://example.test/streaming-anomaly",
        benchmark_type="benchmark",
        domain="streaming anomaly detection",
        task_type="sequential time-series anomaly detection with false alarm labels",
        license="MIT",
        dataset_access="public metadata fixture",
        relevance_to_selected_benchmark="Useful for sequential false-alarm metric plumbing only.",
        fit_status="unknown",
        fit_reason="Candidate is useful as a sanity check for sequential false-alarm scoring.",
        adaptation_required=["Translate anomaly windows into monitor false-alarm sanity checks."],
        provenance=Provenance(created_by_skill="fixture"),
    )


def _no_fit_candidate() -> RealBenchmarkCandidate:
    return RealBenchmarkCandidate(
        id="real-benchmark-static-image-no-fit",
        name="Static Image Classification Benchmark",
        source_url="https://example.test/static-image",
        benchmark_type="dataset",
        domain="computer vision",
        task_type="single image classification",
        license="CC0",
        dataset_access="public metadata fixture",
        relevance_to_selected_benchmark="Unrelated static classification dataset.",
        fit_status="unknown",
        fit_reason="No relevant temporal or monitoring substrate.",
        provenance=Provenance(created_by_skill="fixture"),
    )
