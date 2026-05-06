from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.sources.canonical import canonicalize_run, canonicalize_run_state, render_merge_report, write_merge_artifacts
from gapforge.state import ResearchStateManager


def test_doi_duplicates_merge_and_preserve_richer_metadata(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.papers = [
        Paper(
            id="crossref-1",
            title="Low FPR Collusion Detection",
            authors=["Ada Author"],
            abstract="Short.",
            year=2025,
            source="Crossref",
            doi="https://doi.org/10.1234/example",
            url="https://publisher.example/paper",
            raw_metadata={"venue": "Conference A"},
        ),
        Paper(
            id="s2-1",
            title="Low-FPR Collusion Detection",
            authors=["Ada Author"],
            abstract="This is a substantially richer abstract about low false-positive collusion detection.",
            year=2025,
            source="Semantic Scholar",
            doi="10.1234/example",
            pdf_url="https://example.org/paper.pdf",
            citation_count=42,
            raw_metadata={"paperId": "S2-123", "venue": "Conference A"},
        ),
    ]

    identities, decisions = canonicalize_run_state(state)

    assert len(state.papers) == 1
    kept = state.papers[0]
    assert kept.id == "s2-1"
    assert kept.pdf_url == "https://example.org/paper.pdf"
    assert kept.url == "https://publisher.example/paper"
    assert kept.citation_count == 42
    assert "richer abstract" in kept.abstract
    assert kept.raw_metadata["source_paper_ids"] == ["s2-1", "crossref-1"]
    assert len(decisions) == 1
    assert decisions[0].merged_paper_ids == ["crossref-1"]
    assert "matching DOI" in decisions[0].merge_reason
    assert identities[0].doi == "10.1234/example"


def test_arxiv_duplicates_merge(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.papers = [
        Paper(id="arxiv", title="A Paper", authors=["A"], abstract="A", year=2024, arxiv_id="2401.00001v1"),
        Paper(id="web", title="A Paper", authors=["A"], abstract="A", year=2024, url="https://arxiv.org/abs/2401.00001v1"),
    ]

    _, decisions = canonicalize_run_state(state)

    assert len(state.papers) == 1
    assert decisions[0].merged_paper_ids
    assert "arXiv" in decisions[0].merge_reason


def test_similar_unrelated_title_does_not_merge(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.papers = [
        Paper(id="p1", title="Low FPR Collusion Detection", authors=["Ada"], abstract="A", year=2025),
        Paper(id="p2", title="Low FPR Collision Detection", authors=["Grace"], abstract="B", year=2025),
    ]

    _, decisions = canonicalize_run_state(state)

    assert len(state.papers) == 2
    assert decisions == []


def test_exact_normalized_title_merges(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.papers = [
        Paper(id="p1", title="Low-FPR: Collusion Detection!", authors=["Ada"], abstract="A", year=2025),
        Paper(id="p2", title="Low FPR Collusion Detection", authors=["Different"], abstract="B", year=2024),
    ]

    _, decisions = canonicalize_run_state(state)

    assert len(state.papers) == 1
    assert "exact normalized title" in decisions[0].merge_reason


def test_merge_report_renders_and_files_are_written(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.papers = [
        Paper(id="p1", title="Paper", authors=["A"], abstract="A", year=2025, doi="10.1/x"),
        Paper(id="p2", title="Paper", authors=["A"], abstract="B", year=2025, doi="10.1/x"),
    ]
    identities, decisions = canonicalize_run_state(state)

    identities_path, decisions_path, report_path = write_merge_artifacts(tmp_path, identities, decisions)
    rendered = render_merge_report(identities, decisions)

    assert identities_path.exists()
    assert decisions_path.exists()
    assert report_path.exists()
    assert "Paper Merge Report" in rendered
    assert json.loads(decisions_path.read_text(encoding="utf-8"))[0]["kept_paper_id"] in {"p1", "p2"}


def test_canonicalize_run_cli_path_updates_papers(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("canonical test")
    state.papers = [
        Paper(id="p1", title="Paper", authors=["A"], abstract="A", year=2025, doi="10.1/x"),
        Paper(id="p2", title="Paper", authors=["A"], abstract="B", year=2025, doi="10.1/x"),
    ]
    manager.save_run(state)

    _, decisions = canonicalize_run(config, state.run_id)
    reloaded = manager.load_run(state.run_id)

    assert len(decisions) == 1
    assert len(reloaded.papers) == 1
    assert (Path(reloaded.run_dir) / "paper_merge_report.md").exists()


def _state(tmp_path: Path):
    config = GapForgeConfig.from_cwd(tmp_path)
    return ResearchStateManager(config).create_run("canonicalization")
