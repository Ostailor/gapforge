from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.claim_ledger import ClaimLedger
from gapforge.config import GapForgeConfig
from gapforge.models import Cluster, EvidenceSpan, FieldMap, Paper, PaperNote, PaperSection, SearchQueryRecord, SourceCoverageReport
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
        Paper(
            id="p5",
            title="Deployment benchmark with false-positive controls",
            authors=[],
            abstract="A deployed benchmark reports false-positive rate and specificity on real-world alerts.",
            year=2025,
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
            source_basis="full text",
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
            source_basis="full text",
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
        PaperNote(
            paper_id="p5",
            citation_key="p5",
            one_sentence_summary="Deployment benchmark note.",
            datasets=["real-world alerts"],
            metrics=["false-positive rate", "specificity"],
            assumptions=[],
            stated_limitations=["external validity remains limited to one deployment"],
            main_results=["Reports false-positive rate under deployed alert review."],
            confidence="medium",
            source_basis="full text",
        ),
    ]
    state.paper_sections = [
        PaperSection(
            id="p1-limitations",
            paper_id="p1",
            title="Limitations",
            section_type="limitations",
            text="Future work should test deployment shift and false-positive behavior.",
            page_start=7,
            page_end=7,
            confidence="high",
        ),
        PaperSection(
            id="p2-limitations",
            paper_id="p2",
            title="Limitations",
            section_type="limitations",
            text="Large-scale deployment scalability remains a challenge.",
            page_start=8,
            page_end=8,
            confidence="high",
        ),
        PaperSection(
            id="p5-results",
            paper_id="p5",
            title="Results",
            section_type="results",
            text="The deployed benchmark reports false-positive rate and specificity on real-world alerts.",
            page_start=5,
            page_end=5,
            confidence="high",
        ),
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-p1-limitation",
            paper_id="p1",
            section_id="p1-limitations",
            quote="Future work should test deployment shift and false-positive behavior.",
            locator="p1:Limitations:p7",
            evidence_type="limitation",
            confidence="high",
        ),
        EvidenceSpan(
            id="span-p2-limitation",
            paper_id="p2",
            section_id="p2-limitations",
            quote="Large-scale deployment scalability remains a challenge.",
            locator="p2:Limitations:p8",
            evidence_type="limitation",
            confidence="high",
        ),
    ]
    state.search_queries = [
        SearchQueryRecord(
            id="query-analogy-medical-screening",
            query="medical screening false positive abstention collusion detection",
            source_names=["fixture"],
            purpose="analogy",
            max_results=5,
            result_paper_ids=["p1", "p2"],
        ),
        SearchQueryRecord(
            id="query-novelty-counter",
            query="low false positive collusion detection benchmark prior work",
            source_names=["fixture"],
            purpose="novelty",
            max_results=5,
            result_paper_ids=["p1", "p2", "p3", "p5"],
        ),
    ]
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        query_records=state.search_queries,
        papers_by_source={"fixture": 5},
        papers_with_full_text=["p1", "p2", "p5"],
        papers_abstract_only=["p3", "p4"],
        confidence="medium",
    )
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
    assert (run_dir / "gap_evidence_matrix.json").exists()
    assert (run_dir / "gap_evidence_matrix.md").exists()
    assert "Evidence Matrix" in markdown


def test_repeated_limitations_create_evidence_backed_stronger_gap(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)
    deployment_gap = next(gap for gap in mined.gaps if gap.title == "Repeated deployment limitations")
    matrix = next(matrix for matrix in mined.gap_evidence_matrices if matrix.gap_id == deployment_gap.id)

    assert deployment_gap.confidence in {"medium", "high"}
    assert matrix.repeated_limitation_count >= 2
    assert {"p1", "p2"} <= set(matrix.papers_supporting)


def test_counterevidence_lowers_gap_confidence(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)
    measurement_gap = next(gap for gap in mined.gaps if gap.title == "False-positive measurement is missing or inconsistent")
    matrix = next(matrix for matrix in mined.gap_evidence_matrices if matrix.gap_id == measurement_gap.id)

    assert "p5" in matrix.papers_countering
    assert measurement_gap.confidence == "low"
    assert "Potential counterevidence papers" in measurement_gap.risk_that_gap_is_fake


def test_abstract_only_evidence_cannot_create_high_confidence_gap(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)
    state.paper_sections = []
    state.evidence_spans = []
    for note in state.paper_notes:
        note.source_basis = "metadata/abstract only"
    orchestrator.state_store.save_run(state)

    mined = orchestrator.mine_gaps(run_id=state.run_id)

    assert all(gap.confidence != "high" for gap in mined.gaps)


def test_missing_full_text_lowers_confidence(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        query_records=state.search_queries,
        papers_by_source={"fixture": 5},
        papers_with_full_text=[],
        papers_abstract_only=[paper.id for paper in state.papers],
        confidence="low",
    )
    orchestrator.state_store.save_run(state)

    mined = orchestrator.mine_gaps(run_id=state.run_id)

    assert all(gap.confidence != "high" for gap in mined.gaps)
    assert any(gap.title == "Abstract-only evidence limits gap certainty" for gap in mined.gaps)


def test_evidence_matrix_links_to_span_locators(tmp_path: Path) -> None:
    orchestrator, state = gap_fixture_state(tmp_path)

    mined = orchestrator.mine_gaps(run_id=state.run_id)
    matrix_rows = [row for matrix in mined.gap_evidence_matrices for row in matrix.evidence_rows]

    assert any(row.evidence_span_id == "span-p1-limitation" for row in matrix_rows)
    assert any(row.locator == "p1:Limitations:p7" for row in matrix_rows)


def test_mine_gaps_cli(tmp_path: Path) -> None:
    _, state = gap_fixture_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "mine-gaps",
            "--run-id",
            state.run_id,
            "--min-confidence",
            "medium",
            "--include-low-confidence",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "gaps.md" in result.stdout
