from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.claims.contradiction import llm_contradiction_check
from gapforge.claims.project_sync import ProjectClaimGraphManager
from gapforge.config import GapForgeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.models import Claim, Paper, Provenance
from gapforge.orchestrator import Orchestrator
from gapforge.project_memory import ProjectMemoryManager


def test_duplicate_claims_merge(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project, run_id = _project_with_claims(
        config,
        [
            Claim(id="c1", text="The method works at low FPR.", type="result", status="supported", source_paper_ids=["p1"]),
            Claim(id="c2", text="The method works at low FPR", type="result", status="supported", source_paper_ids=["p2"]),
        ],
    )

    graph = ProjectClaimGraphManager(config).build(project.project.id)

    assert run_id in graph.nodes[0].run_ids
    assert len(graph.nodes) == 1
    assert len(graph.nodes[0].linked_claim_ids) == 2
    assert any(edge.relation == "duplicates" for edge in graph.edges)


def test_contradiction_detected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project, _run_id = _project_with_claims(
        config,
        [
            Claim(id="c1", text="The monitor was evaluated at low FPR.", type="result", status="supported"),
            Claim(id="c2", text="The monitor was not evaluated at low FPR.", type="limitation", status="supported"),
        ],
    )

    graph = ProjectClaimGraphManager(config).build(project.project.id)

    assert any(edge.relation == "contradicts" for edge in graph.edges)
    assert graph.unresolved_contradictions


def test_human_resolution_persists(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project, _run_id = _project_with_claims(
        config,
        [
            Claim(id="c1", text="The model works under deployment shift.", type="result"),
            Claim(id="c2", text="The model fails under deployment shift.", type="limitation"),
        ],
    )
    manager = ProjectClaimGraphManager(config)
    graph = manager.build(project.project.id)
    contradicting = next(edge for edge in graph.edges if edge.relation == "contradicts")

    resolved = manager.resolve_contradiction(
        project.project.id,
        contradicting.source_claim_id,
        contradicting.target_claim_id,
        "Claims refer to different datasets.",
    )
    loaded = manager.load(project.project.id)

    assert loaded is not None
    assert any(edge.relation == "refines" for edge in loaded.edges)
    assert len(resolved.unresolved_contradictions) == 0


def test_claim_graph_report_renders(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project, _run_id = _project_with_claims(config, [Claim(id="c1", text="A benchmark requires calibration.", type="method")])

    graph = ProjectClaimGraphManager(config).build(project.project.id)
    report = ProjectClaimGraphManager(config).render(project.project.id)

    assert graph.nodes
    assert "Project Claim Graph" in report
    assert "benchmark requires calibration" in report.lower()
    assert (Path(project.project.root_dir) / "claim_graph.md").exists()


def test_optional_llm_contradiction_path_fake_only() -> None:
    value, reason = llm_contradiction_check(
        "The model requires labels.",
        "The model does not require labels.",
        client=FakeLLMClient(skill_name="claim-contradiction-test"),
    )

    assert value
    assert reason


def test_claim_graph_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project, _run_id = _project_with_claims(config, [Claim(id="c1", text="The approach works.", type="result")])
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    build = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "build-claim-graph", "--project-id", project.project.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    show = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "claim-graph", "--project-id", project.project.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert build.returncode == 0, build.stderr
    assert show.returncode == 0, show.stderr
    assert "Built claim graph" in build.stdout
    assert "Project Claim Graph" in show.stdout


def _project_with_claims(config: GapForgeConfig, claims: list[Claim]):
    orchestrator = Orchestrator(config)
    state = orchestrator.init_topic("claim graph fixture")
    state.papers = [Paper(id="p1", title="Paper One", authors=[], abstract="", year=2025)]
    for claim in claims:
        if not claim.provenance.timestamp:
            claim.provenance = Provenance(created_by_skill="test", source_ids=[claim.id], reasoning_summary="Fixture claim.")
    state.claims = claims
    orchestrator.state_store.save_run(state)
    manager = ProjectMemoryManager(config)
    project = manager.create_project("Claim Graph Project")
    manager.attach_run(project.project.id, state.run_id)
    return project, state.run_id
