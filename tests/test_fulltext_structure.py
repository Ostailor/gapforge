from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.citations import CitationGraphBuilder
from gapforge.config import GapForgeConfig
from gapforge.fulltext.equations import parse_equations
from gapforge.fulltext.ocr import record_ocr_recommendations
from gapforge.fulltext.references import parse_reference, split_references
from gapforge.fulltext.structure import FullTextStructureParser
from gapforge.models import OcrAttemptRecord, Paper, PaperArtifact, PaperSection, Provenance
from gapforge.state import ResearchStateManager, utc_now_iso


def test_reference_splitting_and_identifier_extraction() -> None:
    text = """
    [1] A. Researcher. "False-positive calibrated collusion detector benchmark." ICML. 2024. doi:10.1234/ABC.DEF
    [2] B. Writer. Related graph monitoring. arXiv:2401.12345. 2023.
    """

    refs = split_references(text)
    first = parse_reference("p1", refs[0], index=1)
    second = parse_reference("p1", refs[1], index=2)

    assert len(refs) == 2
    assert first.doi.lower() == "10.1234/abc.def"
    assert first.parsed_title == "False-positive calibrated collusion detector benchmark"
    assert second.arxiv_id == "2401.12345"
    assert second.parsed_year == 2023


def test_table_caption_and_equation_extraction(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("structure parsing")
    state.paper_sections = [
        PaperSection(
            id="sec-results",
            paper_id="p1",
            title="Results",
            section_type="results",
            text=(
                "Table 1: Benchmark results at fixed false-positive budgets.\n"
                "Method  FPR  Recall\n"
                "Base    0.01 0.40\n"
                "Ours    0.01 0.55\n"
                "Figure 2: Recall changes under deployment shift.\n"
                "score = \\frac{TP}{TP + FP}\n"
            ),
            page_start=5,
            page_end=5,
        )
    ]

    FullTextStructureParser().parse_all(state)

    assert state.tables
    assert state.tables[0].caption == "Benchmark results at fixed false-positive budgets."
    assert any(caption.caption_type == "figure" for caption in state.captions)
    assert any("score =" in equation.text for equation in state.equations)


def test_equation_detection() -> None:
    section = PaperSection(id="sec-method", paper_id="p1", title="Method", text="loss = y_i - \\sum_j w_j x_j", page_start=3)

    equations = parse_equations(section)

    assert equations
    assert equations[0].locator == "p1:eq:1:p3"


def test_low_text_density_flags_ocr_recommended_and_fake_provider_can_attempt(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("ocr")
    state.paper_artifacts = [PaperArtifact(id="artifact-1", paper_id="p1", artifact_type="pdf", status="available", local_path="scan.pdf")]
    state.paper_sections = [PaperSection(id="sec-empty", paper_id="p1", text="", page_start=1)]

    record_ocr_recommendations(state)
    assert state.ocr_attempts[0].status == "unavailable"

    state.ocr_attempts = []
    record_ocr_recommendations(state, provider=FakeOcrProvider())
    assert state.ocr_attempts[0].status == "attempted"


def test_reference_records_feed_citation_graph(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("citation graph")
    state.papers = [
        Paper(id="p1", title="Citing paper", authors=[], abstract="", year=2025),
        Paper(id="p2", title="False-positive calibrated collusion detector benchmark", authors=[], abstract="", year=2024),
    ]
    state.paper_sections = [
        PaperSection(
            id="refs",
            paper_id="p1",
            title="References",
            normalized_title="references",
            section_type="unknown",
            text='[1] A. Researcher. "False-positive calibrated collusion detector benchmark." ICML. 2024.',
        )
    ]

    FullTextStructureParser().parse_references(state)
    graph = CitationGraphBuilder().build(state)

    assert state.references[0].resolved_paper_id == "p2"
    assert any(edge.source_paper_id == "p1" and edge.target_paper_id == "p2" for edge in graph.edges)


def test_parse_structure_cli_writes_artifacts(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("structure cli")
    state.paper_sections = [
        PaperSection(
            id="refs",
            paper_id="p1",
            title="References",
            normalized_title="references",
            text="[1] A. Researcher. Example paper. 2024. doi:10.1000/example",
        )
    ]
    manager.save_run(state)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "parse-structure", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((Path(state.run_dir) / "references.json").read_text(encoding="utf-8"))
    assert (Path(state.run_dir) / "ocr_status.md").exists()


class FakeOcrProvider:
    def attempt(self, artifact: PaperArtifact, pages: list[int]) -> OcrAttemptRecord:
        return OcrAttemptRecord(
            id=f"ocr-{artifact.paper_id}-{artifact.id}",
            paper_id=artifact.paper_id,
            artifact_id=artifact.id,
            pages_attempted=pages,
            status="attempted",
            warnings=["fake OCR provider used in tests"],
            provenance=Provenance(
                created_by_skill="fake-ocr",
                source_ids=[artifact.paper_id, artifact.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Fake OCR provider used for offline tests.",
            ),
        )
