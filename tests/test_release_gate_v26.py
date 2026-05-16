from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v26 import V26ReleaseGateEnforcer, render_v26_release_gate_markdown


def test_v26_missing_related_work_matrix_fails(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, matrix=False)

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["related_work_matrix_load_result_loaded"] is False


def test_v26_missing_artifact_package_fails(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, artifact=False)

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["artifact_package_load_result_loaded"] is False


def test_v26_missing_benchmark_search_or_no_fit_fails(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, benchmark_search=False)

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["real_benchmark_search_or_no_fit_exists"] is False


def test_v26_resolved_blockers_can_be_conference_candidate_and_cli_json(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, package_status="conference_candidate", likely_decision="accept_likely", adapter_support="primary")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = V26ReleaseGateEnforcer(config).evaluate()
    rendered = render_v26_release_gate_markdown(result)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v26-release-gate", "--paper-quality", "--write-report", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.passed is True
    assert result.status == "conference_candidate"
    assert result.top_conference_readiness is True
    assert result.paper_quality_score >= 0.7
    assert "GapForge v2.6 Release Gate" in rendered
    assert "paper_quality_score" in rendered
    assert cli.returncode == 0, cli.stderr
    cli_payload = json.loads(cli.stdout)
    assert cli_payload["status"] == "conference_candidate"
    assert cli_payload["top_conference_readiness"] is True
    assert (tmp_path / "data" / "release_gate" / "v26_release_gate_latest.json").exists()


def test_v26_workshop_candidate_passes_but_not_top_conference_ready(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path)

    result = V26ReleaseGateEnforcer(config).evaluate()
    rendered = render_v26_release_gate_markdown(result)

    assert result.passed is True
    assert result.status == "workshop_candidate"
    assert result.top_conference_readiness is False
    assert result.workshop_readiness is True
    assert result.paper_quality_status == "workshop_candidate"
    assert "workshop_candidate" in rendered
    assert "not top-conference readiness" in rendered


def test_v26_borderline_reject_caps_readiness_as_progress_not_success(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, likely_decision="borderline_reject")

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.status == "workshop_candidate"
    assert result.top_conference_readiness is False
    assert result.paper_quality_score <= 0.5
    assert "progress" in result.paper_quality_status
    assert any("borderline reject" in warning for warning in result.warnings)


def test_v26_accepts_v25_revise_record_and_negative_safety_statements(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path)
    project_root = next((tmp_path / "projects").glob("*"))
    v25_path = tmp_path / "data" / "release_gate" / "v25_release_gate_latest.json"
    v25 = json.loads(v25_path.read_text(encoding="utf-8"))
    v25["passed"] = False
    v25["status"] = "revise_for_reviews"
    v25_path.write_text(json.dumps(v25, indent=2) + "\n", encoding="utf-8")
    (project_root / "guardrails.md").write_text(
        "No fake citations or fake results are allowed.\nDo not invent citations or results.\nNo copied venue-style prose is generated.\n",
        encoding="utf-8",
    )

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.requirements["v25_release_gate_completed"] is True
    assert result.requirements["fake_citations_results_blocked"] is True
    assert result.requirements["no_copied_paper_prose"] is True
    assert result.status == "workshop_candidate"


def test_v26_unresolved_fatal_blockers_revise_for_reviews(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, remaining_fatal=True, package_status="revise_for_reviews")

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "revise_for_reviews"
    assert result.requirements["no_hidden_fatal_blockers"] is True


def test_v26_hidden_fatal_blockers_are_no_go(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, remaining_fatal=True, package_status="workshop_candidate")

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["no_hidden_fatal_blockers"] is False


def test_v26_fake_citation_fails(tmp_path: Path) -> None:
    config = _v26_fixture(tmp_path, fake_citation=True)

    result = V26ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["fake_citations_results_blocked"] is False
    assert result.safety_score == 0.0
    assert result.top_conference_readiness is False


