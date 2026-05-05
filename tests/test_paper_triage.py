from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import CrossDomainTransferCandidate, Paper, PaperSection
from gapforge.orchestrator import Orchestrator
from gapforge.skills.paper_triage import PaperTriage
from gapforge.sources.ranking_v2 import rank_papers_v2


def triage_fixture_papers() -> list[Paper]:
    return [
        Paper(
            id="direct-recent",
            title="Low false positive collusion detection with calibrated graph models",
            authors=["A"],
            abstract=(
                "A recent benchmark dataset study for low false positive collusion detection. It reports false positive rate, "
                "calibration error, limitations, and future work."
            ),
            year=2026,
            venue="KDD",
            source="arXiv",
            citation_count=25,
            keywords=["collusion", "calibration", "benchmark"],
        ),
        Paper(
            id="weak-old",
            title="General social network visualization",
            authors=["B"],
            abstract="This old paper studies generic visualization of online communities.",
            year=2012,
            venue="Workshop",
            source="Crossref",
            citation_count=5,
            keywords=["visualization"],
        ),
        Paper(
            id="semantic-method",
            title="Graph anomaly detection benchmark for coordinated abuse",
            authors=["C"],
            abstract="Graph anomaly detection benchmark with datasets, precision, recall, and open problem discussion.",
            year=2024,
            venue="WWW",
            source="Semantic Scholar",
            citation_count=120,
            keywords=["graph", "anomaly", "benchmark"],
        ),
        Paper(
            id="crossref-method",
            title="Dataset validity for fraud and collusion detection",
            authors=["D"],
            abstract="Evaluation validity, labels, datasets, and ground truth assumptions for fraud detection.",
            year=2023,
            venue="NeurIPS",
            source="Crossref",
            citation_count=60,
            keywords=["dataset", "fraud", "collusion"],
        ),
        Paper(
            id="arxiv-extra",
            title="Collusion detection using embeddings",
            authors=["E"],
            abstract="Representation learning method for collusion detection with benchmark evaluation.",
            year=2025,
            venue="arXiv",
            source="arXiv",
            citation_count=2,
            keywords=["embedding", "collusion"],
        ),
        Paper(
            id="classic-survey",
            title="A survey of collusion and anomaly detection",
            authors=["F"],
            abstract="A systematic review and survey of collusion detection, anomaly detection, benchmarks, and evaluation.",
            year=2015,
            venue="JMLR",
            source="DBLP",
            citation_count=700,
            keywords=["survey", "collusion", "anomaly"],
        ),
        Paper(
            id="adjacent-medicine",
            title="Specificity calibrated screening with confirmatory diagnosis",
            authors=["G"],
            abstract="Medicine screening uses specificity, threshold triage, and confirmatory diagnosis to reduce false positives.",
            year=2024,
            venue="Nature Medicine",
            source="Semantic Scholar",
            citation_count=80,
            keywords=["screening", "specificity"],
        ),
    ]


def test_triage_prioritizes_direct_recent_paper_over_weak_old_paper() -> None:
    skill = PaperTriage(max_tier1=2)
    result = skill.triage("low false positive collusion detection", triage_fixture_papers(), max_tier1=2)
    by_id = {decision.paper_id: decision for decision in result.decisions}

    assert by_id["direct-recent"].score > by_id["weak-old"].score
    assert by_id["direct-recent"].tier == "Tier 1"
    assert by_id["weak-old"].tier in {"Tier 3", "Tier 4"}
    assert by_id["direct-recent"].paper_role in {"frontier", "benchmark"}


def test_triage_tier_assignment_and_source_diversity() -> None:
    skill = PaperTriage(max_tier1=3)
    result = skill.triage("low false positive collusion detection", triage_fixture_papers(), max_tier1=3)
    tier1 = [decision for decision in result.decisions if decision.tier == "Tier 1"]
    sources = {next(paper.source for paper in triage_fixture_papers() if paper.id == decision.paper_id) for decision in tier1}

    assert len(tier1) >= 2
    assert len(sources) >= 2
    assert result.tier_counts["Tier 1"] == len(tier1)


