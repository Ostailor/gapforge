from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Claim, Paper, PaperSection, PaperTriageDecision, PaperTriageResult
from gapforge.orchestrator import Orchestrator
from gapforge.skills.deep_reading import DeepReading


def result_paper() -> Paper:
    return Paper(
        id="paper-result",
        title="Calibrated graph collusion detection",
        authors=["Ada Lovelace"],
        abstract=(
            "This paper proposes a calibrated graph neural detector for collusion detection. "
            "We demonstrate reduced false positive rate on a benchmark dataset. "
            "Future work should test deployment shift."
        ),
        year=2026,
        venue="KDD",
        source="fixture",
        url="https://example.test/result",
        keywords=["graph", "collusion", "calibration"],
    )


def no_result_paper() -> Paper:
    return Paper(
        id="paper-no-result",
        title="Position paper on collusion detection benchmarks",
        authors=["Grace Hopper"],
        abstract="This paper discusses benchmark design and dataset assumptions for collusion detection.",
        year=2025,
        venue="Workshop",
        source="fixture",
        url="https://example.test/no-result",
        keywords=["benchmark", "dataset"],
    )


def test_deep_reading_marks_abstract_only_and_extracts_supported_claims() -> None:
    note = DeepReading().read_paper("low false positive collusion detection", result_paper())

    assert note.source_basis == "metadata/abstract only"
    assert note.confidence == "medium"
    assert note.core_claims
    assert note.main_results
    assert any("reduced false positive rate" in result.lower() for result in note.main_results)


def test_deep_reading_does_not_fabricate_results_without_result_text() -> None:
    note = DeepReading().read_paper("low false positive collusion detection", no_result_paper())

    assert note.main_results == []
    assert "No concrete result statement is visible in the available text." in note.unstated_limitations
    assert note.confidence != "high"


def test_deep_reading_run_adds_claims_and_writes_artifacts(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = [result_paper(), no_result_paper()]
    state.paper_triage = PaperTriageResult(
        topic=state.topic.text,
        decisions=[
            PaperTriageDecision(
                paper_id="paper-result",
                title=result_paper().title,
                tier="Tier 1",
                score=90,
                recommended_reading_depth="read full paper deeply",
            ),
            PaperTriageDecision(
                paper_id="paper-no-result",
                title=no_result_paper().title,
                tier="Tier 2",
                score=55,
                recommended_reading_depth="read method, results, and limitations",
            ),
        ],
    )
    orchestrator.state_store.save_run(state)

    read_state = orchestrator.read(run_id=state.run_id, tier=1)

    run_dir = Path(read_state.run_dir)
    assert (run_dir / "paper_notes.json").exists()
    assert (run_dir / "paper_notes.md").exists()
    assert len(read_state.paper_notes) == 1
    assert any(claim.created_by_skill == "deep-reading" and claim.status == "supported" for claim in read_state.claims)
    payload = json.loads((run_dir / "paper_notes.json").read_text(encoding="utf-8"))
    assert payload[0]["source_basis"] == "metadata/abstract only"


def test_deep_reading_uses_full_text_sections_and_saves_evidence_spans(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    paper = result_paper()
    state.papers = [paper]
    state.paper_sections = [
        _section(paper.id, "s-abstract", "Abstract", "abstract", 1, "This paper proposes calibrated collusion detection."),
        _section(paper.id, "s-methods", "Methods", "method", 2, "We use graph neural calibration with abstention."),
        _section(
            paper.id,
            "s-results",
            "Results",
            "results",
            5,
            "Results show reduced false positive rate on a benchmark dataset using precision and recall.",
        ),
        _section(paper.id, "s-limitations", "Limitations", "limitations", 7, "Limitations include deployment shift."),
    ]
    orchestrator.state_store.save_run(state)

    read_state = orchestrator.read(run_id=state.run_id, paper_id=paper.id)

    note = read_state.paper_notes[0]
    assert note.source_basis == "full text"
    assert note.sections_used
    assert "full text" not in note.missing_sections
    assert any("reduced false positive rate" in result.lower() for result in note.main_results)
    assert read_state.evidence_spans
    assert any(span.evidence_type == "result" and span.locator.endswith(":p5") for span in read_state.evidence_spans)
    assert any(evidence.locator.endswith(":p5") for evidence in note.quotes_or_evidence_snippets)
    assert any(claim.supporting_evidence and claim.supporting_evidence[0].locator.startswith(paper.id) for claim in read_state.claims)
    markdown = (Path(read_state.run_dir) / "paper_notes.md").read_text(encoding="utf-8")
    assert "Source basis: full text" in markdown
    assert "Sections used:" in markdown
    assert "Evidence Snippets" in markdown


def test_full_text_reading_does_not_extract_results_without_result_section(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    paper = result_paper()
    state.papers = [paper]
    state.paper_sections = [
        _section(paper.id, "s-abstract", "Abstract", "abstract", 1, "This paper proposes calibrated collusion detection."),
        _section(paper.id, "s-methods", "Methods", "method", 2, "We use graph neural calibration."),
    ]
    orchestrator.state_store.save_run(state)

    read_state = orchestrator.read(run_id=state.run_id, paper_id=paper.id)

    note = read_state.paper_notes[0]
    assert note.source_basis == "full text"
    assert note.main_results == []
    assert "experiments/evaluation/results" in note.missing_sections
    assert not any(span.evidence_type == "result" for span in read_state.evidence_spans)


def test_fulltext_only_skips_abstract_only_papers(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = [result_paper()]
    orchestrator.state_store.save_run(state)

    read_state = orchestrator.read(run_id=state.run_id, fulltext_only=True)

    assert read_state.paper_notes == []


def test_validation_catches_high_confidence_full_text_claim_without_span(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    paper = result_paper()
    state.papers = [paper]
    state.paper_sections = [_section(paper.id, "s-results", "Results", "results", 5, "Results show reduced false positives.")]
    state.claims = [
        Claim(
            id="claim-fulltext",
            text="A high-confidence result claim without a span.",
            type="result",
            status="supported",
            confidence="high",
            source_paper_ids=[paper.id],
            created_by_skill="test",
        )
    ]

    validation = orchestrator.state_store.validate_state(state)

    assert not validation.ok
    assert any(issue.code == "high-confidence-full-text-claim-without-evidence-span" for issue in validation.issues)


def test_read_cli_by_paper_id(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = [result_paper(), no_result_paper()]
    orchestrator.state_store.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "read", "--run-id", state.run_id, "--paper-id", "paper-no-result"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "paper_notes.md" in result.stdout
    notes = json.loads((Path(state.run_dir) / "paper_notes.json").read_text(encoding="utf-8"))
    assert [note["paper_id"] for note in notes] == ["paper-no-result"]
    papers = json.loads((Path(state.run_dir) / "papers.json").read_text(encoding="utf-8"))
    assert {paper["id"] for paper in papers} == {"paper-result", "paper-no-result"}


def _section(paper_id: str, section_id: str, title: str, section_type: str, page: int, text: str) -> PaperSection:
    return PaperSection(
        id=section_id,
        paper_id=paper_id,
        title=title,
        normalized_title=title.lower(),
        section_type=section_type,
        text=text,
        page_start=page,
        page_end=page,
        char_start=0,
        char_end=len(text),
        confidence="medium",
    )