def _v26_fixture(
    tmp_path: Path,
    *,
    matrix: bool = True,
    artifact: bool = True,
    benchmark_search: bool = True,
    no_fit: bool = False,
    remaining_fatal: bool = False,
    fake_citation: bool = False,
    package_status: str = "workshop_candidate",
    likely_decision: str = "revise_before_submission",
    adapter_support: str = "auxiliary",
) -> GapForgeConfig:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("V26 Gate Project")
    project_root = Path(program.project.root_dir)
    benchmark_id = "benchmark-v26-fixture"
    manuscript_id = "manuscript-v26-fixture"
    benchmark_dir = project_root / "selected_benchmark"
    manuscript_root = project_root / "manuscripts" / manuscript_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    (manuscript_root / "reviews" / "drastic").mkdir(parents=True, exist_ok=True)

    _write_json(
        config.data_dir / "release_gate" / "v25_release_gate_latest.json",
        {
            "passed": True,
            "status": "conference_candidate",
            "project_id": program.project.id,
            "benchmark_id": benchmark_id,
            "manuscript_id": manuscript_id,
            "blockers": [],
        },
    )
    if matrix:
        _write_json(
            benchmark_dir / "related_work_matrix_loader" / "related_work_matrix_load_result.json",
            {
                "id": "related-work-matrix-load-v26",
                "benchmark_id": benchmark_id,
                "manuscript_id": manuscript_id,
                "status": "loaded",
                "matrix_id": "related-work-matrix-v26",
                "entry_count": 8,
                "must_cite_count": 3,
                "closest_prior_work_count": 1,
                "fallback_entries_promoted": False,
                "warnings": [],
                "blockers": [],
            },
        )
    if artifact:
        _write_json(
            benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json",
            {
                "id": "artifact-package-load-v26",
                "benchmark_id": benchmark_id,
                "manuscript_id": manuscript_id,
                "status": "loaded",
                "selected_package_id": "artifact-package-v26",
                "required_files_present": ["README.md", "run.sh", "expected_outputs.json"],
                "missing_files": [],
                "expected_outputs_present": True,
                "replication_package_present": True,
                "hardware_requirements_present": True,
                "run_instructions_present": True,
                "warnings": [],
                "blockers": [],
            },
        )
    if benchmark_search:
        _write_benchmark_search_fixture(benchmark_dir, benchmark_id, no_fit=no_fit, adapter_support=adapter_support)

    _write_json(
        benchmark_dir / "venue_artifact_integration" / "report.json",
        {
            "id": "venue-artifact-integration-v26",
            "manuscript_id": manuscript_id,
            "related_work_matrix_status": "loaded",
            "artifact_package_status": "loaded",
            "real_benchmark_status": "no_fit" if no_fit else "complete",
            "integrated_sections": ["related_work", "artifact_appendix", "limitations"],
            "updated_citations": ["paper-fixture-1"],
            "updated_artifact_links": ["artifact-package-v26"],
            "warnings": [],
            "blockers": [],
        },
    )
    remaining = ["missing:benchmark_results persisted benchmark results are incomplete."] if remaining_fatal else []
    _write_json(
        manuscript_root / "reviews" / "drastic" / "drastic_review_rerun_result.json",
        {
            "id": "drastic-review-rerun-v26",
            "manuscript_id": manuscript_id,
            "previous_review_id": "drastic-review-v25",
            "new_review_id": "drastic-review-v26",
            "resolved_blockers": ["missing:related_work_matrix", "missing:artifact_package"],
            "remaining_blockers": remaining,
            "readiness_change": "fatal_blockers_resolved" if not remaining else "fatal_blockers_remain",
            "likely_decision": likely_decision if not remaining else "reject_likely",
        },
    )
    _write_json(
        benchmark_dir / "venue_revision_package" / "latest.json",
        {
            "id": "venue-revision-package-v26",
            "manuscript_id": manuscript_id,
            "venue_profile_id": "generic_ml_conference",
            "status": package_status,
            "files": ["manuscript.pdf", "references.bib", "artifact-package-v26"],
            "related_work_matrix_id": "related-work-matrix-v26",
            "artifact_package_id": "artifact-package-v26",
            "drastic_review_id": "drastic-review-v26",
            "revision_plan_id": "drastic-revision-plan-v26",
            "limitations": remaining + ["Real public benchmark evidence is labeled by claim support level."],
        },
    )
    if fake_citation:
        (manuscript_root / "submission.md").write_text("Smith et al. 2024 reports an invented result.", encoding="utf-8")
    return config


def _write_benchmark_search_fixture(
    benchmark_dir: Path,
    benchmark_id: str,
    *,
    no_fit: bool,
    adapter_support: str,
) -> None:
    search_dir = benchmark_dir / "real_benchmark_search"
    if no_fit:
        _write_json(
            search_dir / "real_benchmark_candidate_search.json",
            {
                "id": "real-benchmark-search-v26",
                "selected_benchmark_id": benchmark_id,
                "search_queries": ["public multi-agent collusion benchmark"],
                "candidate_benchmark_ids": [],
                "rejected_candidate_ids": ["public-dataset-no-fit"],
                "no_fit_reason": "No candidate survived claim-mapping assessment.",
                "status": "no_fit",
            },
        )
        (search_dir / "real_benchmark_no_fit_report.md").write_text(
            "# Real Benchmark No-Fit\n\nNo candidate survived mapping; a new benchmark protocol is needed.\n",
            encoding="utf-8",
        )
        _write_json(
            benchmark_dir / "real_benchmark_experiments" / "real_benchmark_experiment_attempts.json",
            [{"id": "attempt-no-fit", "status": "no_fit", "limitations": ["No public benchmark fit."]}],
        )
        return

    candidate_id = "real-public-candidate-v26"
    _write_json(
        search_dir / "real_benchmark_candidate_search.json",
        {
            "id": "real-benchmark-search-v26",
            "selected_benchmark_id": benchmark_id,
            "search_queries": ["public multi-agent monitoring benchmark"],
            "candidate_benchmark_ids": [candidate_id],
            "rejected_candidate_ids": [],
            "no_fit_reason": "",
            "status": "complete",
        },
    )
    _write_json(
        benchmark_dir / "real_benchmark_adapters" / f"{candidate_id}.assessment.json",
        {
            "id": "real-benchmark-adapter-assessment-v26",
            "candidate_benchmark_id": candidate_id,
            "selected_benchmark_id": benchmark_id,
            "adapter_possible": True,
            "adapter_type": adapter_support,
            "schema_mismatches": [],
            "label_mismatches": [],
            "sequentialization_needed": False,
            "observability_mapping": "Monitor observations are mapped only as auxiliary evidence.",
            "expected_claim_support": adapter_support,
            "blockers": [],
        },
    )
    _write_json(
        benchmark_dir / "real_benchmark_experiments" / "real_benchmark_experiment_attempts.json",
        [
            {
                "id": "real-benchmark-experiment-v26",
                "selected_benchmark_id": benchmark_id,
                "candidate_benchmark_id": candidate_id,
                "adapter_id": "adapter-v26",
                "status": "complete",
                "run_type": "fixture",
                "metric_results": {"accuracy": 0.5},
                "claim_support_level": adapter_support,
                "limitations": [f"{adapter_support.title()} evidence only."],
            }
        ],
    )


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
