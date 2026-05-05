from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.fulltext.pdf_parser import FullTextParser, ParsedPage, PdfTextExtractor
from gapforge.fulltext.section_types import classify_section_title
from gapforge.fulltext.sectionizer import Sectionizer, create_evidence_span_from_quote
from gapforge.models import Paper, PaperArtifact
from gapforge.state import ResearchStateManager


def test_sectionizer_detects_common_sections_and_pages() -> None:
    pages = [
        ParsedPage(
            paper_id="p1",
            artifact_id="a1",
            page_number=1,
            text="Abstract\nWe study low false positives.\nIntroduction\nThe problem matters.",
        ),
        ParsedPage(
            paper_id="p1",
            artifact_id="a1",
            page_number=2,
            text="Methods\nWe calibrate detectors.\nResults\nFalse positives fall.",
        ),
        ParsedPage(
            paper_id="p1",
            artifact_id="a1",
            page_number=3,
            text="Limitations\nSmall benchmark only.\nConclusion\nMore work remains.",
        ),
    ]

    sections = Sectionizer().sectionize("p1", pages)

    assert [section.section_type for section in sections] == [
        "abstract",
        "introduction",
        "method",
        "results",
        "limitations",
        "conclusion",
    ]
    assert sections[0].page_start == 1
    assert sections[3].page_start == 2
    assert sections[-1].page_end == 3
    assert "False positives fall" in sections[3].text


def test_sectionizer_falls_back_when_headings_are_missing() -> None:
    pages = [
        ParsedPage(
            paper_id="p1",
            artifact_id="a1",
            page_number=4,
            text="This paper has extracted text but no obvious academic headings.",
        )
    ]

    sections = Sectionizer().sectionize("p1", pages)

    assert len(sections) == 1
    assert sections[0].section_type == "unknown"
    assert sections[0].page_start == 4
    assert sections[0].confidence == "low"


def test_section_type_classification_normalizes_numbered_headings() -> None:
    assert classify_section_title("2 Related Work") == "related_work"
    assert classify_section_title("III. Methodology") == "method"
    assert classify_section_title("Threats to Validity") == "limitations"
    assert classify_section_title("Appendix A") == "appendix"


def test_evidence_span_helper_locates_quote_in_section() -> None:
    section = Sectionizer().sectionize(
        "p1",
        [ParsedPage(paper_id="p1", artifact_id="a1", page_number=2, text="Results\nFalse positives fall in deployment.")],
    )[0]

    span = create_evidence_span_from_quote(section, "False positives fall", evidence_type="result")

    assert span.paper_id == "p1"
    assert span.section_id == section.id
    assert span.evidence_type == "result"
    assert span.page_start == 2
    assert span.char_start >= section.char_start
    assert span.locator.endswith(":p2")


def test_fulltext_parser_creates_sections_and_text_artifacts(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("parser fixture")
    state.papers = [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026)]
    state.paper_artifacts = [_available_artifact(state.run_dir, "p1")]

    class FakeExtractor:
        def extract(self, run_dir: Path, artifact: PaperArtifact) -> list[ParsedPage]:
            return [
                ParsedPage(
                    paper_id=artifact.paper_id,
                    artifact_id=artifact.id,
                    page_number=1,
                    text="Abstract\nA short abstract.\nMethods\nA deterministic method.",
                )
            ]

    sections = FullTextParser(extractor=FakeExtractor()).parse_for_state(state)  # type: ignore[arg-type]
    manager.save_run(state)

    assert len(sections) == 2
    assert state.source_coverage is not None
    assert state.source_coverage.papers_with_full_text == ["p1"]
    section_files = list((Path(state.run_dir) / "artifacts" / "papers" / "p1" / "sections").glob("*.txt"))
    assert section_files
    assert json.loads((Path(state.run_dir) / "paper_sections.json").read_text(encoding="utf-8"))[0]["paper_id"] == "p1"


def test_malformed_pdf_extraction_returns_warning_page(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    pdf_dir = run_dir / "artifacts" / "papers" / "p1"
    pdf_dir.mkdir(parents=True)
    bad_pdf = pdf_dir / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-not-really-a-valid-pdf")
    artifact = PaperArtifact(id="a1", paper_id="p1", artifact_type="pdf", local_path="artifacts/papers/p1/bad.pdf")

    pages = PdfTextExtractor().extract(run_dir, artifact)

    assert len(pages) == 1
    assert pages[0].text == ""
    assert pages[0].warnings
    assert pages[0].extraction_confidence == "low"


def test_parse_fulltext_cli_records_malformed_pdf_warning(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("cli parser fixture")
    state.papers = [Paper(id="p1", title="Paper", authors=[], abstract="", year=2026)]
    artifact = _available_artifact(state.run_dir, "p1")
    Path(state.run_dir, artifact.local_path).write_bytes(b"%PDF-not-valid")
    state.paper_artifacts = [artifact]
    manager.save_run(state)

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "parse-fulltext", "--run-id", state.run_id],
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
    coverage = (Path(state.run_dir) / "full_text_coverage.md").read_text(encoding="utf-8")
    assert "PDF extraction failed" in coverage


def _available_artifact(run_dir: str, paper_id: str) -> PaperArtifact:
    local_path = f"artifacts/papers/{paper_id}/paper.pdf"
    path = Path(run_dir) / local_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\nfixture")
    return PaperArtifact(
        id=f"{paper_id}-pdf",
        paper_id=paper_id,
        artifact_type="pdf",
        local_path=local_path,
        status="available",
        mime_type="application/pdf",
    )
