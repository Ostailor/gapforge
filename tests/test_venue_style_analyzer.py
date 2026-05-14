from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_manuscripts import _project

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.models import to_plain
from gapforge.style_corpus import StyleCorpusManager, VenueStyleAnalyzer


def test_style_profile_from_fixtures(tmp_path: Path) -> None:
    config, _project_id = _style_corpus_fixture(tmp_path, paper_count=3)

    profile = VenueStyleAnalyzer(config).analyze("generic_ml_conference")

    assert profile.venue_profile_id == "generic_ml_conference"
    assert len(profile.corpus_paper_ids) == 3
    assert profile.section_order_distribution["paper_count"] == 3
    assert profile.abstract_length_stats["with_abstract_count"] == 3
    assert profile.experiment_section_patterns["present_count"] == 3
    assert profile.caveat_patterns["limitations_present_count"] == 3


def test_recommendations_generated(tmp_path: Path) -> None:
    config, project_id = _style_corpus_fixture(tmp_path, paper_count=3)
    manuscript_id = _manuscript_fixture(config, project_id)

    recommendations = VenueStyleAnalyzer(config).recommend(manuscript_id)

    assert {recommendation.recommendation_type for recommendation in recommendations} >= {
        "section_order",
        "abstract_length",
        "contribution_framing",
        "limitations",
    }
    assert all(recommendation.evidence_from_style_corpus for recommendation in recommendations)
    assert all(
        "must not override evidence" in recommendation.risk or "evidence" in recommendation.risk for recommendation in recommendations
    )


def test_too_small_corpus_warning(tmp_path: Path) -> None:
    config, project_id = _style_corpus_fixture(tmp_path, paper_count=1)
    manuscript_id = _manuscript_fixture(config, project_id)

    profile = VenueStyleAnalyzer(config).analyze("generic_ml_conference")
    recommendations = VenueStyleAnalyzer(config).recommend(manuscript_id)
    report = VenueStyleAnalyzer(config).render_report("generic_ml_conference")

    assert profile.abstract_length_stats["too_small_corpus"] is True
    assert "corpus is too small" in report
    assert all(recommendation.risk.startswith("high: corpus too small") for recommendation in recommendations)


def test_no_copied_text_in_recommendations(tmp_path: Path) -> None:
    config, project_id = _style_corpus_fixture(tmp_path, paper_count=3, unique_phrase="UNIQUE_DO_NOT_COPY_STYLE_ANALYZER_PROSE")
    manuscript_id = _manuscript_fixture(config, project_id)

    recommendations = VenueStyleAnalyzer(config).recommend(manuscript_id)
    rendered = VenueStyleAnalyzer(config).render_recommendations(manuscript_id)
    payload = json.dumps(to_plain(recommendations), indent=2)

    assert "UNIQUE_DO_NOT_COPY_STYLE_ANALYZER_PROSE" not in payload
    assert "UNIQUE_DO_NOT_COPY_STYLE_ANALYZER_PROSE" not in rendered


def test_venue_style_cli_commands(tmp_path: Path) -> None:
    config, project_id = _style_corpus_fixture(tmp_path, paper_count=3)
    manuscript_id = _manuscript_fixture(config, project_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    analyze = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-style-analyze", "--venue", "generic_ml_conference"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    recommend = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-style-recommend", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "venue-style-report", "--venue", "generic_ml_conference"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert analyze.returncode == 0, analyze.stderr
    assert json.loads(analyze.stdout)["venue_profile_id"] == "generic_ml_conference"
    assert recommend.returncode == 0, recommend.stderr
    assert "Venue Style Recommendations" in recommend.stdout
    assert "structural/rhetorical only" in recommend.stdout
    assert report.returncode == 0, report.stderr
    assert "Venue Style Report" in report.stdout


def _style_corpus_fixture(
    tmp_path: Path, *, paper_count: int, unique_phrase: str = "UNIQUE_DO_NOT_COPY_PROSE"
) -> tuple[GapForgeConfig, str]:
    config, project_id = _project(tmp_path)
    manager = StyleCorpusManager(config)
    for index in range(paper_count):
        manager.add_tex(_synthetic_tex(tmp_path, index, unique_phrase=unique_phrase), "generic_ml_conference", year=2025)
    return config, project_id


def _manuscript_fixture(config: GapForgeConfig, project_id: str) -> str:
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-style",
        workspace_id="workspace-style",
        title="Venue Style Draft",
        target_venue="generic_ml_conference",
    )
    manager.create_section(manuscript_id=state.manuscript.id, section_type="abstract", title="Abstract", status="drafted")
    manager.create_section(manuscript_id=state.manuscript.id, section_type="introduction", title="Introduction", status="drafted")
    manager.create_section(manuscript_id=state.manuscript.id, section_type="method", title="Method", status="drafted")
    return state.manuscript.id


def _synthetic_tex(tmp_path: Path, index: int, *, unique_phrase: str) -> Path:
    tex_path = tmp_path / f"style-paper-{index}.tex"
    result_section = "Experiments" if index % 2 == 0 else "Evaluation"
    tex_path.write_text(
        f"""
% SPDX-License-Identifier: CC-BY-4.0
\\documentclass{{article}}
\\title{{A Fixture Style Paper {index}}}
\\begin{{document}}
\\begin{{abstract}}
We propose a benchmark protocol and evaluate it carefully with calibration and caveats.
\\end{{abstract}}
\\section{{Introduction}}
{unique_phrase} This sentence must never enter recommendations.
We introduce a measurement benchmark and we show calibrated behavior \\cite{{one,two}}.
\\section{{Related Work}}
Prior work is categorized structurally.
\\section{{Method}}
\\begin{{figure}}\\caption{{A figure}}\\end{{figure}}
\\section{{{result_section}}}
\\begin{{table}}\\caption{{A table}}\\end{{table}}
\\section{{Limitations}}
Threats to validity remain.
\\end{{document}}
""",
        encoding="utf-8",
    )
    return tex_path
