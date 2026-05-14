from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v25 import V25ReleaseGateEnforcer, render_v25_release_gate_markdown


def test_v25_missing_vetted_benchmark_or_no_fit_report_fails(tmp_path: Path) -> None:
    config = _v25_fixture(tmp_path, mapping=False, adapter=False)

    result = V25ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["selected_idea_mapped_or_no_fit_justified"] is False
    assert result.requirements["vetted_benchmark_adapter_or_no_fit_report_exists"] is False


def test_v25_copied_prose_fails(tmp_path: Path) -> None:
    config = _v25_fixture(tmp_path, copied_prose=True)

    result = V25ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["no_copied_paper_prose"] is False


def test_v25_fake_citation_fails(tmp_path: Path) -> None:
    config = _v25_fixture(tmp_path, fake_citation=True)

    result = V25ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["fake_citations_results_blocked"] is False


def test_v25_drastic_fatal_blockers_revise_for_reviews(tmp_path: Path) -> None:
    config = _v25_fixture(tmp_path, drastic_fatal=True)

    result = V25ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "revise_for_reviews"
    assert result.requirements["no_publication_ready_claim_if_drastic_fatal_blockers"] is True


def test_v25_complete_fixture_passes_and_cli_json(tmp_path: Path) -> None:
    config = _v25_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = V25ReleaseGateEnforcer(config).evaluate()
    rendered = render_v25_release_gate_markdown(result)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v25-release-gate", "--write-report", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.passed is True
    assert result.status == "conference_candidate"
    assert "GapForge v2.5 Release Gate" in rendered
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["status"] == "conference_candidate"
    assert (tmp_path / "data" / "release_gate" / "v25_release_gate_latest.json").exists()


