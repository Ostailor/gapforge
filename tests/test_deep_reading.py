from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, PaperTriageDecision, PaperTriageResult
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
