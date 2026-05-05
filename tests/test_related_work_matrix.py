from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.models import EvidenceSpan, ExperimentPlan, Gap, NoveltyDossier, Paper
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.matrix import RelatedWorkMatrixBuilder
from gapforge.related_work.renderer import render_related_work_matrix_markdown
from gapforge.skills.experiment_designer import ExperimentDesigner
from gapforge.state import ResearchStateManager


def test_directly_solving_paper_detected_from_novelty_dossier(tmp_path: Path) -> None:
    config, project_id, direction_id, _run_id = _project_with_related_work_fixture(tmp_path, verdict="reject")

    matrix = RelatedWorkMatrixBuilder(config).build_for_project(project_id, direction_id)
    direct = next(entry for entry in matrix.entries if entry.paper_id == "p-direct")
    program = ProjectMemoryManager(config).load_project(project_id)
    direction = next(item for item in program.research_directions if item.id == direction_id)

    assert direct.relationship == "directly_solves"
    assert direct.must_cite
    assert "fatal novelty risk" in direct.reviewer_risk_if_omitted
    assert "Related-work matrix contains directly solving prior work." in direction.blocking_issues


def test_survey_marked_background_and_must_read(tmp_path: Path) -> None:
    config, project_id, direction_id, _run_id = _project_with_related_work_fixture(tmp_path)

    matrix = RelatedWorkMatrixBuilder(config).build_for_project(project_id, direction_id)
    survey = next(entry for entry in matrix.entries if entry.paper_id == "p-survey")

    assert survey.relationship == "survey_background"
    assert survey.must_cite
    assert "p-survey" in matrix.must_read_paper_ids


def test_benchmark_paper_marked_baseline_dataset_provider(tmp_path: Path) -> None:
    config, project_id, direction_id, _run_id = _project_with_related_work_fixture(tmp_path)

    matrix = RelatedWorkMatrixBuilder(config).build_for_project(project_id, direction_id)
    benchmark = next(entry for entry in matrix.entries if entry.paper_id == "p-benchmark")

    assert benchmark.relationship == "benchmark_dataset_provider"
    assert benchmark.baseline_candidate
    assert "p-benchmark" in matrix.baseline_paper_ids


def test_experiment_plans_inherit_baseline_candidates(tmp_path: Path) -> None:
    config, _project_id, _direction_id, run_id = _project_with_related_work_fixture(tmp_path)
    builder = RelatedWorkMatrixBuilder(config)
    state_manager = ResearchStateManager(config)

    builder.build_for_run(run_id, "gap-1")
    state = state_manager.load_run(run_id)
    ExperimentDesigner().design(state)

    experiment = state.experiments[0]
    assert any("related-work baseline paper: p-benchmark" == baseline for baseline in experiment.baselines)
    assert any("related-work baseline paper: p-direct" == baseline for baseline in experiment.baselines)


def test_matrix_renders_markdown_and_cli_must_read(tmp_path: Path) -> None:
    config, project_id, direction_id, _run_id = _project_with_related_work_fixture(tmp_path)
    matrix = RelatedWorkMatrixBuilder(config).build_for_project(project_id, direction_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    rendered = render_related_work_matrix_markdown(matrix)
    must_read = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "must-read", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Related Work Matrix" in (Path(config.project_root, project_id, "related_work_matrix.md").read_text(encoding="utf-8"))
    assert "Reviewer risk if omitted" in rendered
    assert "p-survey" in must_read.stdout
    assert must_read.returncode == 0, must_read.stderr


def _project_with_related_work_fixture(tmp_path: Path, *, verdict: str = "pursue") -> tuple[GapForgeConfig, str, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("low false positive monitoring")
    state.papers = [
        Paper(
            id="p-direct",
            title="Low False Positive Monitoring Benchmark",
            authors=["A"],
            abstract="A monitor benchmark directly evaluates operator workload at low false positive rates.",
            year=2025,
            source="fixture",
        ),
        Paper(
            id="p-survey",
            title="Survey of Monitoring and False Positive Evaluation",
            authors=["B"],
            abstract="A survey of monitoring methods, evaluation protocols, and false positive controls.",
            year=2024,
            source="fixture",
            roles=["survey"],
        ),
        Paper(
            id="p-benchmark",
            title="Dataset and Benchmark for Alert Workload",
            authors=["C"],
            abstract="Introduces a dataset, labels, and benchmark split for alert workload evaluation.",
            year=2026,
            source="fixture",
            roles=["benchmark"],
        ),
        Paper(
            id="p-method",
            title="Graph Detector for Monitoring",
            authors=["D"],
            abstract="A graph anomaly detector method for monitoring hidden collusion.",
            year=2023,
            source="fixture",
            roles=["method"],
        ),
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-direct",
            paper_id="p-direct",
            quote="The benchmark evaluates operator workload at low false positive rates.",
            locator="p-direct:Results:p4",
            evidence_type="result",
        )
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Low false positive workload gap",
            description="Monitoring work often lacks operator workload evaluation at low false positive rates.",
            supporting_paper_ids=["p-method"],
            linked_paper_ids=["p-method"],
            risk_that_gap_is_fake="A benchmark paper may already cover the workload setting.",
            why_existing_work_does_not_solve_it="Closest method papers do not report workload-sensitive metrics.",
            novelty_status="medium",
        )
    ]
    state.novelty_dossiers = [
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Evaluate monitoring methods under workload-sensitive low-FPR constraints.",
            candidates_considered=["p-direct", "p-method"],
            top_prior_work=["p-direct"],
            comparison_table=[
                {
                    "paper_id": "p-direct",
                    "overall_similarity": 0.86,
                    "problem_overlap": 0.8,
                    "method_overlap": 0.7,
                    "evaluation_overlap": 0.75,
                    "title": "Low False Positive Monitoring Benchmark",
                },
                {
                    "paper_id": "p-method",
                    "overall_similarity": 0.55,
                    "problem_overlap": 0.6,
                    "method_overlap": 0.7,
                    "evaluation_overlap": 0.2,
                    "title": "Graph Detector for Monitoring",
                },
            ],
            decisive_difference_needed="Use a different workload metric or accept that the benchmark already covers the core setting.",
            verdict=verdict,
            novelty_strength="weak" if verdict == "reject" else "medium",
            confidence="medium",
        )
    ]
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Existing experiment",
            linked_gap_ids=["gap-1"],
            baselines=["simple supervised baseline"],
            metrics=["false-positive-rate"],
            what_result_would_falsify_the_idea="No improvement over benchmark baselines.",
        )
    ]
    state_manager.save_run(state)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Related Work Project")
    project_manager.attach_run(program.project.id, state.run_id)
    direction = DirectionMaturationManager(config).create_direction(program.project.id, "gap-1")
    return config, program.project.id, direction.id, state.run_id
