from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.models import (
    BaselineCandidate,
    ClaimGraph,
    ExperimentPlan,
    ExperimentProtocol,
    NoveltyDossier,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchDirection,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.panel import ReviewPanelBuilder, render_review_panel_markdown
from gapforge.reviewers.rebuttal import render_rebuttal_plans_markdown
from gapforge.state import ResearchStateManager


def test_review_panel_fatal_missing_baseline_reduces_score(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path, include_baselines=False)

    panel = ReviewPanelBuilder(config).build_for_project(project_id, direction_id)

    empirical = next(review for review in panel.reviewer_reviews if review.role == "empirical")
    assert empirical.score < 5
    assert empirical.fatal_flaws
    assert "baseline" in " ".join(empirical.required_fixes).lower()
    assert panel.decision_risk in {"reject_likely", "high"}


def test_review_panel_unresolved_novelty_duplicate_creates_rejection_risk(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path, novelty_verdict="reject")

    panel = ReviewPanelBuilder(config).build_for_project(project_id, direction_id)

    novelty = next(review for review in panel.reviewer_reviews if review.role == "novelty")
    assert novelty.fatal_flaws
    assert panel.decision_risk == "reject_likely"
    assert any("duplicative" in flaw.lower() or "prior work" in flaw.lower() for flaw in novelty.fatal_flaws)


def test_rebuttal_plan_recommends_citation_or_experiment(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path, include_baselines=False)

    panel = ReviewPanelBuilder(config).build_for_project(project_id, direction_id)

    assert panel.rebuttal_plan
    assert any(plan.citations_to_add or plan.experiments_to_add for plan in panel.rebuttal_plan)
    text = render_rebuttal_plans_markdown([panel])
    assert "Do not present planned or expected results as completed findings" in text


def test_review_panel_output_contains_no_fake_result_claims(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path, include_baselines=False)

    panel = ReviewPanelBuilder(config).build_for_project(project_id, direction_id)
    text = render_review_panel_markdown(panel) + render_rebuttal_plans_markdown([panel])

    assert "our results show" not in text.lower()
    assert "we found" not in text.lower()
    assert "significantly outperforms" not in text.lower()


def test_review_panel_fake_llm_path_remains_safe(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path)
    client = FakeLLMClient(run_dir=tmp_path, skill_name="review-panel")

    panel = ReviewPanelBuilder(config, llm_client=client).build_for_project(project_id, direction_id)

    llm_review = next(review for review in panel.reviewer_reviews if review.reviewer_id == "LLM")
    assert llm_review.confidence == "low"
    assert llm_review.score <= 4
    assert "advisory" in " ".join(llm_review.required_fixes).lower()


def test_review_panel_cli_and_package_export(tmp_path: Path) -> None:
    config, project_id, direction_id = _panel_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "review-panel", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Review Panel" in result.stdout
    project_root = Path(config.project_root, project_id)
    assert (project_root / "review_panels.json").exists()
    assert (project_root / "review_panel.md").exists()

    package = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-paper-package", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert package.returncode == 0, package.stderr
    package_root = project_root / "paper_packages" / direction_id
    assert (package_root / "review_panel.md").exists()
    assert "Review Panel" in (package_root / "review_panel.md").read_text(encoding="utf-8")
    assert json.loads((package_root / "paper_package.json").read_text(encoding="utf-8"))["direction_id"] == direction_id


def _panel_fixture(
    tmp_path: Path,
    *,
    include_baselines: bool = True,
    novelty_verdict: str = "pursue",
) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("review panel fixture")
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Review panel experiment",
            linked_gap_ids=["gap-1"],
            hypothesis="A calibrated detector improves recall at fixed FPR.",
            minimum_viable_experiment="Compare proposed method against closest prior work.",
            baselines=["closest-prior-work"] if include_baselines else [],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            statistical_tests=["bootstrap confidence intervals"],
            what_result_would_falsify_the_idea="Closest prior work matches the proposed method.",
            reviewer_killer_result="Hypothetical publishable pattern: better recall at fixed FPR after experiments are run.",
            novelty_assessment_id="gap-1",
        )
    ]
    state.experiment_protocols = [
        ExperimentProtocol(
            id="protocol-1",
            direction_id="gap-1",
            linked_experiment_plan_id="experiment-1",
            objective="Test calibrated detection.",
            hypothesis="A calibrated detector improves recall at fixed FPR.",
            datasets=["fixture-dataset"],
            baselines=[
                BaselineCandidate(
                    paper_id="paper-1",
                    baseline_name="closest prior work",
                    why_required="Required for reviewer comparison.",
                )
            ]
            if include_baselines
            else [],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            statistical_tests=["bootstrap confidence intervals"],
            failure_modes=["No improvement over closest prior work."],
            safety_ethics_notes=["Audit false positives."],
        )
    ]
    state.related_work_matrices = [
        RelatedWorkMatrix(
            direction_id="gap-1",
            entries=[
                RelatedWorkEntry(
                    direction_id="gap-1",
                    paper_id="paper-1",
                    relationship="baseline_to_include",
                    evidence_span_ids=["span-1"],
                    must_cite=True,
                    baseline_candidate=include_baselines,
                    reviewer_risk_if_omitted="baseline omission is fatal",
                )
            ],
            must_read_paper_ids=["paper-1"],
            baseline_paper_ids=["paper-1"] if include_baselines else [],
        )
    ]
    state.novelty_dossiers = [
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Review panel direction",
            top_prior_work=["paper-1"],
            candidates_considered=["paper-1"],
            comparison_table=[{"paper_id": "paper-1", "overall_similarity": 0.8}],
            decisive_difference_needed="Use the fixed-FPR setting.",
            verdict=novelty_verdict,
            novelty_strength="weak" if novelty_verdict == "reject" else "medium",
            confidence="medium",
        )
    ]
    state_manager.save_run(state)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Review Panel Project")
    project_manager.attach_run(program.project.id, state.run_id)
    program = project_manager.load_project(program.project.id)
    direction = ResearchDirection(
        id="direction-1",
        project_id=program.project.id,
        title="Review Panel Direction",
        linked_gap_ids=["gap-1"],
        linked_experiment_ids=["experiment-1"],
        linked_novelty_dossier_ids=["gap-1"],
        supporting_paper_ids=["paper-1"],
        maturity="experiment_ready",
        readiness_score=0.75,
    )
    program.research_directions = [direction]
    program.related_work_matrices = state.related_work_matrices
    program.experiment_protocols = state.experiment_protocols
    program.claim_graph = ClaimGraph(project_id=program.project.id)
    project_manager.save_project(program)
    return config, program.project.id, direction.id
