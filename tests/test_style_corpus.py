from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.style_corpus import StyleCorpusManager, check_tex_license, parse_tex_file


def test_parse_synthetic_tex_extracts_features_without_prose(tmp_path: Path) -> None:
    tex_path = _synthetic_tex(tmp_path)

    features = parse_tex_file(tex_path)

    assert features["title"] == "A Fixture Benchmark Paper"
    assert features["section_titles"] == ["Introduction", "Method", "Experiments", "Limitations"]
    assert features["abstract_length"] > 0
    assert features["figure_table_counts"] == {"figure": 1, "table": 1}
    assert "we_propose_statement" in features["contribution_statement_patterns"]
    assert features["limitations_presence"] is True


def test_style_corpus_add_tex_extracts_section_order_and_does_not_store_prose(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    tex_path = _synthetic_tex(tmp_path)

    record = StyleCorpusManager(config).add_tex(tex_path, "generic_ml_conference")
    paper_path = next((config.data_dir / "style_corpus" / "papers").glob("style-paper-*.json"))
    payload = json.loads(paper_path.read_text(encoding="utf-8"))

    assert record.status == "complete"
    assert payload["section_titles"] == ["Introduction", "Method", "Experiments", "Limitations"]
    assert "UNIQUE_DO_NOT_COPY_PROSE" not in paper_path.read_text(encoding="utf-8")


def test_license_unknown_warns(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    tex_path = tmp_path / "unknown.tex"
    tex_path.write_text("\\title{Unknown License}\\section{Intro} Text.\n", encoding="utf-8")

    record = StyleCorpusManager(config).add_tex(tex_path, "generic_ml_conference")
    paper = StyleCorpusManager(config).list_papers()[0]

    assert record.status == "warning"
    assert paper.license_status == "unknown"
    assert any("License" in warning and "unknown" in warning for warning in record.license_warnings)


def test_restricted_source_rejected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    tex_path = tmp_path / "restricted.tex"
    tex_path.write_text("% All rights reserved\n\\title{Restricted}\\section{Intro} Text.\n", encoding="utf-8")

    license_result = check_tex_license(tex_path)
    record = StyleCorpusManager(config).add_tex(tex_path, "generic_ml_conference")

    assert license_result.status == "restricted"
    assert record.status == "rejected"
    assert record.rejected_sources == [str(tex_path.resolve())]
    assert StyleCorpusManager(config).list_papers() == []


def test_style_corpus_report_and_cli_dry_run(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    StyleCorpusManager(config).add_tex(_synthetic_tex(tmp_path), "generic_ml_conference")
    report = StyleCorpusManager(config).render_report()
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    dry_run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "style-corpus-ingest", "--source", "arxiv-source", "--dry-run"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    cli_report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "style-corpus-report"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Style Corpus Report" in report
    assert "structural and stylistic features only" in report
    assert dry_run.returncode == 0, dry_run.stderr
    assert json.loads(dry_run.stdout)["status"] == "dry_run"
    assert cli_report.returncode == 0, cli_report.stderr
    assert "arxiv-source" in cli_report.stdout


def _synthetic_tex(tmp_path: Path) -> Path:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(
        """
% SPDX-License-Identifier: CC-BY-4.0
\\documentclass{article}
\\newcommand{\\method}{GapForge}
\\title{A Fixture Benchmark Paper}
\\begin{document}
\\begin{abstract}
We propose a benchmark protocol and evaluate it carefully.
\\end{abstract}
\\section{Introduction}
UNIQUE_DO_NOT_COPY_PROSE This sentence must never enter stored corpus features.
We propose a measurement benchmark and we show calibration behavior \\cite{one,two}.
\\section{Method}
\\begin{figure}\\caption{A figure}\\end{figure}
\\section{Experiments}
\\begin{table}\\caption{A table}\\end{table}
\\section{Limitations}
Threats to validity remain.
\\end{document}
""",
        encoding="utf-8",
    )
    return tex_path
