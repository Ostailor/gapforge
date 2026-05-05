from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.citations import CitationGraphBuilder, RelatedWorkExpander
from gapforge.config import GapForgeConfig
from gapforge.models import Gap, Paper, PaperTriageDecision, PaperTriageResult
from gapforge.orchestrator import Orchestrator
from gapforge.state import ResearchStateManager


def test_build_graph_from_fixture_metadata(tmp_path: Path) -> None:
    state = _citation_state(tmp_path)

    graph = CitationGraphBuilder().build(state)

    assert graph.paper_ids == ["p1", "p2", "p3"]
    assert any(edge.source_paper_id == "p1" and edge.target_paper_id == "p2" and edge.edge_type == "cites" for edge in graph.edges)
    assert any(edge.source_paper_id == "p1" and edge.target_paper_id == "p3" and edge.edge_type == "cited_by" for edge in graph.edges)


def test_unresolved_references_are_tracked(tmp_path: Path) -> None:
    state = _citation_state(tmp_path)

    graph = CitationGraphBuilder().build(state)

    assert any("Unresolved Reference" in item for item in graph.unresolved_references)


def test_expansion_records_query_and_adds_deduped_papers(tmp_path: Path) -> None:
    state = _citation_state(tmp_path)
    CitationGraphBuilder().build(state)
    state.paper_triage = PaperTriageResult(
        topic=state.topic.text,
        decisions=[PaperTriageDecision(paper_id="p1", title="Main Method", tier="Tier 1", score=90)],
    )
    state.gaps = [Gap(id="gap-1", title="Benchmark gap", type="benchmark gap", description="Need better benchmark.")]
    source = ExpansionSource()

    added = RelatedWorkExpander([source]).expand(state, max_new_papers=5)

    assert len(added) == 1
    assert any(paper.id == "new-related" for paper in state.papers)
    assert sum(1 for paper in state.papers if paper.doi == "10.1/main") == 1
    assert any(record.purpose == "citation_expansion" for record in state.search_queries)
    assert state.source_coverage is not None
    assert any(record.purpose == "citation_expansion" for record in state.source_coverage.query_records)


def test_failed_citation_resolver_does_not_crash_run(tmp_path: Path) -> None:
    state = _citation_state(tmp_path)
    CitationGraphBuilder().build(state)

    added = RelatedWorkExpander([FailingExpansionSource()]).expand(state, max_new_papers=3)

    assert added == []
    assert any(record.failure_messages for record in state.search_queries)
    assert state.source_coverage is not None
    assert "FailingExpansion" in state.source_coverage.failed_sources


def test_citation_cli_writes_artifacts(tmp_path: Path) -> None:
    state = _citation_state(tmp_path)
    ResearchStateManager(GapForgeConfig.from_cwd(tmp_path)).save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    graph_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "build-citation-graph", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert graph_result.returncode == 0, graph_result.stderr
    assert (Path(state.run_dir) / "citation_graph.json").exists()
    assert (Path(state.run_dir) / "citation_graph.md").exists()


def test_orchestrator_citation_expansion_before_novelty(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = Orchestrator(config, sources=[ExpansionSource()]).run("collusion benchmark", max_papers=8, stop_after="citation-expansion")

    assert state.citation_graph is not None
    assert any(step.name == "citation-expansion" and step.status == "complete" for step in state.orchestrator_plan.steps)


def _citation_state(tmp_path: Path):
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("citation fixture")
    state.papers = [
        Paper(
            id="p1",
            title="Main Method",
            authors=["Ada Lovelace"],
            abstract="A collusion benchmark method.",
            year=2025,
            source="Semantic Scholar",
            doi="10.1/main",
            semantic_scholar_id="s2-main",
            raw_metadata={
                "references": [
                    {"paperId": "s2-ref", "title": "Resolved Reference"},
                    {"paperId": "s2-missing", "title": "Unresolved Reference"},
                ],
                "citations": [{"paperId": "s2-citing", "title": "Citing Paper"}],
                "influentialCitationCount": 7,
            },
        ),
        Paper(
            id="p2",
            title="Resolved Reference",
            authors=[],
            abstract="reference",
            year=2023,
            source="Semantic Scholar",
            semantic_scholar_id="s2-ref",
        ),
        Paper(
            id="p3",
            title="Citing Paper",
            authors=[],
            abstract="citing",
            year=2026,
            source="Semantic Scholar",
            semantic_scholar_id="s2-citing",
        ),
    ]
    return state


class ExpansionSource:
    name = "Expansion"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id="dup-main",
                title="Main Method",
                authors=[],
                abstract="duplicate",
                year=2025,
                source=self.name,
                doi="10.1/main",
            ),
            Paper(
                id="new-related",
                title=f"Related Work for {query[:20]}",
                authors=[],
                abstract="new related work",
                year=2026,
                source=self.name,
            ),
        ][:max_results]


class FailingExpansionSource:
    name = "FailingExpansion"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("resolver unavailable")
