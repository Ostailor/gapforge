from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.models import Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_build_bibliography_from_known_papers(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(tmp_path)

    bibliography = ManuscriptBibliographyManager(config).build(manuscript_id)

    assert bibliography.manuscript_id == manuscript_id
    assert [entry.paper_id for entry in bibliography.entries] == ["paper-1", "paper-2"]
    assert bibliography.entries[0].citation_key == "lovelace2025traceable"
    assert bibliography.entries[0].metadata_completeness["authors"] == "present"
    assert bibliography.missing_metadata == {}


def test_duplicate_papers_dedupe_by_doi(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(
        tmp_path,
        extra_papers=[
            Paper(
                id="paper-duplicate",
                title="Traceable Manuscripts",
                authors=["Ada Lovelace"],
                abstract="Duplicate record.",
                year=2025,
                doi="10.1000/trace",
            )
        ],
        section_paper_ids=["paper-1", "paper-duplicate"],
    )

    bibliography = ManuscriptBibliographyManager(config).build(manuscript_id)

    assert [entry.paper_id for entry in bibliography.entries] == ["paper-1"]
    assert bibliography.duplicate_entries["paper-duplicate"] == "paper-1"


def test_missing_metadata_warns(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(tmp_path, section_paper_ids=["paper-missing"])

    bibliography = ManuscriptBibliographyManager(config).build(manuscript_id)

    assert bibliography.entries[0].paper_id == "paper-missing"
    assert bibliography.missing_metadata["paper-missing"] == ["authors", "venue", "doi_or_arxiv"]
    assert bibliography.entries[0].metadata_completeness["authors"] == "missing"


def test_bibtex_exports(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(tmp_path)
    manager = ManuscriptBibliographyManager(config)
    manager.build(manuscript_id)

    bibtex = manager.export(manuscript_id, export_format="bibtex")

    assert "@article{lovelace2025traceable," in bibtex
    assert "doi = {10.1000/trace}" in bibtex
    assert "GapForge paper id: paper-1" in bibtex


def test_fake_citation_rejected(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(tmp_path)
    manager = ManuscriptManager(config)
    section = manager.load_state(manuscript_id).sections[0]
    manager.link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section.id,
        claim_id="claim-fake",
        claim_text="Fake citation should not enter the manuscript.",
        use_type="background",
        support_status="unsupported",
        citation_keys=["Fake Citation 2099"],
    )

    with pytest.raises(ValueError, match="Unresolved citation keys"):
        ManuscriptBibliographyManager(config).build(manuscript_id)


def test_unknown_paper_rejected(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_with_papers(tmp_path, section_paper_ids=["unknown-paper"])

    with pytest.raises(ValueError, match="unknown paper IDs"):
        ManuscriptBibliographyManager(config).build(manuscript_id)


def test_bibliography_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id = _manuscript_with_papers(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    build = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "bibliography-build", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    exported = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "bibliography-export", "--manuscript-id", manuscript_id, "--format", "bibtex"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    checked = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "citation-check", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "citation-list", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert build.returncode == 0, build.stderr
    assert exported.returncode == 0, exported.stderr
    assert checked.returncode == 0, checked.stderr
    assert listed.returncode == 0, listed.stderr
    assert json.loads(build.stdout)["id"] == "bibliography-manuscript-citation-draft"
    assert "@article{lovelace2025traceable," in exported.stdout
    assert "Citation check passed" in checked.stdout
    assert json.loads(listed.stdout)[0]["paper_id"] == "paper-1"


def _manuscript_with_papers(
    tmp_path: Path,
    *,
    extra_papers: list[Paper] | None = None,
    section_paper_ids: list[str] | None = None,
) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("citation manuscript")
    run.papers = [
        Paper(
            id="paper-1",
            title="Traceable Manuscripts",
            authors=["Ada Lovelace"],
            abstract="Manuscript traceability.",
            year=2025,
            venue="ICLR",
            doi="10.1000/trace",
            url="https://example.test/trace",
        ),
        Paper(
            id="paper-2",
            title="Auditable Artifacts",
            authors=["Grace Hopper", "Katherine Johnson"],
            abstract="Artifact evaluation.",
            year=2024,
            venue="NeurIPS",
            arxiv_id="2401.12345",
        ),
        Paper(
            id="paper-missing",
            title="Sparse Metadata",
            authors=[],
            abstract="Missing metadata.",
            year=0,
        ),
        *(extra_papers or []),
    ]
    state_manager.save_run(run)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Citation Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)

    manuscript_manager = ManuscriptManager(config)
    manuscript = manuscript_manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Citation Draft",
    )
    manuscript_manager.create_section(
        manuscript_id=manuscript.manuscript.id,
        section_type="related_work",
        source_paper_ids=section_paper_ids or ["paper-1", "paper-2"],
    )
    return config, manuscript.manuscript.id
