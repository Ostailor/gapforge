from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project
from test_selected_related_work_completion import _attach_papers, _complete_real_papers

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript import ManuscriptManager
from gapforge.models import Paper, Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.drastic_panel import DrasticReviewPanelBuilder
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES, SelectedBenchmarkRelatedWorkManager
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager
from gapforge.selected_benchmark.related_work_matrix_loader import (
    RelatedWorkMatrixLoader,
    render_related_work_matrix_load_result,
)
from gapforge.selected_benchmark.related_work_matrix_v2 import SelectedBenchmarkRelatedWorkMatrixV2Manager
from gapforge.state import slugify, utc_now_iso


def test_loader_loads_existing_matrix_v2_fixture(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, _manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    result = RelatedWorkMatrixLoader(config).load(benchmark_id)

    assert result.status == "loaded"
    assert result.entry_count >= len(REQUIRED_RELATED_WORK_CATEGORIES)
    assert result.must_cite_count > 0
    assert result.closest_prior_work_count > 0
    assert result.blockers == []
    assert result.selected_path.endswith("related_work_matrix_v2.json")


def test_loader_repairs_matrix_from_v24_fixture_for_drastic_review(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)

    repair = RelatedWorkMatrixLoader(config).repair(benchmark_id)
    panel = DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)
    novelty = next(review for review in panel.reviewer_reports if review.reviewer_id == "R1")

    assert repair.status == "repaired"
    assert repair.repaired_matrix_id
    assert not any("missing:related_work_matrix" in flaw for flaw in novelty.fatal_flaws)
    assert any("related-work-matrix" in evidence for evidence in novelty.evidence_or_prior_work)


def test_missing_must_cite_blocks_load(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, _manuscript_id = _complete_fixture(tmp_path)
    manager = SelectedBenchmarkRelatedWorkMatrixV2Manager(config)
    matrix = manager.build(benchmark_id)
    matrix.must_cite_ids.append("missing-paper-id")
    manager.matrix_path(benchmark_id).write_text(json.dumps(to_plain(matrix), indent=2) + "\n", encoding="utf-8")

    result = RelatedWorkMatrixLoader(config).load(benchmark_id)

    assert result.status == "invalid"
    assert "missing-paper-id" in "\n".join(result.blockers)
    assert any("Unknown related-work paper IDs" in blocker for blocker in result.blockers)


def test_fallback_only_category_remains_warning_and_blocker(tmp_path: Path) -> None:
    config, project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(project_id).id
    _attach_papers(
        config,
        project_id,
        [
            Paper(
                id="fallback-low-fpr",
                title="Low false positive specificity fallback",
                authors=[],
                abstract="low false positive specificity",
                year=2025,
                source="fixture",
                raw_metadata={"fallback": True},
                provenance=Provenance(
                    created_by_skill="fixture",
                    timestamp=utc_now_iso(),
                    reasoning_summary="fallback related-work fixture",
                ),
            )
        ],
    )
    SelectedBenchmarkRelatedWorkManager(config).build_related_work_matrix(benchmark_id)

    result = RelatedWorkMatrixLoader(config).load(benchmark_id)

    assert result.status == "invalid"
    assert any("Fallback-only" in blocker for blocker in result.blockers)
    assert result.missing_categories


def test_matrix_load_report_renders_and_cli_status(tmp_path: Path) -> None:
    config, _project_id, benchmark_id, _manuscript_id = _complete_fixture(tmp_path)
    SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(benchmark_id)
    result = RelatedWorkMatrixLoader(config).load(benchmark_id)

    rendered = render_related_work_matrix_load_result(result)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-related-work-matrix-status", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Related-Work Matrix Load Result" in rendered
    assert "Candidate Paths" in rendered
    assert cli.returncode == 0, cli.stderr
    assert "Related-Work Matrix Load Result" in cli.stdout
    assert "Status: `loaded`" in cli.stdout


def _complete_fixture(tmp_path: Path) -> tuple[GapForgeConfig, str, str, str]:
    config, project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(project_id).id
    _attach_papers(config, project_id, _complete_real_papers())
    curation = RelatedWorkCurationManager(config)
    for index, category in enumerate(REQUIRED_RELATED_WORK_CATEGORIES):
        paper_id = _complete_real_papers()[index].id
        relationship = "closest_prior_work" if index == 0 else "background"
        if category == "benchmark/evaluation protocol papers":
            relationship = "baseline_source"
        curation.attach_paper(benchmark_id, category=category, paper_id=paper_id, relationship=relationship)
    manuscript_id = _create_selected_manuscript(config, project_id, benchmark_id)
    return config, project_id, benchmark_id, manuscript_id


def _create_selected_manuscript(config: GapForgeConfig, project_id: str, benchmark_id: str) -> str:
    direction_id = f"selected-benchmark-{slugify(benchmark_id)}"
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=project_id, direction_id=direction_id)
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id=direction_id,
        workspace_id=workspace.id,
        title="Sequential specificity benchmark for low-FPR collusion audits",
    )
    root = manager.manuscript_root(state.manuscript.id)
    sections = {
        "abstract": "We study sequential specificity for low-FPR collusion audits.",
        "introduction": "This paper contribution is a benchmark protocol for sequential specificity.",
        "related_work": "Closest prior work and benchmark baselines are compared.",
        "method": "The method uses vetted benchmark adapters and synthetic protocol scaffolding.",
        "results": "Results report specificity, uncertainty, power, ablation evidence, and baseline monitors.",
        "limitations": "Limitations include synthetic data validity and benchmark adaptation boundaries.",
    }
    for section_type, text in sections.items():
        section = manager.create_section(manuscript_id=state.manuscript.id, section_type=section_type, title=section_type.title())
        (root / section.content_path).write_text(f"# {section.title}\n\n{text}\n", encoding="utf-8")
    ProjectMemoryManager(config).load_project(project_id)
    return state.manuscript.id
