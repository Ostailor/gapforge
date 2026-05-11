from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env
from test_selected_publication_review import _benchmark, _complete_main_analysis, _complete_related_work, _write_manuscript_inputs
from test_selected_related_work_completion import _attach_papers, _complete_real_papers

from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    RelatedWorkCurationManager,
    SelectedBenchmarkRelatedWorkManuscriptManager,
    render_selected_paper_package_v24,
    render_selected_related_work_manuscript_revision,
)
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_matrix_v2 import SelectedBenchmarkRelatedWorkMatrixV2Manager


def test_related_work_section_generated_with_real_citations(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id, curate=True)
    _write_manuscript_inputs(config, project_id)

    revision = SelectedBenchmarkRelatedWorkManuscriptManager(config).revise_related_work(benchmark_id)
    rendered = render_selected_related_work_manuscript_revision(revision)
    section = Path(revision.related_work_section_path).read_text(encoding="utf-8")

    assert "# Related Work" in section
    assert "[@real-low-fpr]" in section
    assert "## Closest Prior Work Comparison" in section
    assert "Must-cite coverage" in section
    assert revision.missing_categories == []
    assert "fake" not in rendered.lower()


def test_fake_citation_blocked(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_related_work(config, project_id, benchmark_id, curate=True)

    matrix_manager = SelectedBenchmarkRelatedWorkMatrixV2Manager(config)
    matrix = matrix_manager.build(benchmark_id)
    matrix_path = matrix_manager.matrix_path(benchmark_id)
    matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix_payload["must_cite_ids"] = [*matrix.must_cite_ids, "invented-paper"]
    matrix_path.write_text(json.dumps(matrix_payload, indent=2) + "\n", encoding="utf-8")

    manager = SelectedBenchmarkRelatedWorkManuscriptManager(config)
    try:
        manager.revise_related_work(benchmark_id)
    except ValueError as exc:
        assert "fake citations" in str(exc).lower()
    else:
        raise AssertionError("fake citation was not blocked")


def test_missing_categories_visible_in_related_work_section(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    papers = _complete_real_papers()
    _attach_papers(config, project_id, papers)
    RelatedWorkCurationManager(config).attach_paper(
        benchmark_id,
        category=REQUIRED_RELATED_WORK_CATEGORIES[0],
        paper_id=papers[0].id,
        relationship="background",
    )

    revision = SelectedBenchmarkRelatedWorkManuscriptManager(config).revise_related_work(benchmark_id)
    section = Path(revision.related_work_section_path).read_text(encoding="utf-8")

    assert revision.missing_categories
    assert "Missing related-work categories" in section
    assert REQUIRED_RELATED_WORK_CATEGORIES[1] in section


def test_positioning_update_includes_softened_claims_and_synthetic_limitations(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_related_work(config, project_id, benchmark_id, curate=True)
    _write_manuscript_inputs(config, project_id)

    revision = SelectedBenchmarkRelatedWorkManuscriptManager(config).update_positioning(benchmark_id)
    positioning = Path(revision.positioning_section_path).read_text(encoding="utf-8")

    assert "candidate evaluation protocol" in positioning.lower()
    assert "synthetic" in positioning.lower()
    assert "deployment validity" in positioning.lower()
    assert "first novel SOTA deployment-valid" not in positioning


def test_v24_paper_package_renders_and_readiness_is_honest(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id, curate=True)
    _write_manuscript_inputs(config, project_id)

    package = SelectedBenchmarkRelatedWorkManuscriptManager(config).paper_package_v24(benchmark_id)
    rendered = render_selected_paper_package_v24(package)

    assert package.publication_ready is True
    assert package.publication_readiness == "publication_candidate"
    assert "related_work_v24.md" in package.files
    assert "publication_readiness_v24.md" in package.files
    assert "Publication-ready status requires publication review pass" in rendered
    assert Path(package.package_dir, "README.md").exists()


def test_v24_package_cli_renders(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id, curate=True)
    _write_manuscript_inputs(config, project_id)

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-paper-package-v24", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "selected-paper-package-v24" in cli.stdout
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir)
    assert (root / "selected_benchmark" / "paper_package_v24" / "README.md").exists()
