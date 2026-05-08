from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaStore
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso


def test_create_idea_bank_persists_project_artifacts(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)

    bank = store.create_bank(project_id=project_id, root_topic="low false-positive collusion detection")
    ideas_dir = config.project_root / project_id / "ideas"

    assert bank.project_id == project_id
    assert bank.root_topic == "low false-positive collusion detection"
    assert (ideas_dir / "idea_bank.json").exists()
    assert (ideas_dir / "candidates.json").exists()
    assert (ideas_dir / "preference_profiles.json").exists()
    assert (ideas_dir / "evidence_links.json").exists()
    assert (ideas_dir / "feedback_records.json").exists()
    assert (ideas_dir / "novelty_assessments.json").exists()
    assert (ideas_dir / "reviews.json").exists()
    assert (ideas_dir / "mutations.json").exists()
    assert (ideas_dir / "constructive_gaps.json").exists()
    assert (ideas_dir / "transfer_candidates.json").exists()
    assert (ideas_dir / "search_decisions.json").exists()
    assert (ideas_dir / "tournaments.json").exists()
    assert (ideas_dir / "reports" / "idea_bank.md").exists()
    assert "first-class idea bank state" in bank.provenance.reasoning_summary


def test_add_candidate_round_trips_as_auditable_object(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent safety evaluation")

    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-agent-safety",
        title="False-positive aware collusion benchmark",
        summary="Measure collusion detectors under strict false-positive constraints.",
        contribution_type="benchmark",
        core_claim="A benchmark can expose false-positive failure modes hidden by aggregate accuracy.",
        proposed_experiment="Compare detector baselines on benign and collusive multi-agent traces.",
        expected_baselines=["rule detector", "embedding detector"],
        expected_metrics=["false positive rate", "true positive rate"],
        novelty_status="plausible",
        tractability_score=0.8,
        impact_score=0.7,
        evidence_score=0.4,
        reviewer_risk_score=0.3,
        idea_yield_score=0.62,
    )
    state = store.load_state(project_id)

    assert candidate.id in state.idea_bank.candidate_ids if state.idea_bank else False
    assert state.candidates[0].contribution_type == "benchmark"
    assert state.candidates[0].maturity == "candidate"
    assert state.candidates[0].expected_metrics == ["false positive rate", "true positive rate"]
    assert "paper readiness" in state.candidates[0].provenance.reasoning_summary


def test_reject_candidate_remains_in_memory(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent safety evaluation")
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-agent-safety",
        title="Generic agent safety idea",
        summary="Too broad to evaluate.",
    )

    rejected = store.reject_candidate(candidate.id, "Too generic and lacks closest-prior-work boundary.")
    state = store.load_state(project_id)

    assert rejected.maturity == "rejected"
    assert rejected.rejection_reason == "Too generic and lacks closest-prior-work boundary."
    assert any(item.id == candidate.id for item in state.candidates)
    assert state.idea_bank is not None
    assert candidate.id in state.idea_bank.rejected_candidate_ids
    assert "Too generic" in (config.project_root / project_id / "ideas" / "reports" / "idea_bank.md").read_text(encoding="utf-8")


def test_link_evidence_updates_candidate_trace_fields(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent safety evaluation")
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-agent-safety",
        title="Measurement slice",
        summary="Measure a narrow failure slice.",
        contribution_type="measurement",
    )

    support = store.link_evidence(
        idea_id=candidate.id,
        link_type="supports",
        paper_id="paper-support",
        evidence_span_id="span-1",
        claim_id="claim-1",
        note="Shows the failure mode exists.",
    )
    counter = store.link_evidence(
        idea_id=candidate.id,
        link_type="counters",
        paper_id="paper-counter",
        note="May already cover the benchmark setup.",
    )
    state = store.load_state(project_id)
    loaded = next(item for item in state.candidates if item.id == candidate.id)

    assert support.link_type == "supports"
    assert counter.link_type == "counters"
    assert "paper-support" in loaded.supporting_paper_ids
    assert "paper-counter" in loaded.counterevidence_paper_ids
    assert "span-1" in loaded.evidence_span_ids
    assert len(state.evidence_links) == 2


def test_add_human_review_preserves_review_and_candidate_feedback_link(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent safety evaluation")
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-agent-safety",
        title="Tooling candidate",
        summary="Build tooling for evidence audit.",
        contribution_type="tooling",
    )

    review = store.add_review(
        idea_id=candidate.id,
        reviewer="Human Reviewer",
        status="revise",
        novelty_judgment="Needs closer prior-work search.",
        feasibility_judgment="Feasible as a scoped tool.",
        impact_judgment="Useful if tied to release gates.",
        required_fixes=["Add closest-prior-work dossier."],
        notes="Promising but not accepted.",
    )
    state = store.load_state(project_id)
    loaded = next(item for item in state.candidates if item.id == candidate.id)

    assert review.id in loaded.human_feedback_ids
    assert state.reviews[0].reviewer == "Human Reviewer"
    assert loaded.maturity == "candidate"


def test_idea_report_renders_and_writes(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent safety evaluation")
    candidate = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-agent-safety",
        title="Evaluation protocol candidate",
        summary="Define an evaluation protocol.",
        contribution_type="evaluation_protocol",
        expected_baselines=["baseline-a"],
        expected_metrics=["metric-a"],
    )
    store.link_evidence(idea_id=candidate.id, link_type="closest_prior_work", paper_id="paper-prior", note="Closest known setup.")
    store.add_review(idea_id=candidate.id, reviewer="Reviewer", status="uncertain", notes="Needs more evidence.")

    report = store.write_idea_report(candidate.id)
    report_path = config.project_root / project_id / "ideas" / "reports" / f"{candidate.id}.md"

    assert f"# Idea Candidate `{candidate.id}`" in report
    assert "Idea maturity is not paper readiness" in report
    assert "closest_prior_work" in report
    assert "Reviewer" in report
    assert report_path.exists()


def test_idea_cli_create_list_report_review(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "idea-bank-create",
            "--project-id",
            project_id,
            "--root-topic",
            "CLI idea discovery",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    assert json.loads(created.stdout)["root_topic"] == "CLI idea discovery"

    store = IdeaStore(config)
    candidate = store.add_candidate(project_id=project_id, source_topic_id="topic-cli", title="CLI Candidate", summary="CLI test idea.")

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-list", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-report", "--idea-id", candidate.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    review = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "idea-review",
            "--idea-id",
            candidate.id,
            "--reviewer",
            "CLI Reviewer",
            "--status",
            "accepted",
            "--notes",
            "Accepted for continued research, not paper readiness.",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert listed.returncode == 0, listed.stderr
    assert report.returncode == 0, report.stderr
    assert review.returncode == 0, review.stderr
    assert "CLI Candidate" in listed.stdout
    assert f"# Idea Candidate `{candidate.id}`" in report.stdout
    assert json.loads(review.stdout)["reviewer"] == "CLI Reviewer"


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for idea discovery state.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
