from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.orchestrator import Orchestrator
from gapforge.skills.literature_cartographer import LiteratureCartographer
from gapforge.state import ResearchStateManager


def fixture_papers() -> list[Paper]:
    return [
        Paper(
            id="p1",
            title="Graph neural collusion detection in interaction networks",
            authors=["A"],
            abstract="Graph neural methods detect collusion in interaction networks with benchmark datasets.",
            year=2024,
            venue="KDD",
            source="fixture",
            citation_count=50,
            keywords=["graph", "collusion", "benchmark"],
        ),
        Paper(
            id="p2",
            title="Network anomaly detection for coordinated abuse",
            authors=["B"],
            abstract="Anomaly detection on social network edges reports precision and recall on synthetic graphs.",
            year=2023,
            venue="WWW",
            source="fixture",
            citation_count=30,
            keywords=["anomaly", "network"],
        ),
        Paper(
            id="p3",
            title="Benchmark validity for fraud detection datasets",
            authors=["C"],
            abstract="Evaluation validity depends on labels, datasets, metrics, and ground truth assumptions.",
            year=2022,
            venue="NeurIPS",
            source="fixture",
            citation_count=20,
            keywords=["benchmark", "dataset", "metrics"],
        ),
        Paper(
            id="p4",
            title="Human review and explanations for suspicious behavior",
            authors=["D"],
            abstract="Auditable explanations and human review improve trust but rarely measure explanation coverage.",
            year=2025,
            venue="CHI",
            source="fixture",
            citation_count=10,
            keywords=["explanation", "human review"],
        ),
    ]


def test_literature_cartographer_creates_clusters_and_claims(tmp_path: Path) -> None:
    skill = LiteratureCartographer([])
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.papers = fixture_papers()

    mapped = skill.run(state)

    assert mapped.field_map is not None
    cluster_names = {cluster.name for cluster in mapped.field_map.clusters}
    assert "Graph and Network Methods" in cluster_names
    assert "Benchmarks and Evaluation" in cluster_names
    assert mapped.claims
    assert all(claim.status == "uncertain" for claim in mapped.claims if claim.created_by_skill == "literature-cartographer")
    assert mapped.field_map.confidence == "low"


def test_literature_cartographer_extracts_underexplored_areas() -> None:
    skill = LiteratureCartographer([])
    field_map = skill.build_field_map(
        "low false positive collusion detection",
        [
            Paper(
                id="p1",
                title="Graph collusion detection",
                authors=[],
                abstract="Graph detection with accuracy on synthetic datasets.",
                year=2024,
                source="fixture",
            )
        ],
    )

    assert "Explicit false-positive-rate evaluation" in field_map.underexplored_areas
    assert "Calibration under deployment shift" in field_map.underexplored_areas
    assert "Broader source coverage before firm gap claims" in field_map.underexplored_areas


def test_map_writes_field_map_artifacts(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = fixture_papers()
    orchestrator.state_store.save_run(state)

    mapped = orchestrator.map_topic(run_id=state.run_id)

    run_dir = Path(mapped.run_dir)
    assert (run_dir / "field_map.md").exists()
    assert (run_dir / "field_map.json").exists()
    field_map_json = json.loads((run_dir / "field_map.json").read_text(encoding="utf-8"))
    assert field_map_json["clusters"]
    assert "Underexplored Areas" in (run_dir / "field_map.md").read_text(encoding="utf-8")


def test_cli_map_by_run_id(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = fixture_papers()
    orchestrator.state_store.save_run(state)

    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "map", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "field_map.md" in result.stdout
    assert (Path(state.run_dir) / "field_map.md").exists()
