from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, PaperSection
from gapforge.orchestrator import Orchestrator
from gapforge.reporting import write_final_report
from gapforge.sources.coverage import refresh_source_coverage


def test_query_record_is_created_for_search(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FixtureSource()])

    state = orchestrator.search("low false positive collusion detection", max_results=5)

    assert state.search_queries
    record = state.search_queries[0]
    assert record.purpose == "initial_topic"
    assert record.query == "low false positive collusion detection"
    assert record.source_names == ["Fixture"]
    assert record.result_paper_ids == ["paper-1"]
    assert state.source_coverage is not None
    assert state.source_coverage.searched_sources == ["Fixture"]


def test_source_failures_are_recorded_in_query_and_coverage(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FailingSource(), FixtureSource()])

    state = orchestrator.search("collusion detection", max_results=5)

    assert state.search_queries[0].failure_messages
    assert state.source_coverage is not None
    assert "Failing" in state.source_coverage.failed_sources
    assert any("Failing search failed" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_warns_when_all_papers_are_fallback(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("fallback fixture")
    state.papers = [
        Paper(
            id="fallback-1",
            title="Fallback Paper",
            authors=[],
            abstract="fallback",
            year=2024,
            source="arXiv",
            raw_metadata={"fallback": True},
        )
    ]

    refresh_source_coverage(state)

    assert state.source_coverage is not None
    assert state.source_coverage.fallback_paper_count == 1
    assert any("smoke test" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_warns_without_full_text_and_improves_with_sections(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("coverage fixture")
    state.papers = [Paper(id="p1", title="Paper", authors=[], abstract="abstract", year=2024, source="manual")]

    refresh_source_coverage(state)
    assert state.source_coverage is not None
    assert state.source_coverage.papers_with_full_text == []
    assert any("No parsed full text" in warning for warning in state.source_coverage.coverage_warnings)

    state.paper_sections = [
        PaperSection(id="s1", paper_id="p1", title="Results", section_type="results", text="Results show useful evidence.")
    ]
    refresh_source_coverage(state)

    assert state.source_coverage.papers_with_full_text == ["p1"]
    assert not any("No parsed full text" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_cli_and_final_report_include_source_coverage(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FixtureSource()])
    state = orchestrator.search("collusion detection", max_results=5)
    orchestrator.state_store.save_run(state)

    write_final_report(state)
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "coverage", "--run-id", state.run_id],
        cwd=tmp_path,
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = (Path(state.run_dir) / "final_report.md").read_text(encoding="utf-8")

    assert "Search and Source Coverage" in report
    assert "Queries run: 1" in report
    assert (Path(state.run_dir) / "source_coverage.md").exists()


class FixtureSource:
    name = "Fixture"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [Paper(id="paper-1", title=f"Paper for {query}", authors=[], abstract="abstract", year=2025, source=self.name)]


class FailingSource:
    name = "Failing"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("source unavailable")
