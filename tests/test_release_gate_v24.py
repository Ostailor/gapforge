from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_release_gate_v22 import _complete_v22_fixture, _env
from test_release_gate_v23 import _complete_main_outputs
from test_selected_publication_review import _complete_related_work, _duplicate_real_papers, _write_manuscript_inputs

from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v24 import V24ReleaseGateEnforcer
from gapforge.selected_benchmark import (
    RelatedWorkReadingManager,
    RequiredRelatedWorkSearchManager,
    SelectedBenchmarkPositioningManager,
    SelectedBenchmarkPriorWorkRefreshManager,
    SelectedBenchmarkRelatedWorkManuscriptManager,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedMainManuscriptManager,
)


def test_v24_gate_fails_when_missing_related_work_search(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_v24_fixture(config, project_id, benchmark_id, include_search=False)

    result = V24ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.decision_status == "revise_related_work"
    assert result.requirements["related_work_search_campaign_exists"] is False
    assert any("search campaign" in blocker.lower() for blocker in result.blockers)


def test_v24_gate_fails_on_fake_citation(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_v24_fixture(config, project_id, benchmark_id)
    root = _selected_root(config, project_id)
    matrix_path = root / "related_work_matrix_v2" / "related_work_matrix_v2.json"
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    payload["must_cite_ids"] = [*payload["must_cite_ids"], "invented-paper"]
    matrix_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    result = V24ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_fake_citations"] is False
    assert any("fake citation" in blocker.lower() for blocker in result.blockers)


def test_v24_gate_fails_on_hidden_missing_category(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_v24_fixture(config, project_id, benchmark_id, missing_categories_visible=True)
    root = _selected_root(config, project_id)
    matrix_path = root / "related_work_matrix_v2" / "related_work_matrix_v2.json"
    matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix_payload["missing_categories"] = []
    matrix_path.write_text(json.dumps(matrix_payload, indent=2) + "\n", encoding="utf-8")

    result = V24ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_hidden_missing_categories"] is False
    assert any("missing categor" in blocker.lower() for blocker in result.blockers)


def test_v24_completed_related_work_yields_publication_or_workshop_candidate_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_v24_fixture(config, project_id, benchmark_id)

    result = V24ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.decision_status in {"publication_candidate", "workshop_candidate"}
    assert result.requirements["v23_release_gate_passes"] is True
    assert result.requirements["no_publication_ready_claim_unless_review_passes"] is True

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v24-release-gate", "--write-report", "--json"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    payload = json.loads(cli.stdout)
    assert payload["passed"] is True
    assert payload["decision_status"] in {"publication_candidate", "workshop_candidate"}


def test_v24_duplicate_prior_work_yields_no_go(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    _complete_v24_fixture(config, project_id, benchmark_id, duplicate=True)

    result = V24ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.decision_status == "no_go"
    assert result.requirements["publication_review_rerun_after_related_work_exists"] is True


def _complete_v24_fixture(
    config: object,
    project_id: str,
    benchmark_id: str,
    *,
    include_search: bool = True,
    duplicate: bool = False,
    missing_categories_visible: bool = False,
) -> None:
    if include_search:
        RequiredRelatedWorkSearchManager(config).plan(benchmark_id)  # type: ignore[arg-type]
    _complete_related_work(config, project_id, benchmark_id, curate=not missing_categories_visible, duplicate=duplicate)
    if missing_categories_visible:
        papers = _duplicate_real_papers() if duplicate else _duplicate_real_papers()
        from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager

        RelatedWorkCurationManager(config).attach_paper(  # type: ignore[arg-type]
            benchmark_id,
            category="low-FPR detection/evaluation",
            paper_id=papers[0].id,
            relationship="background",
        )
    _complete_main_outputs(config, benchmark_id, negative_count=3000, positive_count=20)
    _write_manuscript_inputs(config, project_id)
    SelectedMainManuscriptManager(config).paper_package(benchmark_id)  # type: ignore[arg-type]
    RelatedWorkReadingManager(config).report(benchmark_id)  # type: ignore[arg-type]
    SelectedBenchmarkPriorWorkRefreshManager(config).refresh(benchmark_id)  # type: ignore[arg-type]
    SelectedBenchmarkPositioningManager(config).build(benchmark_id)  # type: ignore[arg-type]
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)  # type: ignore[arg-type]
    SelectedBenchmarkReviewerPanelBuilder(config).publication_review(benchmark_id, after_related_work=True)  # type: ignore[arg-type]
    SelectedBenchmarkRelatedWorkManuscriptManager(config).paper_package_v24(benchmark_id)  # type: ignore[arg-type]


def _selected_root(config: object, project_id: str) -> Path:
    return Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"  # type: ignore[arg-type]
