from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import BaselineCandidate, ExperimentPlan, ExperimentProtocol, NoveltyAssessment, PaperNote, ReproducibilityChecklist
from gapforge.skills.reviewer_simulation import ReviewerSimulation
from gapforge.state import ResearchStateManager


def test_reviewer_flags_missing_baselines_as_fatal(tmp_path: Path) -> None:
    state = _review_state(tmp_path)
    state.experiments[0].baselines = []

    ReviewerSimulation().review(state)

    baseline_objections = [item for item in state.reviewer_objections if item.category == "baseline"]
    assert baseline_objections
    assert baseline_objections[0].severity == "fatal"
    assert baseline_objections[0].blocks_submission is True
    assert "Add closest-prior-work" in baseline_objections[0].suggested_fix
    assert state.reviewer_summaries[0].final_recommendation == "not_ready"


def test_reviewer_flags_unsupported_novelty_as_fatal(tmp_path: Path) -> None:
    state = _review_state(tmp_path)
    state.novelty_assessments = []

    ReviewerSimulation().review(state)

    novelty_objections = [item for item in state.reviewer_objections if item.category == "novelty"]
    assert any(item.severity == "fatal" for item in novelty_objections)
    assert any("no novelty assessment" in item.objection.lower() for item in novelty_objections)
    assert state.reviewer_summaries[0].blocking_issues
    assert state.reviewer_summaries[0].submission_readiness_score < 70


def test_reviewer_scores_strong_plan_higher_than_weak_plan(tmp_path: Path) -> None:
    strong = _review_state(tmp_path / "strong")
    ReviewerSimulation().review(strong)

    weak = _review_state(tmp_path / "weak")
    weak.experiments[0].baselines = []
    weak.experiments[0].metrics = []
    weak.novelty_assessments = []
    ReviewerSimulation().review(weak)

    assert strong.reviewer_summaries[0].submission_readiness_score > weak.reviewer_summaries[0].submission_readiness_score
    assert strong.reviewer_summaries[0].final_recommendation in {
        "conference_potential",
        "strong_submission_candidate",
        "workshop_ready",
    }
    assert weak.reviewer_summaries[0].final_recommendation == "not_ready"


def test_reviewer_artifacts_are_written(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _review_state(tmp_path, manager=manager)

    ReviewerSimulation().review(state)
    manager.save_run(state)

    run_dir = Path(state.run_dir)
    assert (run_dir / "reviewer_objections.json").exists()
    assert (run_dir / "reviewer_summaries.json").exists()
    assert (run_dir / "reviewer_simulation.md").exists()
    assert (run_dir / "revised_experiment_recommendations.md").exists()
    assert "Submission readiness score" in (run_dir / "reviewer_simulation.md").read_text(encoding="utf-8")
    objections = json.loads((run_dir / "reviewer_objections.json").read_text(encoding="utf-8"))
    assert objections[0]["suggested_fix"]


def test_review_cli_for_single_experiment(tmp_path: Path) -> None:
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
    experiment_id = json.loads((run_dir / "experiments.json").read_text(encoding="utf-8"))[0]["id"]

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review", "--run-id", run_dir.name, "--experiment-id", experiment_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "reviewer objections" in result.stdout
    objections = json.loads((run_dir / "reviewer_objections.json").read_text(encoding="utf-8"))
    assert objections
    assert {item["experiment_id"] for item in objections} == {experiment_id}


def _review_state(tmp_path: Path, manager: ResearchStateManager | None = None):
    manager = manager or ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Measurement study: false-positive calibrated collusion detection",
            linked_gap_ids=["gap-1"],
            hypothesis="False-positive calibrated review improves collusion detection at fixed alert budgets.",
            core_claim_being_tested="Existing work does not test alert-budget behavior.",
            minimum_viable_experiment="Compare candidate methods at fixed false-positive budgets.",
            datasets_needed=["synthetic-collusion-graphs", "public interaction logs"],
            baselines=["closest-prior-work implementation", "graph anomaly detector", "rule-based collusion heuristic"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr", "precision-at-alert-budget"],
            statistical_tests=["bootstrap confidence intervals", "paired permutation test"],
            ablations=["remove calibration", "sweep alert thresholds"],
            what_result_would_falsify_the_idea="The closest-prior-work baseline matches the proposed method.",
            reviewer_killer_result="Publishable result: robust improvement over closest prior work at fixed false-positive rate.",
            ethical_or_safety_considerations=["audit false positives because accusation can harm users"],
            novelty_assessment_id="gap-1",
            confidence="medium",
        )
    ]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="False-positive calibrated collusion detection",
            closest_prior_work=["paper-1: Related anomaly detection (similarity 0.31)"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    ]
    state.paper_notes = [PaperNote(paper_id="paper-1", source_basis="full text", metrics=["false-positive-rate"])]
    state.experiment_protocols = [
        ExperimentProtocol(
            id="protocol-1",
            direction_id="gap-1",
            linked_experiment_plan_id="experiment-1",
            objective="Test false-positive calibrated collusion detection.",
            hypothesis="False-positive calibrated review improves collusion detection at fixed alert budgets.",
            datasets=["synthetic-collusion-graphs", "public interaction logs"],
            baselines=[
                BaselineCandidate(
                    paper_id="paper-1",
                    baseline_name="closest prior work baseline",
                    why_required="Closest prior work must be compared.",
                )
            ],
            metrics=["false-positive-rate", "recall-at-fixed-fpr", "precision-at-alert-budget"],
            statistical_tests=["bootstrap confidence intervals"],
            expected_artifacts=["metrics_summary.csv"],
            evaluation_script_outline=["run baselines", "compute metrics"],
            reproducibility_checklist=ReproducibilityChecklist(
                metric_definitions=["false-positive-rate"],
                negative_controls=["no-collusion control"],
                error_analysis_plan="Inspect false positives and false negatives.",
            ),
        )
    ]
    return state