def test_seminal_survey_paper_is_not_discarded_solely_because_old() -> None:
    skill = PaperTriage(max_tier1=4)
    result = skill.triage("low false positive collusion detection", triage_fixture_papers(), max_tier1=4)
    by_id = {decision.paper_id: decision for decision in result.decisions}

    assert by_id["classic-survey"].paper_role == "survey"
    assert by_id["classic-survey"].tier in {"Tier 1", "Tier 2"}
    assert by_id["classic-survey"].score > by_id["weak-old"].score


def test_ranking_full_text_boost_does_not_dominate_topic_relevance(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    state.paper_sections = [PaperSection(id="weak-fulltext", paper_id="weak-old", text="Full text exists.", section_type="method")]

    ranking = rank_papers_v2(state.topic.text, state.papers, state=state)
    ranks = {decision.paper_id: decision.rank for decision in ranking.decisions}

    assert ranks["direct-recent"] < ranks["weak-old"]
    assert next(decision for decision in ranking.decisions if decision.paper_id == "weak-old").full_text_score == 1.0


def test_adjacent_field_papers_are_triaged_separately(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    state.cross_domain_transfers = [
        CrossDomainTransferCandidate(
            id="transfer-med",
            target_gap_id="gap-1",
            source_field="medicine",
            source_paper_ids=["adjacent-medicine"],
            source_concept="screening specificity",
            status="promoted",
            confidence="medium",
        )
    ]
    orchestrator.state_store.save_run(state)

    triaged = orchestrator.triage(run_id=state.run_id, max_tier1=4)
    by_id = {decision.paper_id: decision for decision in triaged.paper_triage.decisions}

    assert by_id["adjacent-medicine"].paper_role == "adjacent_field"
    assert by_id["adjacent-medicine"].important_for_cross_domain_transfer
    assert "adjacent-field" in by_id["adjacent-medicine"].recommended_reading_depth


def test_rank_papers_cli_writes_artifact(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    orchestrator.state_store.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "rank-papers", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "paper_ranking.md" in result.stdout
    assert (Path(state.run_dir) / "paper_ranking.json").exists()


def test_triage_writes_markdown_and_json_artifacts(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    orchestrator.state_store.save_run(state)

    triaged = orchestrator.triage(run_id=state.run_id, max_tier1=2)

    run_dir = Path(triaged.run_dir)
    assert (run_dir / "paper_triage.json").exists()
    assert (run_dir / "paper_triage.md").exists()
    assert (run_dir / "paper_ranking.json").exists()
    assert (run_dir / "paper_ranking.md").exists()
    markdown = (run_dir / "paper_triage.md").read_text(encoding="utf-8")
    payload = json.loads((run_dir / "paper_triage.json").read_text(encoding="utf-8"))
    assert "Tier 1" in markdown
    assert "Role:" in markdown
    assert payload["decisions"]
    assert triaged.paper_notes


def test_triage_adds_claim_for_tier1_set_only(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    orchestrator.state_store.save_run(state)

    triaged = orchestrator.triage(run_id=state.run_id, max_tier1=2)
    triage_claims = [claim for claim in triaged.claims if claim.created_by_skill == "paper-triage"]

    assert len(triage_claims) == 1
    assert "deserve deep reading" in triage_claims[0].text
    assert len(triage_claims[0].source_paper_ids) <= 2


def test_cli_triage_by_topic_and_run_id(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = triage_fixture_papers()
    orchestrator.state_store.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    by_run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "triage", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    by_topic = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "triage", "low false positive collusion detection", "--max-tier1", "2"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert by_run.returncode == 0, by_run.stderr
    assert by_topic.returncode == 0, by_topic.stderr
    assert "paper_triage.md" in by_run.stdout
    assert "paper_triage.md" in by_topic.stdout
