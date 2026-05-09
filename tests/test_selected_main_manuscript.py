from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env
from test_selected_publication_review import (
    _benchmark,
    _complete_main_analysis,
    _complete_pilot_analysis,
    _complete_related_work,
)

from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import (
    SelectedMainManuscriptManager,
    render_selected_main_manuscript,
)


def test_pilot_only_main_manuscript_is_labeled_pilot_candidate(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_pilot_analysis(config, benchmark_id, negative_count=40, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)

    manuscript = SelectedMainManuscriptManager(config).generate(benchmark_id)
    rendered = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert manuscript.evidence_maturity == "pilot"
    assert manuscript.status == "workshop_candidate"
    assert manuscript.publication_candidate is False
    assert "Run type: `pilot`" in rendered
    assert "conference_candidate" not in rendered


def test_main_manuscript_is_publication_candidate_only_when_gates_pass(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)

    manuscript = SelectedMainManuscriptManager(config).generate(benchmark_id)

    assert manuscript.evidence_maturity == "main"
    assert manuscript.status == "publication_candidate"
    assert manuscript.publication_candidate is True
    assert manuscript.unresolved_blockers == []
    assert manuscript.go_no_go_decision == "go_publication_candidate"


def test_main_manuscript_blocks_synthetic_deployment_overclaim(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_pilot_analysis(config, benchmark_id, negative_count=40, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)
    root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"
    manuscript_dir = root / "main_manuscript"
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    (manuscript_dir / "overclaim.md").write_text("This package claims deployment validity from synthetic data.\n", encoding="utf-8")

    manuscript = SelectedMainManuscriptManager(config).generate(benchmark_id)
    rendered = render_selected_main_manuscript(manuscript)

    assert manuscript.publication_candidate is False
    assert any("deployment" in blocker.lower() for blocker in manuscript.fatal_blockers)
    assert "deployment-validity claims are blocked" in rendered.lower()


def test_unresolved_blockers_are_visible_in_main_manuscript(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    _complete_main_analysis(config, benchmark_id, negative_count=3000, positive_count=20)

    manuscript = SelectedMainManuscriptManager(config).generate(benchmark_id)
    rendered = Path(manuscript.manuscript_path).read_text(encoding="utf-8")

    assert manuscript.publication_candidate is False
    assert manuscript.unresolved_blockers
    assert any("related work" in blocker.lower() for blocker in manuscript.unresolved_blockers)
    assert "Unresolved Blockers" in rendered
    assert "related work" in rendered.lower()


def test_main_paper_package_renders_and_cli(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _complete_pilot_analysis(config, benchmark_id, negative_count=40, positive_count=20)
    _complete_related_work(config, project_id, benchmark_id)

    package = SelectedMainManuscriptManager(config).paper_package(benchmark_id)
    package_dir = Path(package.package_dir)

    assert package.human_decision_ready is True
    assert "selected_main_manuscript.md" in package.files
    assert "main_artifact_manifest.json" in package.files
    assert "publication_readiness_review.md" in package.files
    assert (package_dir / "README.md").exists()

    manuscript_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-main-manuscript", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    package_cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-main-paper-package", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert manuscript_cli.returncode == 0, manuscript_cli.stderr
    assert package_cli.returncode == 0, package_cli.stderr
    assert json.loads(manuscript_cli.stdout)["status"] == "workshop_candidate"
    assert "selected_main_manuscript.md" in json.loads(package_cli.stdout)["files"]
