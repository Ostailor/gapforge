from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Claim, Gap, HumanReviewRecord, Paper, RejectedIdea
from gapforge.project_memory import PROJECT_ARTIFACTS, ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_create_project_writes_project_memory_files(tmp_path: Path) -> None:
    manager = ProjectMemoryManager(GapForgeConfig.from_cwd(tmp_path))

    program = manager.create_project("Low FPR Collusion Program")

    project_dir = Path(program.project.root_dir)
    assert project_dir.exists()
    assert project_dir.parent == tmp_path / "projects"
    assert (project_dir / "runs").exists()
    assert (project_dir / "reports").exists()
    for artifact in PROJECT_ARTIFACTS:
        assert (project_dir / artifact).exists(), artifact

    loaded = manager.load_project(program.project.id)
    assert loaded.project.name == "Low FPR Collusion Program"
    assert loaded.corpus_papers == []


def test_gapforge_project_root_env_override(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    custom_root = tmp_path / "custom-projects"
    monkeypatch.setenv("GAPFORGE_PROJECT_ROOT", str(custom_root))

    config = GapForgeConfig.from_cwd(tmp_path)
    ProjectMemoryManager(config).create_project("Custom Root Project")

    assert config.project_root == custom_root
    assert any(custom_root.iterdir())


def test_attach_run_and_sync_deduplicates_corpus_papers(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    run_a = state_manager.create_run("collusion detection")
    run_b = state_manager.create_run("agent collusion")
    run_a.papers.append(
        Paper(
            id="paper-a",
            title="Shared Collusion Detection Benchmark",
            authors=["A"],
            abstract="A benchmark.",
            year=2024,
            doi="10.1234/shared",
            source="fixture",
        )
    )
    run_b.papers.append(
        Paper(
            id="paper-b",
            title="Shared Collusion Detection Benchmark",
            authors=["B"],
            abstract="Same DOI.",
            year=2025,
            doi="10.1234/SHARED",
            source="fixture",
        )
    )
    state_manager.save_run(run_a)
    state_manager.save_run(run_b)
    program = project_manager.create_project("Collusion Memory")

    project_manager.attach_run(program.project.id, run_a.run_id)
    project_manager.attach_run(program.project.id, run_b.run_id)
    synced = project_manager.sync_project_memory(program.project.id)

    assert synced.run_ids == [run_a.run_id, run_b.run_id]
    assert len(synced.corpus_papers) == 1
    corpus = synced.corpus_papers[0]
    assert corpus.canonical_doi == "10.1234/shared"
    assert set(corpus.seen_run_ids) == {run_a.run_id, run_b.run_id}
    assert set(corpus.source_paper_ids) == {"paper-a", "paper-b"}
    assert (Path(synced.project.root_dir) / "runs" / f"{run_a.run_id}.json").exists()


def test_sync_claims_gaps_rejected_ideas_and_human_decisions(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    state = state_manager.create_run("claim memory")
    state.papers.append(Paper(id="paper-1", title="Paper One", authors=[], abstract="Abstract", year=2026, source="fixture"))
    state.claims.append(
        Claim(
            id="claim-1",
            text="False positive rate remains a deployment blocker.",
            type="gap",
            status="supported",
            confidence="medium",
            source_paper_ids=["paper-1"],
        )
    )
    state.gaps.append(
        Gap(
            id="gap-1",
            title="Deployment false-positive gap",
            description="Systems are rarely evaluated for operator workload at low false-positive rates.",
            supporting_paper_ids=["paper-1"],
            confidence="medium",
            novelty_status="unchecked",
        )
    )
    state.rejected_ideas.append(RejectedIdea(id="rej-1", idea="Duplicate benchmark idea", reason="Already covered by prior work."))
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-1",
            object_type="gap",
            object_id="gap-1",
            action="reject",
            note="Not actionable enough.",
            reviewer="researcher",
        )
    )
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-2",
            object_type="gap",
            object_id="gap-1",
            action="lock",
            note="Preserve human rejection.",
            reviewer="researcher",
        )
    )
    state_manager.save_run(state)
    program = project_manager.create_project("Claim Memory")
    project_manager.attach_run(program.project.id, state.run_id)

    synced = project_manager.sync_project_memory(program.project.id)
    records = synced.memory_records

    assert any(record.record_type == "claim" and "False positive" in record.text for record in records)
    assert any(record.record_type == "gap" and "Deployment" in record.text for record in records)
    assert any(record.record_type == "rejected_idea" and record.status == "rejected" for record in records)
    assert any(record.record_type == "decision" and record.status == "rejected" for record in records)
    assert any(record.record_type == "decision" and "lock gap:gap-1" in record.text for record in records)
    direction = synced.research_directions[0]
    assert direction.maturity == "rejected"
    assert direction.readiness_score == 0.0

    reloaded = project_manager.load_project(program.project.id)
    assert any(record.record_type == "decision" for record in reloaded.memory_records)


def test_project_report_renders_summary(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    state = state_manager.create_run("report memory")
    state.papers.append(Paper(id="paper-1", title="Report Paper", authors=[], abstract="", year=2026, source="fixture"))
    state.rejected_ideas.append(RejectedIdea(id="rej-1", idea="Weak idea", reason="Insufficient novelty."))
    state_manager.save_run(state)
    program = project_manager.create_project("Report Project")
    project_manager.attach_run(program.project.id, state.run_id)
    synced = project_manager.sync_project_memory(program.project.id)

    report_path = project_manager.write_project_report(synced)

    text = report_path.read_text(encoding="utf-8")
    assert "GapForge Project Report" in text
    assert "Corpus papers: 1" in text
    assert "Weak idea" in text
    assert (Path(synced.project.root_dir) / "reports" / "project_report.md").exists()


def test_project_cli_commands(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"

    init = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "init-project", "CLI Project"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    project_dir = Path(init.stdout.strip())
    project_id = project_dir.name

    use = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "use-project", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert use.returncode == 0, use.stderr
    assert json.loads((tmp_path / "data" / "active_project.json").read_text(encoding="utf-8"))["project_id"] == project_id

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "list-projects"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert project_id in listed.stdout
    assert "*active*" in listed.stdout

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "init-topic", "cli topic"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    run_id = Path(run.stdout.strip()).name

    attach = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "attach-run", "--project-id", project_id, "--run-id", run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert attach.returncode == 0, attach.stderr

    sync = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "sync-project-memory", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert sync.returncode == 0, sync.stderr

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "project-status", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["run_ids"] == [run_id]

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "project-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert report.returncode == 0, report.stderr
    assert (project_dir / "project_report.md").exists()
