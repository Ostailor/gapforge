from __future__ import annotations

from pathlib import Path

from gapforge import api
from gapforge.config import GapForgeConfig
from gapforge.models import PaperNote
from gapforge.state import ResearchStateManager


def test_api_create_project_and_run(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    project = api.create_project("Notebook Project", description="scripted workflow", config=config)
    state = api.create_run("low false positive collusion detection", project_id=project.project.id, config=config)

    loaded_project = api.get_project(project.project.id, config=config)
    assert state.run_id in loaded_project.run_ids
    assert api.get_state(state.run_id, config=config).topic.text == "low false positive collusion detection"


def test_api_add_pdf_and_parse_fulltext(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("pdf api workflow", config=config)
    pdf = tmp_path / "api-paper.pdf"
    pdf.write_bytes(_tiny_pdf("Abstract API paper. Results mention deployment false positives."))

    added = api.add_pdf(state.run_id, pdf, title="API PDF Paper", authors=["Ada"], year=2026, config=config)
    parsed = api.parse_fulltext(state.run_id, paper_id=added.paper.id, config=config)

    assert added.artifact.status == "available"
    assert parsed.sections
    assert parsed.sections[0].paper_id == added.paper.id


def test_api_mine_gaps_and_build_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("deployment limitation mining", config=config)
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(_tiny_pdf("Abstract A."))
    pdf_b.write_bytes(_tiny_pdf("Abstract B."))
    paper_a = api.add_pdf(state.run_id, pdf_a, title="Deployment A", config=config).paper
    paper_b = api.add_pdf(state.run_id, pdf_b, title="Deployment B", config=config).paper

    state = api.get_state(state.run_id, config=config)
    state.paper_notes.extend(
        [
            PaperNote(
                paper_id=paper_a.id,
                one_sentence_summary="A",
                stated_limitations=["Deployment false-positive behavior remains unresolved."],
            ),
            PaperNote(
                paper_id=paper_b.id,
                one_sentence_summary="B",
                stated_limitations=["Real-world deployment validation is missing."],
            ),
        ]
    )
    ResearchStateManager(config).save_run(state)

    mined = api.mine_gaps(state.run_id, config=config)
    manifest = api.build_index(run_id=state.run_id, config=config)

    assert mined.gaps
    assert any(gap.type == "deployment gap" for gap in mined.gaps)
    assert manifest.document_count > 0


def test_api_export_report_without_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("report api workflow", config=config)

    result = api.export_report(state.run_id, config=config)

    assert result.path == Path(state.run_dir) / "final_report.md"
    assert result.path.exists()
    assert "GapForge Final Research Report" in result.path.read_text(encoding="utf-8")


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
