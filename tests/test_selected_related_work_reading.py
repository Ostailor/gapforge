from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, PaperSection
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager
from gapforge.selected_benchmark.related_work_reading import (
    RelatedWorkReadingManager,
    render_related_work_reading_report,
)
from gapforge.state import ResearchStateManager

LOW_FPR_CATEGORY = "low-FPR detection/evaluation"


def test_full_text_fixture_creates_evidence_spans(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(
        config,
        project_id,
        [_real_paper("real-low-fpr")],
        sections=[
            PaperSection(
                id="real-low-fpr-methods",
                paper_id="real-low-fpr",
                title="Methods",
                normalized_title="methods",
                section_type="method",
                text="This paper solves low false-positive detector calibration with a benchmark protocol.",
                page_start=2,
                page_end=2,
                confidence="medium",
            ),
            PaperSection(
                id="real-low-fpr-limitations",
                paper_id="real-low-fpr",
                title="Limitations",
                normalized_title="limitations",
                section_type="limitations",
                text="It does not solve multi-agent collusion deployment validity.",
                page_start=8,
                page_end=8,
                confidence="medium",
            ),
        ],
    )
    RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="real-low-fpr")

    statuses = RelatedWorkReadingManager(config).read(benchmark_id)
    status = statuses[0]

    assert status.source_basis == "full_text"
    assert status.sections_used == ["real-low-fpr-methods", "real-low-fpr-limitations"]
    assert status.evidence_span_ids
    assert status.extracted_contributions
    assert status.extracted_limitations
    assert status.confidence == "high"


def test_abstract_only_reading_has_lower_confidence(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_real_paper("real-low-fpr")])
    RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="real-low-fpr")

    status = RelatedWorkReadingManager(config).read(benchmark_id)[0]

    assert status.source_basis == "abstract_only"
    assert status.confidence == "medium"
    assert any("abstract-only" in blocker for blocker in status.blockers)
    assert status.extracted_contributions


def test_metadata_only_reading_marks_missing_full_text_warning(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_metadata_only_paper("metadata-only")])
    RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="metadata-only")

    status = RelatedWorkReadingManager(config).read(benchmark_id)[0]

    assert status.source_basis == "metadata_only"
    assert status.confidence == "low"
    assert any("Missing full text and abstract" in blocker for blocker in status.blockers)


def test_reading_report_renders_and_cli_single_paper(tmp_path: Path) -> None:
    config, project_id, benchmark_id = _benchmark(tmp_path)
    _attach_papers(config, project_id, [_real_paper("real-low-fpr")])
    RelatedWorkCurationManager(config).attach_paper(benchmark_id, category=LOW_FPR_CATEGORY, paper_id="real-low-fpr")
    manager = RelatedWorkReadingManager(config)
    statuses = manager.read(benchmark_id, paper_id="real-low-fpr")

    rendered = render_related_work_reading_report(statuses)

    assert "# Selected Related-Work Reading Report" in rendered
    assert "real-low-fpr" in rendered
    assert "abstract_only" in rendered

    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "selected-related-work-reading-report",
            "--benchmark-id",
            benchmark_id,
        ],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Selected Related-Work Reading Report" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id


def _attach_papers(
    config: GapForgeConfig,
    project_id: str,
    papers: list[Paper],
    *,
    sections: list[PaperSection] | None = None,
) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("selected benchmark related work reading")
    run.papers = papers
    run.paper_sections = sections or []
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _real_paper(paper_id: str) -> Paper:
    return Paper(
        id=paper_id,
        title="Low false positive specificity evaluation for detectors",
        authors=["A. Researcher"],
        abstract="This paper solves false alarm calibration but does not evaluate multi-agent collusion deployment.",
        year=2025,
        source="arxiv",
        arxiv_id="2501.00001",
    )


def _metadata_only_paper(paper_id: str) -> Paper:
    return Paper(
        id=paper_id,
        title="Low false positive specificity evaluation metadata record",
        authors=["A. Researcher"],
        abstract="",
        year=2025,
        source="arxiv",
        arxiv_id="2501.00002",
    )
