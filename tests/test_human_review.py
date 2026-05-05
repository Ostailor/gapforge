from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Claim, Gap, NoveltyAssessment, Paper, PaperNote, ResearchRunState
from gapforge.reporting import write_final_report
from gapforge.review.audit import is_locked, is_rejected
from gapforge.review.edits import HumanReviewEditor
from gapforge.skills.experiment_designer import ExperimentDesigner
from gapforge.skills.gap_mining import GapMining
from gapforge.state import ResearchStateManager


def test_approve_gap_creates_review_record(tmp_path: Path) -> None:
    manager, state = _review_state(tmp_path)

    record = HumanReviewEditor().approve_gap(state, "gap-1", note="Worth prioritizing.")
    manager.save_run(state)

    assert record.action == "approve"
    assert state.human_reviews[0].object_id == "gap-1"
    data = json.loads((Path(state.run_dir) / "human_reviews.json").read_text(encoding="utf-8"))
    assert data[0]["note"] == "Worth prioritizing."
    assert "Worth prioritizing" in (Path(state.run_dir) / "human_reviews.md").read_text(encoding="utf-8")


def test_reject_gap_prevents_experiment_generation(tmp_path: Path) -> None:
    _, state = _review_state(tmp_path)
    HumanReviewEditor().reject_gap(state, "gap-1", reason="Researcher knows this is already solved.")

    ExperimentDesigner().design(state)

    linked_gap_ids = {experiment.linked_gap_ids[0] for experiment in state.experiments}
    assert "gap-1" not in linked_gap_ids
    assert linked_gap_ids == {"gap-2"}
    assert is_rejected(state, "gap", "gap-1")


def test_annotate_claim_persists(tmp_path: Path) -> None:
    manager, state = _review_state(tmp_path)

    HumanReviewEditor().annotate_claim(state, "claim-1", note="Check the full-text wording before reuse.")
    manager.save_run(state)
    loaded = manager.load_run(state.run_id)

    assert "Check the full-text wording" in loaded.claims[0].notes
    assert loaded.human_reviews[0].action == "annotate"


def test_manual_evidence_can_support_claim(tmp_path: Path) -> None:
    _, state = _review_state(tmp_path)

    HumanReviewEditor().add_evidence(
        state,
        "claim-1",
        paper_id="paper-1",
        quote="The paper reports evaluation under a fixed false-positive budget.",
        locator="paper-1:Evaluation:p4",
    )

    claim = state.claims[0]
    assert claim.status == "supported"
    assert claim.supporting_evidence[0].locator == "paper-1:Evaluation:p4"
    assert claim.source_paper_ids == ["paper-1"]


def test_locked_gap_is_not_overwritten_by_rerun_unless_force(tmp_path: Path) -> None:
    _, state = _review_state(tmp_path)
    state.gaps = [
        Gap(
            id="locked-gap",
            title="Human edited gap title",
            explicit_reason="Human curated.",
            risk_that_gap_is_fake="Needs manual check.",
        )
    ]
    HumanReviewEditor().lock_object(state, "gap", "locked-gap", note="Do not overwrite curated wording.")

    GapMining().run(state)

    assert any(gap.id == "locked-gap" and gap.title == "Human edited gap title" for gap in state.gaps)
    assert is_locked(state, "gap", "locked-gap")

    GapMining().run(state, force=True)

    assert all(gap.id != "locked-gap" for gap in state.gaps)


def test_final_report_includes_human_review_summary(tmp_path: Path) -> None:
    _, state = _review_state(tmp_path)
    HumanReviewEditor().reject_gap(state, "gap-1", reason="Not useful after manual prior-work check.")

    path = write_final_report(state)

    report = path.read_text(encoding="utf-8")
    assert "Human Review Summary" in report
    assert "human-rejected-gap-1" in report


def test_human_review_cli_commands(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "run", "low false positive collusion detection"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    run_dir = sorted((tmp_path / "runs").iterdir())[-1]
    gap_id = json.loads((run_dir / "gaps.json").read_text(encoding="utf-8"))[0]["id"]

    approve = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "approve-gap", "--run-id", run_dir.name, "--gap-id", gap_id, "--note", "Prioritize"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert approve.returncode == 0, approve.stderr

    audit = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "audit-log", "--run-id", run_dir.name],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert audit.returncode == 0, audit.stderr
    assert "Prioritize" in audit.stdout


def _review_state(tmp_path: Path) -> tuple[ResearchStateManager, ResearchRunState]:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.papers = [
        Paper(
            id="paper-1",
            title="False-positive budgeted collusion detection",
            authors=["A. Researcher"],
            abstract="The paper reports evaluation under a fixed false-positive budget.",
            year=2025,
            source="fixture",
        )
    ]
    state.paper_notes = [
        PaperNote(
            paper_id="paper-1",
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            datasets=["synthetic-collusion-graphs"],
        )
    ]
    state.claims = [
        Claim(
            id="claim-1",
            text="Fixed false-positive budgets are relevant for collusion detection.",
            type="background",
        )
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Human-review target gap",
            description="A gap that the researcher may reject.",
            explicit_reason="Fixture gap.",
            risk_that_gap_is_fake="Could already be solved.",
            confidence="medium",
            novelty_status="medium",
        ),
        Gap(
            id="gap-2",
            title="Active experiment gap",
            description="Evaluate collusion detection under fixed false-positive budgets.",
            explicit_reason="Fixture gap.",
            risk_that_gap_is_fake="Selective detection literature may cover it.",
            confidence="medium",
            novelty_status="medium",
        ),
    ]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="Human-review target gap",
            closest_prior_work=["paper-1"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        ),
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-2",
            idea_summary="Active experiment gap",
            closest_prior_work=["paper-1"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        ),
    ]
    return manager, state
