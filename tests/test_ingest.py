from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ingest import ManualIngestor
from gapforge.state import ResearchStateManager


def test_add_manual_paper_writes_to_state(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("manual fixture")

    paper = ManualIngestor(manager.config).add_paper(
        state,
        title="Known Collusion Detection Paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        year=2024,
        doi="10.1234/example",
        pdf_url="https://example.test/paper.pdf",
    )
    manager.save_run(state)

    assert paper.id == "doi:10.1234/example"
    payload = json.loads((Path(state.run_dir) / "papers.json").read_text(encoding="utf-8"))
    assert payload[0]["title"] == "Known Collusion Detection Paper"
    assert payload[0]["authors"] == ["Ada Lovelace", "Grace Hopper"]


def test_add_local_pdf_creates_artifact_without_network(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("pdf ingest fixture")
    pdf = tmp_path / "known.pdf"
    pdf.write_bytes(_tiny_pdf("Abstract Manual paper text."))

    paper, artifact = ManualIngestor(manager.config).add_pdf(
        state,
        pdf,
        title="Manual PDF Paper",
        authors=["Ada Lovelace"],
        year=2024,
    )
    manager.save_run(state)

    assert paper in state.papers
    assert artifact.status == "available"
    assert (Path(state.run_dir) / artifact.local_path).exists()
    artifacts = json.loads((Path(state.run_dir) / "paper_artifacts.json").read_text(encoding="utf-8"))
    assert artifacts[0]["paper_id"] == paper.id


def test_duplicate_doi_merges_with_existing_manual_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("doi fixture")
    ingestor = ManualIngestor(manager.config)
    ingestor.add_paper(state, title="Complete Manual DOI Title", authors=["Ada"], year=2024, doi="10.1234/example")

    ingestor.add_doi(state, "https://doi.org/10.1234/example")

    assert len(state.papers) == 1
    assert state.papers[0].title == "Complete Manual DOI Title"
    assert state.papers[0].doi == "10.1234/example"
    assert state.papers[0].authors == ["Ada"]


def test_add_arxiv_offline_records_partial_paper(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("arxiv fixture")

    paper = ManualIngestor(manager.config).add_arxiv(state, "2401.00001v1")

    assert paper.arxiv_id == "2401.00001v1"
    assert paper.pdf_url == "https://arxiv.org/pdf/2401.00001v1"
    assert len(state.papers) == 1
    assert state.source_coverage is not None
    assert any("network disabled" in warning for warning in state.source_coverage.coverage_warnings)


def test_add_pdf_with_parse_flag_creates_sections(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("pdf parse fixture")
    pdf = tmp_path / "parseable.pdf"
    pdf.write_bytes(_tiny_pdf("Abstract Manual paper text. Results show a measurable effect."))

    paper, artifact = ManualIngestor(manager.config).add_pdf(
        state,
        pdf,
        title="Parseable Manual PDF",
        authors=["Ada"],
        year=2025,
        parse=True,
    )
    manager.save_run(state)

    assert artifact.status == "available"
    assert state.paper_sections
    assert state.paper_sections[0].paper_id == paper.id
    assert json.loads((Path(state.run_dir) / "paper_sections.json").read_text(encoding="utf-8"))


def test_add_paper_cli(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("cli manual fixture")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "add-paper",
            "--run-id",
            state.run_id,
            "--title",
            "CLI Manual Paper",
            "--authors",
            "A;B",
            "--year",
            "2024",
        ],
        cwd=tmp_path,
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    papers = json.loads((Path(state.run_dir) / "papers.json").read_text(encoding="utf-8"))
    assert papers[0]["title"] == "CLI Manual Paper"
    assert papers[0]["authors"] == ["A", "B"]


def test_add_url_does_not_claim_peer_review(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("url fixture")

    paper = ManualIngestor(manager.config).add_url(state, "https://example.test/preprint-note")

    assert paper.source == "manual-url"
    assert paper.raw_metadata["peer_review_status"] == "unknown"


def _tiny_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n",
        b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        b"5 0 obj<< /Length " + str(len(stream)).encode() + b" >>stream\n" + stream + b"\nendstream\nendobj\n",
    ]
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        body += f"{offset:010d} 00000 n \n".encode()
    body += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body
