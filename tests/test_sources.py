from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.orchestrator import Orchestrator
from gapforge.sources.arxiv_source import ArxivSource
from gapforge.sources.crossref_source import CrossrefSource
from gapforge.sources.http_client import CachedHttpClient
from gapforge.sources.ranking import deduplicate_papers, rank_papers


class MockHttpClient:
    def __init__(self, *, text: str = "", payload: object | None = None, fail: bool = False) -> None:
        self.text = text
        self.payload = payload
        self.fail = fail
        self.calls = 0

    def get_text(self, url: str, params: dict[str, object] | None = None, *, namespace: str = "http") -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("source unavailable")
        return self.text

    def get_json(self, url: str, params: dict[str, object] | None = None, *, namespace: str = "http") -> object:
        self.calls += 1
        if self.fail:
            raise RuntimeError("source unavailable")
        return self.payload


def test_arxiv_source_normalizes_atom_response() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <published>2024-01-02T00:00:00Z</published>
        <title>Low False Positive Collusion Detection</title>
        <summary> A method paper. </summary>
        <author><name>Ada Lovelace</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/2401.00001v1" type="application/pdf"/>
        <arxiv:doi>10.48550/arXiv.2401.00001</arxiv:doi>
        <category term="cs.AI"/>
      </entry>
    </feed>"""
    source = ArxivSource(MockHttpClient(text=xml))  # type: ignore[arg-type]

    papers = source.search("collusion detection", max_results=5, sort="newest", date_from=None, date_to=None)

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2401.00001v1"
    assert papers[0].published_date == "2024-01-02"
    assert papers[0].pdf_url.endswith("2401.00001v1")


def test_crossref_source_normalizes_public_api_response() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1145/123",
                    "title": ["Low false positive collusion detection"],
                    "abstract": "<jats:p>Abstract text.</jats:p>",
                    "published-online": {"date-parts": [[2025, 5, 1]]},
                    "container-title": ["KDD"],
                    "URL": "https://doi.org/10.1145/123",
                    "author": [{"given": "Grace", "family": "Hopper"}],
                    "is-referenced-by-count": 42,
                    "subject": ["Computer Science"],
                }
            ]
        }
    }
    source = CrossrefSource(MockHttpClient(payload=payload))  # type: ignore[arg-type]

    papers = source.search("collusion detection", max_results=5, sort="newest", date_from=None, date_to=None)

    assert papers[0].doi == "10.1145/123"
    assert papers[0].citation_count == 42
    assert papers[0].venue == "KDD"
    assert papers[0].authors == ["Grace Hopper"]


def test_cached_http_client_reuses_cache(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr("gapforge.sources.http_client.urlopen", fake_urlopen)
    client = CachedHttpClient(tmp_path / ".gapforge_cache", retries=0)

    first = client.get_json("https://example.test/api", {"q": "x"}, namespace="fixture")
    second = client.get_json("https://example.test/api", {"q": "x"}, namespace="fixture")

    assert first == second == {"ok": True}
    assert calls["count"] == 1


def test_deduplicate_papers_merges_by_doi_and_ranks_newer_first() -> None:
    older = Paper(
        id="crossref-1",
        title="Low False Positive Collusion Detection",
        authors=[],
        abstract="short",
        year=2020,
        source="Crossref",
        doi="10.1/test",
        citation_count=3,
    )
    newer = Paper(
        id="s2-1",
        title="Low False Positive Collusion Detection",
        authors=["A"],
        abstract="longer abstract",
        year=2025,
        source="Semantic Scholar",
        doi="10.1/test",
        citation_count=50,
    )

    deduped = deduplicate_papers([older, newer])
    ranked = rank_papers("low false positive collusion detection", deduped, newest_first=True)

    assert len(deduped) == 1
    assert deduped[0].citation_count == 50
    assert ranked[0].title == "Low False Positive Collusion Detection"


def test_orchestrator_search_survives_failed_sources_and_writes_current_run(monkeypatch, tmp_path: Path) -> None:
    class FailingSource:
        name = "Failing"

        def search(self, *args, **kwargs):
            raise RuntimeError("boom")

    class WorkingSource:
        name = "Crossref"

        def search(self, *args, **kwargs):
            return [
                Paper(
                    id="paper-1",
                    title="Low False Positive Collusion Detection",
                    authors=[],
                    abstract="abstract",
                    year=2026,
                    source="Crossref",
                    citation_count=1,
                )
            ]

    monkeypatch.setattr("gapforge.orchestrator.default_sources", lambda config: [FailingSource(), WorkingSource()])
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")

    searched = orchestrator.search("low false positive collusion detection", max_results=10)

    assert searched.run_id == state.run_id
    papers_path = Path(searched.run_dir) / "papers.json"
    papers = json.loads(papers_path.read_text(encoding="utf-8"))
    assert papers[0]["id"] == "paper-1"
