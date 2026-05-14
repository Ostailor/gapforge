from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_manuscripts import _project

from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.venue_rewriter import VenueManuscriptRewriter
from gapforge.style_corpus import StyleCorpusManager


def test_rewrite_improves_section_structure(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)

    result = VenueManuscriptRewriter(config).rewrite(manuscript_id, "generic_ml_conference")
    state = ManuscriptManager(config).load_state(manuscript_id)
    section_order = [section.section_type for section in state.sections]

    assert result.style_revision_report is not None
    assert section_order[:4] == ["abstract", "introduction", "related_work", "method"]
    assert "limitations" in section_order
    assert any("Added missing required section" in change for change in result.style_revision_report.structural_changes)


def test_rewrite_does_not_add_unsupported_claim(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path, unsupported_claim=True)
    manager = ManuscriptManager(config)
    before_claims = manager.load_state(manuscript_id).claim_uses

    result = VenueManuscriptRewriter(config).rewrite(manuscript_id, "generic_ml_conference")
    after_state = manager.load_state(manuscript_id)
    root = manager.manuscript_root(manuscript_id)
    rewritten_text = "\n".join((root / section.content_path).read_text(encoding="utf-8") for section in after_state.sections)

    assert len(after_state.claim_uses) == len(before_claims)
    assert all(claim.claim_text != "This benchmark is state of the art." for claim in after_state.claim_uses)
    assert "state of the art" not in rewritten_text.lower()
    assert result.claim_softening_report is not None
    assert "unsupported-claim" in result.claim_softening_report.unsupported_claim_ids


def test_rewrite_preserves_limitations(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    manager = ManuscriptManager(config)
    state = manager.load_state(manuscript_id)
    limitation = next(section for section in state.sections if section.section_type == "limitations")
    root = manager.manuscript_root(manuscript_id)
    original_phrase = "ORIGINAL_LIMITATION_SENTENCE: deployment validity remains unproven."
    (root / limitation.content_path).write_text(f"# Limitations\n\n{original_phrase}\n", encoding="utf-8")

    result = VenueManuscriptRewriter(config).rewrite(manuscript_id, "generic_ml_conference")
    rewritten = (root / limitation.content_path).read_text(encoding="utf-8")

    assert result.style_revision_report is not None
    assert result.style_revision_report.limitations_preserved is True
    assert original_phrase in rewritten


def test_copied_text_detector_fixture_catches_copied_phrase(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    copied_phrase = "This source sentence contains exactly enough words to trigger copied text detection safely."
    _style_source_fixture(tmp_path, config, copied_phrase)
    manager = ManuscriptManager(config)
    state = manager.load_state(manuscript_id)
    intro = next(section for section in state.sections if section.section_type == "introduction")
    root = manager.manuscript_root(manuscript_id)
    (root / intro.content_path).write_text(f"# Introduction\n\n{copied_phrase}\n", encoding="utf-8")

    result = VenueManuscriptRewriter(config).rewrite(manuscript_id, "generic_ml_conference")

    assert result.style_revision_report is not None
    assert result.style_revision_report.copied_text_warnings
    assert result.style_revision_report.status == "not_publication_ready"
    assert any("Possible copied source sentence" in warning for warning in result.style_revision_report.copied_text_warnings)


def test_style_report_renders_and_cli(tmp_path: Path) -> None:
    config, manuscript_id = _manuscript_fixture(tmp_path)
    report = VenueManuscriptRewriter(config).rewrite(manuscript_id, "generic_ml_conference").style_revision_report
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    style_report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-style-report", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    rewrite = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-rewrite-for-venue",
            "--manuscript-id",
            manuscript_id,
            "--venue",
            "generic_ml_conference",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report is not None
    assert style_report.returncode == 0, style_report.stderr
    assert "Venue Style Revision" in style_report.stdout
    assert "Venue style changes are structural and rhetorical only" in style_report.stdout
    assert rewrite.returncode == 0, rewrite.stderr
    assert json.loads(rewrite.stdout)["venue_profile_id"] == "generic_ml_conference"


def _manuscript_fixture(tmp_path: Path, *, unsupported_claim: bool = False):
    config, project_id = _project(tmp_path)
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-venue-rewrite",
        workspace_id="workspace-venue-rewrite",
        title="Venue Rewrite Draft",
    )
    intro = manager.create_section(
        manuscript_id=state.manuscript.id,
        section_type="introduction",
        title="Introduction",
        status="drafted",
    )
    manager.create_section(
        manuscript_id=state.manuscript.id,
        section_type="limitations",
        title="Limitations",
        status="drafted",
    )
    if unsupported_claim:
        manager.link_claim_use(
            manuscript_id=state.manuscript.id,
            section_id=intro.id,
            claim_id="unsupported-claim",
            claim_text="A monitoring claim without evidence.",
            use_type="result",
            support_status="unsupported",
        )
    return config, state.manuscript.id


def _style_source_fixture(tmp_path: Path, config, copied_phrase: str) -> None:
    source = tmp_path / "source-paper.tex"
    source.write_text(
        f"""
% SPDX-License-Identifier: CC-BY-4.0
\\documentclass{{article}}
\\title{{Copied Text Detector Source}}
\\begin{{document}}
\\begin{{abstract}}
We propose a structural benchmark paper fixture.
\\end{{abstract}}
\\section{{Introduction}}
{copied_phrase}
\\section{{Experiments}}
We evaluate the method with fixture results.
\\section{{Limitations}}
Known limits remain visible.
\\end{{document}}
""",
        encoding="utf-8",
    )
    StyleCorpusManager(config).add_tex(source, "generic_ml_conference")
