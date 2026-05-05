from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.claim_ledger import ClaimLedger
from gapforge.config import GapForgeConfig
from gapforge.models import Cluster, FieldMap, Paper, PaperNote
from gapforge.orchestrator import Orchestrator
from gapforge.skills.gap_mining import GAP_TYPES


def gap_fixture_state(tmp_path: Path):
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = [
        Paper(
            id="p1",
            title="Synthetic graph detector",
            authors=[],
            abstract="Synthetic graph evaluation reports accuracy.",
            year=2024,
            source="fixture",
        ),
        Paper(
            id="p2",
            title="Scalable collusion detector",
            authors=[],
            abstract="Large-scale detector fails under deployment shift.",
            year=2025,
            source="fixture",
        ),
        Paper(
            id="p3",
            title="Benchmark position",
            authors=[],
            abstract="Benchmark datasets and labels remain underspecified.",
            year=2023,
            source="fixture",
        ),
        Paper(
            id="p4",
            title="Reproducibility study",
            authors=[],
            abstract="Code is unavailable and replication is difficult.",
            year=2022,
            source="fixture",
        ),
    ]
    shared_assumption = "Available datasets or benchmarks are representative of the target problem."
    state.paper_notes = [
        PaperNote(
            paper_id="p1",
            citation_key="p1",
            one_sentence_summary="Synthetic evaluation note.",
            datasets=["synthetic"],
            metrics=["accuracy"],
            assumptions=[shared_assumption],
            stated_limitations=["future work should test deployment shift"],
            unstated_limitations=["False-positive behavior is not visible in the available text."],
            what_it_cannot_answer=["Cannot assess metric validity from available text."],
            confidence="medium",
        ),
        PaperNote(
            paper_id="p2",
            citation_key="p2",
            one_sentence_summary="Scalability note.",
            datasets=["synthetic"],
            metrics=[],
            assumptions=[shared_assumption],
            stated_limitations=["large-scale deployment scalability remains a challenge"],
            unstated_limitations=["No concrete result statement is visible in the available text."],
            what_it_cannot_answer=["Cannot assess dataset realism from available text."],
            confidence="medium",
        ),
        PaperNote(
            paper_id="p3",
            citation_key="p3",
            one_sentence_summary="Benchmark note.",
            datasets=[],
            metrics=[],
            assumptions=[shared_assumption],
            stated_limitations=["benchmark labels and ground truth are open problem", "large-scale reproducibility remains a challenge"],
            unstated_limitations=["False-positive behavior is not visible in the available text."],
            what_it_cannot_answer=["Cannot assess metric validity from available text."],
            confidence="low",
        ),
        PaperNote(
            paper_id="p4",
            citation_key="p4",
            one_sentence_summary="Reproducibility note.",
            datasets=[],
            metrics=[],
            assumptions=[],
            stated_limitations=["code reproducibility and replication are limited"],
            unstated_limitations=["failure cases and negative results are not reported"],
            what_it_cannot_answer=["Cannot assess dataset realism from available text."],
            confidence="low",
        ),
    ]
    state.field_map = FieldMap(
        topic=state.topic.text,
        clusters=[
            Cluster(
                name="Benchmark",
                description="benchmark cluster",
                paper_ids=["p1", "p3"],
                representative_papers=["p1"],
                dominant_methods=["benchmarking"],
                open_questions=["How should false positives be measured?"],
                why_it_matters="evaluation",
            )
        ],
        dominant_methods=["calibration"],
        common_datasets=["synthetic graphs"],
        common_metrics=["accuracy"],
        contradictions=["Synthetic evaluation appears alongside claims that deployment realism matters."],
        adjacent_fields=["medical screening"],
        initial_gap_candidates=["Test whether medical screening abstention transfers to collusion detection"],
    )
    ledger = ClaimLedger()
    claim = ledger.add_claim(
        "Several notes indicate benchmark and dataset limitations.",
        "limitation",
        created_by_skill="fixture",
        source_paper_ids=["p1", "p3"],
    )
    claim.status = "supported"
    state.claims = ledger.claims
    orchestrator.state_store.save_run(state)
    return orchestrator, state


def test_gap_mining_produces_several_supported_gap_candidates(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)

    assert len(mined.gaps) >= 6
    assert all(gap.supporting_paper_ids or gap.explicit_reason for gap in mined.gaps)
    assert all(gap.risk_that_gap_is_fake for gap in mined.gaps)
    assert all(not (gap.confidence == "high" and not gap.supporting_paper_ids and not gap.supporting_claim_ids) for gap in mined.gaps)
    assert any(claim.created_by_skill == "gap-mining" for claim in mined.claims)


def test_gap_mining_covers_major_gap_types(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)
    types = {gap.type for gap in mined.gaps}

    expected = {
        "benchmark gap",
        "evaluation gap",
        "assumption gap",
        "theory gap",
        "deployment gap",
        "negative-result gap",
        "cross-domain gap",
        "measurement gap",
        "reproducibility gap",
        "scalability gap",
    }
    assert expected <= types
    assert types <= GAP_TYPES


def test_gap_mining_writes_markdown_and_json(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)
    run_dir = Path(mined.run_dir)

    assert (run_dir / "gaps.json").exists()
    assert (run_dir / "gaps.md").exists()
    payload = json.loads((run_dir / "gaps.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "gaps.md").read_text(encoding="utf-8")
    assert payload[0]["risk_that_gap_is_fake"]
    assert "Risk That Gap Is Fake" in markdown


def test_mine_gaps_cli(tmp_path: Path) -> None:
    _, state = gap_fixture_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "mine-gaps", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "gaps.md" in result.stdout