def _v25_fixture(
    tmp_path: Path,
    *,
    mapping: bool = True,
    adapter: bool = True,
    copied_prose: bool = False,
    fake_citation: bool = False,
    drastic_fatal: bool = False,
) -> GapForgeConfig:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("V25 Gate Project")
    project_root = Path(program.project.root_dir)
    benchmark_id = "benchmark-v25-fixture"
    manuscript_id = "manuscript-v25-fixture"
    benchmark_dir = project_root / "selected_benchmark"
    manuscript_root = project_root / "manuscripts" / manuscript_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    (manuscript_root / "submission").mkdir(parents=True, exist_ok=True)
    (manuscript_root / "reviews" / "drastic").mkdir(parents=True, exist_ok=True)

    _write_json(
        config.data_dir / "release_gate" / "v24_release_gate_latest.json",
        {
            "passed": True,
            "status": "pass",
            "project_id": program.project.id,
            "benchmark_id": benchmark_id,
            "decision_status": "publication_candidate",
            "blockers": [],
        },
    )
    _write_json(
        config.data_dir / "vetted_benchmarks" / "records" / "vetted-benchmark-fixture.record.json",
        {"id": "vetted-benchmark-fixture", "name": "Fixture Benchmark", "license": "MIT", "terms_of_use": "fixture"},
    )
    if adapter:
        _write_json(
            config.data_dir / "vetted_benchmarks" / "adapters" / "adapter-v25.adapter.json",
            {
                "id": "adapter-v25",
                "selected_benchmark_id": benchmark_id,
                "vetted_benchmark_id": "vetted-benchmark-fixture",
                "adapter_type": "auxiliary",
            },
        )
    if mapping:
        _write_json(
            benchmark_dir / "vetted_mapping" / "selected_vetted_benchmark_mapping_report.json",
            {
                "id": "selected-vetted-mapping-report-v25",
                "selected_benchmark_id": benchmark_id,
                "mappings": [
                    {
                        "id": "mapping-v25",
                        "selected_benchmark_id": benchmark_id,
                        "vetted_benchmark_id": "vetted-benchmark-fixture",
                        "mapping_type": "sanity_check",
                        "unsupported_claims": ["Does not validate real collusion traces."],
                    }
                ],
                "primary_candidate_ids": [],
                "auxiliary_candidate_ids": ["vetted-benchmark-fixture"],
                "rejected_candidate_ids": [],
                "conclusion": "No direct vetted benchmark is available; use as sanity-check evidence.",
            },
        )

    _write_json(manuscript_root / "submission" / "venue_profile.json", {"id": "generic_ml_conference"})
    _write_json(
        config.data_dir / "style_corpus" / "papers" / "style-paper-fixture.json",
        {
            "id": "style-paper-fixture",
            "title": "Synthetic Style Fixture",
            "venue": "generic_ml_conference",
            "license_status": "allowed",
            "local_source_path": str(tmp_path / "synthetic_fixture.tex"),
            "source_url": "synthetic://fixture",
        },
    )
    _write_json(
        config.data_dir / "style_corpus" / "analysis" / "generic-ml-conference.style_profile.json",
        {
            "id": "venue-style-generic-ml-conference",
            "venue_profile_id": "generic_ml_conference",
            "corpus_paper_ids": ["style-paper-fixture"],
        },
    )
    _write_json(
        manuscript_root / "submission" / "venue_style_revision_report.json",
        {
            "id": "venue-rewrite-v25",
            "manuscript_id": manuscript_id,
            "venue_profile_id": "generic_ml_conference",
            "status": "not_publication_ready" if drastic_fatal else "publication_ready",
            "publication_ready": False if drastic_fatal else True,
            "copied_text_warnings": ["Copied source sentence."] if copied_prose else [],
            "limitations_preserved": True,
        },
    )
    if copied_prose:
        (manuscript_root / "submission" / "copied.md").write_text("UNIQUE_STYLE_DO_NOT_COPY_MARKER", encoding="utf-8")

    dataset_dir = config.data_dir / "review_training" / "datasets" / "openreview_like_fixture"
    _write_json(
        dataset_dir / "dataset.json",
        {"id": "openreview_like_fixture", "source": "synthetic_fixture", "paper_count": 1, "review_count": 2},
    )
    _write_json(
        dataset_dir / "taxonomy" / "review_taxonomy_report.json",
        {"dataset_id": "openreview_like_fixture", "issue_counts": {"weak baselines": 1}, "severity_counts": {"major": 1}},
    )
    _write_json(
        dataset_dir / "reviewer_evaluation.json",
        {
            "id": "reviewer-evaluation-fixture",
            "model_id": "heuristic",
            "dataset_id": "openreview_like_fixture",
            "issue_recall_proxy": 1.0,
            "severity_calibration_score": 1.0,
            "review_specificity_score": 1.0,
            "hallucination_rate": 0.0,
            "evidence_linkage_score": 1.0,
        },
    )
    (dataset_dir / "reviewer_calibration_report.md").write_text("# Reviewer Calibration Report\n", encoding="utf-8")

    _write_json(
        manuscript_root / "reviews" / "drastic" / "drastic_review_panel.json",
        {
            "id": "drastic-review-panel-manuscript-v25",
            "target_id": manuscript_id,
            "target_type": "manuscript",
            "fatal_flaws": ["missing:benchmark_results no persisted results"] if drastic_fatal else [],
            "likely_decision": "reject_likely" if drastic_fatal else "revise_before_submission",
            "reviewer_reports": [],
        },
    )
    _write_json(
        manuscript_root / "reviews" / "drastic" / "drastic_revision_plan.json",
        {
            "id": "drastic-revision-plan-v25",
            "manuscript_id": manuscript_id,
            "review_panel_id": "drastic-review-panel-manuscript-v25",
            "fatal_fixes": ["fatal:missing:benchmark_results"] if drastic_fatal else [],
            "status": "fatal_blockers_open" if drastic_fatal else "ready",
        },
    )
    if fake_citation:
        (manuscript_root / "reviews" / "drastic" / "fake.md").write_text("Smith et al. 2024 reports an invented result.", encoding="utf-8")
    return config


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
