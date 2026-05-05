from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.fulltext.downloader import PdfDownloader, infer_pdf_url
from gapforge.fulltext.hashing import sha256_bytes
from gapforge.models import Paper, ResearchRunState
from gapforge.state import ResearchStateManager


class FakeBinaryHttpClient:
    def __init__(
        self,
        responses: dict[str, tuple[bytes, dict[str, str]]] | None = None,
        failures: dict[str, Exception] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.failures = failures or {}
        self.calls: list[str] = []

    def get_bytes(
        self,
        url: str,
        params: dict[str, object] | None = None,
        *,
        namespace: str = "http",
        max_bytes: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        self.calls.append(url)
        if url in self.failures:
            raise self.failures[url]
        data, response_headers = self.responses[url]
        if max_bytes is not None and len(data) > max_bytes:
            raise RuntimeError("response exceeds size limit")
        return data, response_headers


def test_successful_pdf_download_writes_run_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    state = _state_with_papers(tmp_path, [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026, pdf_url="https://x/p1.pdf")])
    pdf = b"%PDF-1.4\nfixture"
    client = FakeBinaryHttpClient({"https://x/p1.pdf": (pdf, {"content-type": "application/pdf"})})

    artifacts = PdfDownloader(http_client=client).download_for_state(state)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.status == "available"
    assert artifact.sha256 == sha256_bytes(pdf)
    stored_path = Path(state.run_dir) / artifact.local_path
    assert stored_path.exists()
    assert stored_path.read_bytes() == pdf
    assert "artifacts/papers/p1/" in artifact.local_path


def test_network_disabled_records_skipped_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    state = _state_with_papers(tmp_path, [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026, pdf_url="https://x/p1.pdf")])
    client = FakeBinaryHttpClient()

    artifacts = PdfDownloader(http_client=client).download_for_state(state)

    assert client.calls == []
    assert artifacts[0].status == "skipped"
    assert "Network disabled" in artifacts[0].error
    assert state.source_coverage is not None
    assert any("Network disabled" in warning for warning in state.source_coverage.coverage_warnings)


def test_invalid_non_pdf_response_is_recorded_as_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    state = _state_with_papers(tmp_path, [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026, pdf_url="https://x/p1")])
    client = FakeBinaryHttpClient({"https://x/p1": (b"<html>not a pdf</html>", {"content-type": "text/html"})})

    artifacts = PdfDownloader(http_client=client).download_for_state(state)

    assert artifacts[0].status == "failed"
    assert "content type" in artifacts[0].error
    assert state.source_coverage is not None
    assert artifacts[0].id in state.source_coverage.failed_downloads


def test_duplicate_hash_keeps_single_available_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    state = _state_with_papers(tmp_path, [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026, pdf_url="https://x/p1.pdf")])
    pdf = b"%PDF-1.4\nsame"
    client = FakeBinaryHttpClient({"https://x/p1.pdf": (pdf, {"content-type": "application/pdf"})})
    downloader = PdfDownloader(http_client=client)

    downloader.download_for_state(state)
    downloader.download_for_state(state)

    available = [artifact for artifact in state.paper_artifacts if artifact.status == "available"]
    assert len(available) == 1
    assert available[0].sha256 == sha256_bytes(pdf)


def test_failed_download_does_not_stop_other_papers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    state = _state_with_papers(
        tmp_path,
        [
            Paper(id="bad", title="Bad", authors=[], abstract="", year=2025, pdf_url="https://x/bad.pdf"),
            Paper(id="good", title="Good", authors=[], abstract="", year=2026, pdf_url="https://x/good.pdf"),
        ],
    )
    client = FakeBinaryHttpClient(
        responses={"https://x/good.pdf": (b"%PDF-1.4\ngood", {"content-type": "application/pdf"})},
        failures={"https://x/bad.pdf": RuntimeError("timeout")},
    )

    artifacts = PdfDownloader(http_client=client).download_for_state(state)

    by_paper = {artifact.paper_id: artifact.status for artifact in artifacts}
    assert by_paper == {"bad": "failed", "good": "available"}
    assert len(state.paper_artifacts) == 2


def test_arxiv_pdf_url_inference_is_stable() -> None:
    paper = Paper(id="arxiv-1", title="Paper", authors=[], abstract="", year=2026, arxiv_id="2401.00001v1")

    assert infer_pdf_url(paper) == "https://arxiv.org/pdf/2401.00001v1"


def test_download_pdfs_cli_writes_artifacts_without_network(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("pdf cli fixture")
    state.papers.append(Paper(id="p1", title="Paper", authors=[], abstract="", year=2026, pdf_url="https://x/p1.pdf"))
    manager.save_run(state)

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "download-pdfs", "--run-id", state.run_id],
        cwd=tmp_path,
        env={
            **os.environ,
            "GAPFORGE_DISABLE_NETWORK": "1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    artifacts = json.loads((Path(state.run_dir) / "paper_artifacts.json").read_text(encoding="utf-8"))
    assert artifacts[0]["status"] == "skipped"
    coverage = (Path(state.run_dir) / "full_text_coverage.md").read_text(encoding="utf-8")
    assert "Network disabled" in coverage


def _state_with_papers(tmp_path: Path, papers: list[Paper]) -> ResearchRunState:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("pdf fixture")
    state.papers = papers
    manager.save_run(state)
    return state
