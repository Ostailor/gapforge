from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_release_gate_v22 import _complete_v22_fixture, _env
from test_selected_related_work_completion import _attach_papers, _complete_real_papers

from gapforge.models import to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v23 import V23ReleaseGateEnforcer
from gapforge.selected_benchmark import (
    MainPowerManager,
    RelatedWorkCompletionManager,
    SelectedMainManuscriptManager,
)
from gapforge.selected_benchmark.main_dataset import MainDatasetBuilder
from gapforge.selected_benchmark.main_run import MainRunManager


def test_v23_gate_fails_when_missing_related_work_is_hidden(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_main_outputs(config, benchmark_id, negative_count=3000, positive_count=20)
    RelatedWorkCompletionManager(config).complete(benchmark_id)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)
    _hide_related_work_blockers(config, project_id)

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_missing_real_related_work_hidden"] is False
    assert any("related work" in blocker.lower() for blocker in result.blockers)


def test_v23_gate_fails_on_alpha_overclaim(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _attach_papers(config, project_id, _complete_real_papers())
    RelatedWorkCompletionManager(config).complete(benchmark_id)
    _complete_main_outputs(config, benchmark_id, negative_count=300, positive_count=20)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"
    (root / "main_manuscript" / "alpha_overclaim.md").write_text(
        "The manuscript demonstrates alpha=0.001 operational specificity support.\n",
        encoding="utf-8",
    )

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_alpha_overclaim"] is False
    assert any("alpha=0.001" in blocker for blocker in result.blockers)


def test_v23_publication_candidate_complete_fixture_passes_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _attach_papers(config, project_id, _complete_real_papers())
    RelatedWorkCompletionManager(config).complete(benchmark_id)
    _complete_main_outputs(config, benchmark_id, negative_count=3000, positive_count=20)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.decision_status == "publication_candidate"
    assert result.requirements["publication_readiness_review_exists"] is True
    assert result.requirements["no_synthetic_deployment_validity_overclaim"] is True

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v23-release-gate", "--write-report", "--json"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    payload = json.loads(cli.stdout)
    assert payload["passed"] is True
    assert payload["decision_status"] == "publication_candidate"


def test_v23_revise_benchmark_decision_passes_with_warning(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_main_outputs(config, benchmark_id, negative_count=3000, positive_count=20)
    RelatedWorkCompletionManager(config).complete(benchmark_id)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.decision_status == "revise_benchmark"
    assert any("revise_benchmark" in warning for warning in result.warnings)
    assert result.requirements["no_missing_real_related_work_hidden"] is True


def test_v23_no_go_decision_passes_if_honest(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _attach_papers(config, project_id, _complete_real_papers())
    status = RelatedWorkCompletionManager(config).complete(benchmark_id)
    status.novelty_status = "duplicate"
    _write_related_work_status(config, project_id, status)
    _complete_main_outputs(config, benchmark_id, negative_count=3000, positive_count=20)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.decision_status == "no_go"
    assert any("no_go" in warning for warning in result.warnings)


def _complete_main_outputs(config: object, benchmark_id: str, *, negative_count: int, positive_count: int) -> None:
    power_manager = MainPowerManager(config)  # type: ignore[arg-type]
    power_manager.create_plan(benchmark_id, planned_negative_count=negative_count, planned_positive_count=positive_count)
    power_manager.decide_alpha(benchmark_id, alpha_level=0.001)
    dataset = MainDatasetBuilder(config).build(benchmark_id)  # type: ignore[arg-type]
    run_manager = MainRunManager(config)  # type: ignore[arg-type]
    execution = run_manager.run(benchmark_id, run_manager.create_manifest(benchmark_id, dataset.id).id)
    from gapforge.selected_benchmark.main_analysis import MainAnalysisManager

    MainAnalysisManager(config).analyze(execution.id)  # type: ignore[arg-type]


def _hide_related_work_blockers(config: object, project_id: str) -> None:
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"  # type: ignore[arg-type]
    (root / "reviews" / "main_publication_review.json").write_text(
        json.dumps(
            {
                "id": "hidden-review",
                "benchmark_id": "hidden",
                "readiness": "conference_candidate",
                "fatal_blockers": [],
                "major_blockers": [],
                "required_revisions": [],
                "confidence": "medium",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "go_no_go" / "go_no_go.json").write_text(
        json.dumps(
            {
                "id": "hidden-go",
                "benchmark_id": "hidden",
                "decision": "go_publication_candidate",
                "reason": "hidden",
                "evidence": [],
                "blockers": [],
                "required_next_steps": [],
                "confidence": "medium",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manuscript_path = root / "main_manuscript" / "selected_main_manuscript.json"
    payload = json.loads(manuscript_path.read_text(encoding="utf-8"))
    payload["status"] = "publication_candidate"
    payload["publication_candidate"] = True
    payload["fatal_blockers"] = []
    payload["major_blockers"] = []
    payload["required_revisions"] = []
    payload["unresolved_blockers"] = []
    manuscript_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_related_work_status(config: object, project_id: str, status: object) -> None:
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"  # type: ignore[arg-type]
    path = root / "related_work_completion" / "related_work_completion_status.json"
    path.write_text(json.dumps(to_plain(status), indent=2) + "\n", encoding="utf-8")
