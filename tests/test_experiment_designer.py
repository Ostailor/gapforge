from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Gap, NoveltyAssessment, PaperNote
from gapforge.skills.experiment_designer import ExperimentDesigner
from gapforge.state import ResearchStateManager


def test_experiment_designer_skips_rejected_gaps_by_default(tmp_path: Path) -> None:
    state = _experiment_state(tmp_path)

    ExperimentDesigner().design(state)

    assert len(state.experiments) == 1
    experiment = state.experiments[0]
    assert experiment.linked_gap_ids == ["gap-pursue"]
    assert "gap-reject" not in experiment.linked_gap_ids


def test_experiment_designer_can_include_rejected_with_flag(tmp_path: Path) -> None:
    state = _experiment_state(tmp_path)

    ExperimentDesigner().design(state, allow_rejected=True)

    linked = {experiment.linked_gap_ids[0] for experiment in state.experiments}
    assert linked == {"gap-reject", "gap-pursue"}


def test_experiment_contains_decisive_reviewer_ready_fields(tmp_path: Path) -> None:
    state = _experiment_state(tmp_path)

    ExperimentDesigner().design(state)

    experiment = state.experiments[0]
    assert experiment.baselines
    assert experiment.metrics
    assert experiment.what_result_would_falsify_the_idea
    assert "Publishable result" in experiment.reviewer_killer_result
    assert experiment.minimum_viable_experiment
    assert experiment.implementation_steps
    assert experiment.statistical_tests
    assert experiment.confidence in {"low", "medium", "high"}


def test_experiment_artifacts_are_written(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _experiment_state(tmp_path, manager=manager)

    ExperimentDesigner().design(state)
    manager.save_run(state)

    run_dir = Path(state.run_dir)
    assert (run_dir / "experiments.json").exists()
    assert (run_dir / "experiments.md").exists()
    assert (run_dir / "implementation_tasks.md").exists()
    assert "Reviewer Killer Result" in (run_dir / "experiments.md").read_text(encoding="utf-8")
    data = json.loads((run_dir / "experiments.json").read_text(encoding="utf-8"))
    assert data[0]["baselines"]
    assert data[0]["what_result_would_falsify_the_idea"]


def test_design_experiment_cli_for_single_gap(tmp_path: Path) -> None:
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

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "design-experiment", "--run-id", run_dir.name, "--gap-id", gap_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "experiments.md" in result.stdout
    experiments = json.loads((run_dir / "experiments.json").read_text(encoding="utf-8"))
    assert all(gap_id in experiment["linked_gap_ids"] for experiment in experiments)


def _experiment_state(tmp_path: Path, manager: ResearchStateManager | None = None):
    manager = manager or ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.gaps = [
        Gap(
            id="gap-reject",
            title="Duplicate false-positive benchmark",
            type="benchmark gap",
            description="Build the same false-positive benchmark as prior work.",
            explicit_reason="Fixture gap.",
            risk_that_gap_is_fake="Prior work appears identical.",
            novelty_status="likely_not_new",
        ),
        Gap(
            id="gap-pursue",
            title="False-positive calibrated collusion detection under alert budgets",
            type="measurement gap",
            description="Evaluate collusion detection under fixed false-positive alert budgets.",
            why_existing_work_does_not_solve_it="Existing work reports broad anomaly scores but not alert-budget behavior.",
            minimum_experiment_needed="Compare baselines at matched false-positive alert budgets.",
            explicit_reason="Fixture gap.",
            risk_that_gap_is_fake="Selective detection literature may already cover this.",
            confidence="medium",
            novelty_status="medium",
        ),
    ]
    state.paper_notes = [
        PaperNote(
            paper_id="paper-1",
            datasets=["synthetic-collusion-graphs"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
        )
    ]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-reject",
            idea_summary="Duplicate false-positive benchmark",
            closest_prior_work=["paper-x: Same Benchmark (similarity 0.90)"],
            verdict="reject",
            novelty_strength="weak",
            confidence="high",
        ),
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-pursue",
            idea_summary="False-positive calibrated collusion detection under alert budgets",
            closest_prior_work=["paper-y: Related Anomaly Detection (similarity 0.30)"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
            possible_reviewer_objection="A reviewer may ask whether anomaly detection baselines already solve this.",
        ),
    ]
    return state
