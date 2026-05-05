from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import ExperimentPlan, Gap, Hypothesis, NoveltyAssessment, Paper
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.state import ResearchStateManager


def test_novelty_gate_rejects_duplicate_idea(tmp_path: Path) -> None:
    state = _state_with_gap(
        tmp_path,
        Gap(
            id="gap-duplicate",
            title="False-positive calibrated collusion detector benchmark",
            description="Build a false-positive calibrated collusion detector benchmark.",
            supporting_paper_ids=["p-duplicate"],
            risk_that_gap_is_fake="Existing benchmark papers may already solve it.",
        ),
        [
            Paper(
                id="p-duplicate",
                title="False-positive calibrated collusion detector benchmark",
                authors=["A"],
                abstract="We build a false-positive calibrated collusion detector benchmark.",
                year=2025,
                source="fixture",
            )
        ],
    )

    NoveltyGate().run(state)

    assessment = state.novelty_assessments[0]
    assert assessment.verdict == "reject"
    assert assessment.novelty_strength == "weak"
    assert state.gaps[0].novelty_status == "likely_not_new"
    assert state.rejected_ideas
    assert any(claim.type == "novelty" for claim in state.claims)


def test_novelty_gate_revises_near_duplicate_idea(tmp_path: Path) -> None:
    state = _state_with_gap(
        tmp_path,
        Gap(
            id="gap-revise",
            title="Calibration benchmark for collusion detection under analyst review",
            description="Measure collusion detection calibration under analyst review.",
            supporting_paper_ids=["p-near"],
            risk_that_gap_is_fake="Fraud detection review benchmarks may already cover the main idea.",
        ),
        [
            Paper(
                id="p-near",
                title="Calibration benchmark for fraud detection under analyst review",
                authors=["B"],
                abstract="A benchmark for calibration under analyst review in fraud detection.",
                year=2024,
                source="fixture",
            )
        ],
    )

    NoveltyGate().run(state)

    assessment = state.novelty_assessments[0]
    assert assessment.verdict == "revise"
    assert assessment.novelty_strength == "weak"
    assert state.gaps[0].novelty_status == "weak"


def test_novelty_gate_pursues_distinct_but_related_idea(tmp_path: Path) -> None:
    state = _state_with_gap(
        tmp_path,
        Gap(
            id="gap-pursue",
            title="Abstention-aware collusion detection under false-positive budgets",
            description="Evaluate collusion detection with abstention under fixed false-positive budgets.",
            supporting_paper_ids=["p-related"],
            why_existing_work_does_not_solve_it="Closest work studies anomaly detection, not collusion-specific evaluation.",
            minimum_experiment_needed="Compare against selective anomaly detection baselines at fixed false-positive budgets.",
            risk_that_gap_is_fake="Selective classification papers may already include a collusion benchmark.",
        ),
        [
            Paper(
                id="p-related",
                title="Selective classification for anomaly detection with false-positive budgets",
                authors=["C"],
                abstract="Selective classification abstains on uncertain anomaly predictions under false-positive budgets.",
                year=2023,
                source="fixture",
            )
        ],
    )

    NoveltyGate().run(state)

    assessment = state.novelty_assessments[0]
    assert assessment.verdict == "pursue"
    assert assessment.novelty_strength == "medium"
    assert state.gaps[0].novelty_status == "medium"


def test_novelty_gate_marks_unsearched_idea_unknown(tmp_path: Path) -> None:
    state = _state_with_gap(
        tmp_path,
        Gap(
            id="gap-unknown",
            title="Counterfactual provenance drift in emergent research agents",
            description="Study counterfactual provenance drift in research agents.",
            explicit_reason="This is an indirect idea from field-map structure.",
            risk_that_gap_is_fake="The current run has no adjacent-field searches.",
        ),
        [],
    )

    NoveltyGate().run(state)

    assessment = state.novelty_assessments[0]
    assert assessment.verdict == "unknown"
    assert assessment.novelty_strength == "unknown"
    assert assessment.missing_searches
    assert not state.claims


def test_novelty_gate_writes_artifacts_and_validates_paper_ready_experiments(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("novelty validation")
    state.hypotheses.append(Hypothesis(id="hypothesis-1", text="A test hypothesis", rationale="Rationale", gap_id="gap-1"))
    state.experiments.append(
        ExperimentPlan(
            id="experiment-1",
            hypothesis_id="hypothesis-1",
            title="Paper ready experiment",
            design="Design",
            baselines=["closest prior work"],
            metrics=["effect-size"],
            what_result_would_falsify_the_idea="Baseline matches the proposed method.",
            paper_ready=True,
        )
    )
    assert not manager.validate_state(state).ok

    state.novelty_assessments.append(
        NoveltyAssessment(
            target_gap_or_hypothesis_id="hypothesis-1",
            idea_summary="A test hypothesis",
            closest_prior_work=["p1: Related work (similarity 0.30)"],
            novelty_strength="medium",
            verdict="pursue",
        )
    )
    manager.save_run(state)
    assert manager.validate_state(state).ok
    assert (Path(state.run_dir) / "novelty_gate.json").exists()
    assert "# Novelty Gate" in (Path(state.run_dir) / "novelty_gate.md").read_text(encoding="utf-8")


def test_novelty_check_cli(tmp_path: Path) -> None:
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
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

    novelty = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "novelty-check", "--run-id", run_dir.name, "--gap-id", gap_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert novelty.returncode == 0, novelty.stderr
    assert "novelty assessments" in novelty.stdout
    assert (run_dir / "novelty_gate.md").exists()


def _state_with_gap(tmp_path: Path, gap: Gap, papers: list[Paper]):
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.gaps = [gap]
    state.papers = papers
    return state
