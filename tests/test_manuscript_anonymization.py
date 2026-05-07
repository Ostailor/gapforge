from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.anonymization import ManuscriptAnonymizer
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.venues import ManuscriptVenueManager
from gapforge.models import Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_anonymized_copy_created_and_original_preserved(tmp_path: Path) -> None:
    config, manuscript_id, section_path = _anonymization_fixture(tmp_path)
    original = section_path.read_text(encoding="utf-8")

    report = ManuscriptAnonymizer(config).anonymize(manuscript_id)
    root = ManuscriptManager(config).manuscript_root(manuscript_id)
    anonymized_section = root / "submission" / "anonymized" / "sections" / section_path.name

    assert report.status == "pass"
    assert anonymized_section.exists()
    assert "{{AUTHOR_NAMES}}" not in anonymized_section.read_text(encoding="utf-8")
    assert "Anonymous Authors" in anonymized_section.read_text(encoding="utf-8")
    assert section_path.read_text(encoding="utf-8") == original


def test_repo_url_detected(tmp_path: Path) -> None:
    config, manuscript_id, section_path = _anonymization_fixture(tmp_path)
    section_path.write_text(section_path.read_text(encoding="utf-8") + "\nCode: https://github.com/acme/secret-repo\n", encoding="utf-8")

    report = ManuscriptAnonymizer(config).check(manuscript_id)

    assert report.status == "fail"
    assert any(leak.leak_type == "repository_url" for leak in report.detected_identity_leaks)


def test_local_path_detected(tmp_path: Path) -> None:
    config, manuscript_id, section_path = _anonymization_fixture(tmp_path)
    section_path.write_text(section_path.read_text(encoding="utf-8") + "\nLogs: /Users/alovelace/private/results.json\n", encoding="utf-8")

    report = ManuscriptAnonymizer(config).check(manuscript_id)

    assert report.status == "fail"
    assert any(leak.leak_type == "path" for leak in report.detected_identity_leaks)


def test_self_citation_warning_for_anonymous_venue(tmp_path: Path) -> None:
    config, manuscript_id, _section_path = _anonymization_fixture(tmp_path, build_bibliography=True)

    report = ManuscriptAnonymizer(config).check(manuscript_id)

    assert report.status == "warning"
    assert any(leak.leak_type == "self_citation" for leak in report.detected_identity_leaks)
    assert all(leak.severity == "warning" for leak in report.detected_identity_leaks)


def test_non_anonymous_venue_does_not_block(tmp_path: Path) -> None:
    config, manuscript_id, section_path = _anonymization_fixture(tmp_path)
    ManuscriptVenueManager(config).set_venue(manuscript_id, "arxiv_preprint")
    section_path.write_text(section_path.read_text(encoding="utf-8") + "\nCode: https://github.com/acme/secret-repo\n", encoding="utf-8")

    report = ManuscriptAnonymizer(config).check(manuscript_id)

    assert report.status == "warning"
    assert any(leak.severity == "info" for leak in report.detected_identity_leaks)
    assert any("does not require anonymization" in warning for warning in report.warnings)


def test_anonymization_cli_lifecycle(tmp_path: Path) -> None:
    _config, manuscript_id, _section_path = _anonymization_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    anonymized = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "anonymize-manuscript", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    checked = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "anonymization-check", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    deanonymized = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "deanonymize-package", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert anonymized.returncode == 0, anonymized.stderr
    assert checked.returncode == 0, checked.stderr
    assert deanonymized.returncode == 0, deanonymized.stderr
    assert "Anonymization Report" in anonymized.stdout
    assert "Anonymization Report" in checked.stdout
    assert "Deanonymized package intentionally preserves" in deanonymized.stdout


def _anonymization_fixture(
    tmp_path: Path,
    *,
    build_bibliography: bool = False,
) -> tuple[GapForgeConfig, str, Path]:
    config = GapForgeConfig.from_cwd(tmp_path)
    run = ResearchStateManager(config).create_run("blind review fixture")
    run.papers = [
        Paper(
            id="paper-self",
            title="Traceable Blind Review",
            authors=["Ada Lovelace"],
            abstract="Self work.",
            year=2025,
            venue="ICLR",
            doi="10.1000/blind",
        )
    ]
    ResearchStateManager(config).save_run(run)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Blind Review Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    manuscript_manager = ManuscriptManager(config)
    state = manuscript_manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-blind",
        workspace_id="workspace-blind",
        title="Blind Review Draft",
    )
    ManuscriptVenueManager(config).set_venue(state.manuscript.id, "generic_conference")
    section = manuscript_manager.create_section(
        manuscript_id=state.manuscript.id,
        section_type="introduction",
        title="Introduction",
        source_paper_ids=["paper-self"] if build_bibliography else [],
    )
    root = manuscript_manager.manuscript_root(state.manuscript.id)
    config_path = root / "submission" / "anonymization_config.json"
    config_path.write_text(
        json.dumps(
            {
                "author_names": ["Ada Lovelace"],
                "affiliations": ["Analytical Engine Lab"],
                "project_names": ["Blind Review Project"],
                "repository_urls": ["https://github.com/acme/blind-review"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    section_path = root / section.content_path
    section_path.write_text(
        "# Introduction\n\nAuthors: {{AUTHOR_NAMES}}\nAffiliation: {{AFFILIATION}}\nProject: {{PROJECT_NAME}}\n",
        encoding="utf-8",
    )
    if build_bibliography:
        ManuscriptBibliographyManager(config).build(state.manuscript.id)
    return config, state.manuscript.id, section_path
