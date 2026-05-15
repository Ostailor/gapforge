from __future__ import annotations

import subprocess
import sys

from test_selected_benchmark import _env, _selected_project

from gapforge.models import Provenance
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.real_benchmark_search import (
    RealBenchmarkCandidate,
    RealBenchmarkSearchManager,
    render_real_benchmark_candidates,
)


def test_candidate_search_fixture_returns_real_candidates(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)

    search = RealBenchmarkSearchManager(config).search(spec.id)
    candidates = RealBenchmarkSearchManager(config).load_candidates(spec.id)

    assert search.status == "complete"
    assert search.candidate_benchmark_ids
    assert "real-benchmark-agentdojo" in search.candidate_benchmark_ids
    assert any(candidate.source_url.startswith("https://github.com/") for candidate in candidates)
    assert all(candidate.fit_status == "unknown" for candidate in candidates if candidate.id in search.candidate_benchmark_ids)


def test_no_fit_report_generated_when_no_candidate_matches(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    unrelated = RealBenchmarkCandidate(
        id="real-benchmark-static-image-fixture",
        name="Static Image Fixture",
        source_url="https://example.test/static-images",
        benchmark_type="dataset",
        domain="computer vision",
        task_type="single image classification",
        license="CC0",
        dataset_access="public metadata fixture",
        relevance_to_selected_benchmark="No relationship to sequential collusion monitoring.",
        fit_status="no_fit",
        fit_reason="Single-image classification has no agent, monitor, sequential, or collusion substrate.",
        provenance=Provenance(created_by_skill="fixture"),
    )

    search = RealBenchmarkSearchManager(config).search(spec.id, candidates=[unrelated])
    report = RealBenchmarkSearchManager(config).render_no_fit_report(spec.id)

    assert search.status == "no_fit"
    assert unrelated.id in search.rejected_candidate_ids
    assert "No candidate survived" in report
    assert "new benchmark protocol is needed" in report


def test_license_warning_preserved(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    candidate = RealBenchmarkCandidate(
        id="real-benchmark-restricted-agent-fixture",
        name="Restricted Agent Fixture",
        source_url="https://example.test/restricted-agent",
        benchmark_type="benchmark",
        domain="agent monitoring",
        task_type="sequential monitor evaluation",
        license="non-commercial research only",
        dataset_access="separate authentication required",
        relevance_to_selected_benchmark="Agent monitor traces may be relevant after mapping.",
        fit_status="auxiliary",
        fit_reason="Fixture claims auxiliary, but search must demote until mapping assessment.",
        provenance=Provenance(created_by_skill="fixture"),
    )

    RealBenchmarkSearchManager(config).search(spec.id, candidates=[candidate])
    loaded = RealBenchmarkSearchManager(config).load_candidates(spec.id)[0]

    assert loaded.fit_status == "unknown"
    assert any("License warning" in item for item in loaded.limitations)
    assert any("Access warning" in item for item in loaded.limitations)
    assert any("demoted" in item for item in loaded.limitations)


def test_candidate_report_renders_and_cli(tmp_path) -> None:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    manager = RealBenchmarkSearchManager(config)
    search = manager.search(spec.id)
    candidates = manager.load_candidates(spec.id)

    rendered = render_real_benchmark_candidates(search, candidates)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-real-benchmark-candidates", "--benchmark-id", spec.id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Real Benchmark Candidates" in rendered
    assert "License:" in rendered
    assert "mapping assessment is required" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Real Benchmark Candidates" in cli.stdout
    assert "real-benchmark-agentdojo" in cli.stdout
