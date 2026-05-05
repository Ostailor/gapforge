from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.experiments.protocol import ExperimentProtocolBuilder, render_protocol_markdown
from gapforge.models import ExperimentPlan, Gap, Paper, RelatedWorkEntry, RelatedWorkMatrix
from gapforge.project_memory import ProjectMemoryManager
from gapforge.skills.reviewer_simulation import ReviewerSimulation
from gapforge.state import ResearchStateManager


def test_missing_baseline_creates_major_protocol_warning(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path, include_matrix=False)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    state.experiments[0].baselines = []
    state_manager.save_run(state)

    protocol = ExperimentProtocolBuilder(config).build_for_run(run_id, "experiment-1")

    assert any("Major warning: no strong related-work baseline" in item for item in protocol.failure_modes)
    assert any("no related-work matrix" in item for item in protocol.failure_modes)


def test_related_work_baseline_appears_in_protocol(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)

    protocol = ExperimentProtocolBuilder(config).build_for_run(run_id, "experiment-1")

    assert any(candidate.paper_id == "p-baseline" for candidate in protocol.baselines)
    assert any("Benchmark Baseline" in candidate.baseline_name for candidate in protocol.baselines)


def test_low_fpr_metric_recommends_exact_or_binomial_notes(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)

    protocol = ExperimentProtocolBuilder(config).build_for_run(run_id, "experiment-1")

    assert any("confidence intervals" in test.lower() for test in protocol.statistical_tests)
    assert "binomial" in protocol.power_or_sample_size_notes.lower()


def test_protocol_renders_markdown_and_reproducibility_cli(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)
    protocol = ExperimentProtocolBuilder(config).build_for_run(run_id, "experiment-1")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    rendered = render_protocol_markdown(protocol)
    checklist = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproducibility-checklist", "--run-id", run_id, "--experiment-id", "experiment-1"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Evaluation Script Outline" in rendered
    assert "Reproducibility Checklist" in checklist.stdout
    assert checklist.returncode == 0, checklist.stderr
    assert (Path(config.runs_dir, run_id, "experiment_protocols.md")).exists()


def test_reviewer_simulation_uses_protocol_completeness(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)

    ReviewerSimulation().review(state)
    missing_protocol = [item for item in state.reviewer_objections if "no executable protocol" in item.objection.lower()]
    assert missing_protocol
    assert missing_protocol[0].severity == "major"

    state = state_manager.load_run(run_id)
    ExperimentProtocolBuilder(config).build_for_run(run_id, "experiment-1")
    state = state_manager.load_run(run_id)
    ReviewerSimulation().review(state)

    assert not any("no executable protocol" in item.objection.lower() for item in state.reviewer_objections)


def test_paper_ready_experiment_requires_protocol_validation(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    state.experiments[0].paper_ready = True

    result = state_manager.validate_state(state)

    assert any(issue.code == "paper-ready-experiment-without-protocol" for issue in result.issues)


def test_project_protocol_and_baselines_cli(tmp_path: Path) -> None:
    config, run_id = _protocol_run(tmp_path)
    state = ResearchStateManager(config).load_run(run_id)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Protocol Project")
    project_manager.attach_run(program.project.id, run_id)
    direction = DirectionMaturationManager(config).create_direction(program.project.id, "gap-1")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    protocol = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "experiment-protocol",
            "--project-id",
            program.project.id,
            "--direction-id",
            direction.id,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    baselines = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "baselines", "--project-id", program.project.id, "--direction-id", direction.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert state.run_id == run_id
    assert protocol.returncode == 0, protocol.stderr
    assert "Protocol" in protocol.stdout
    assert baselines.returncode == 0, baselines.stderr
    assert "p-baseline" in baselines.stdout
    assert (Path(config.project_root, program.project.id, "experiment_protocols.json")).exists()


def _protocol_run(tmp_path: Path, *, include_matrix: bool = True) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("low false positive protocol")
    state.papers = [
        Paper(
            id="p-baseline",
            title="Benchmark Baseline for Low FPR Monitoring",
            authors=["A"],
            abstract="Provides a benchmark and baseline implementation.",
            year=2025,
            source="fixture",
            raw_metadata={"code_url": "https://example.test/baseline"},
        )
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Low FPR protocol gap",
            description="Evaluate monitoring at low false positive rates.",
            supporting_paper_ids=["p-baseline"],
            risk_that_gap_is_fake="Baseline papers may already solve the setting.",
            novelty_status="medium",
        )
    ]
    if include_matrix:
        state.related_work_matrices = [
            RelatedWorkMatrix(
                direction_id="gap-1",
                entries=[
                    RelatedWorkEntry(
                        direction_id="gap-1",
                        paper_id="p-baseline",
                        relationship="baseline_to_include",
                        relevance_score=0.8,
                        what_it_contributes="Provides strongest available benchmark baseline.",
                        what_it_does_not_solve="Does not test the proposed workload metric.",
                        must_cite=True,
                        baseline_candidate=True,
                        reviewer_risk_if_omitted="baseline omission risk",
                    )
                ],
                coverage_summary="Fixture matrix.",
                must_read_paper_ids=["p-baseline"],
                baseline_paper_ids=["p-baseline"],
            )
        ]
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Low-FPR protocol experiment",
            linked_gap_ids=["gap-1"],
            hypothesis="A workload-aware monitor improves recall at fixed low FPR.",
            core_claim_being_tested="The gap requires workload-aware low-FPR evaluation.",
            minimum_viable_experiment="Compare candidate monitor against baseline at fixed FPR.",
            datasets_needed=["synthetic-monitoring-logs"],
            baselines=["simple threshold baseline"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            statistical_tests=[],
            ablations=["remove workload calibration"],
            what_result_would_falsify_the_idea="Baseline matches recall at fixed FPR.",
            reviewer_killer_result="Improves recall at matched low FPR with confidence intervals.",
            ethical_or_safety_considerations=["Audit false positives."],
            novelty_assessment_id="gap-1",
            confidence="medium",
        )
    ]
    state_manager.save_run(state)
    return config, state.run_id
