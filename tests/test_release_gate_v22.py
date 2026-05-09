from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import (
    ConstructiveGapGenerator,
    IdeaFeedbackManager,
    IdeaMutationEngine,
    IdeaStore,
    IdeaTransferCandidate,
    SelectedIdeaProjectManager,
    TopicPortfolioGenerator,
)
from gapforge.ideas.models import IdeaNoveltyAssessment, IdeaScoreRecord, IdeaTournament
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v22 import V22ReleaseGateEnforcer
from gapforge.selected_benchmark import (
    PilotAnalysisManager,
    PilotDatasetBuilder,
    PilotPowerManager,
    PilotRunManager,
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkRelatedWorkManager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkWorkspaceManager,
    SelectedPilotManuscriptManager,
)
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"
SELECTED_TITLE = "Sequential specificity benchmark for low-FPR collusion audits"


def test_v22_release_gate_missing_pilot_run_fails(tmp_path: Path) -> None:
    config, _project_id, spec_id = _complete_v21_fixture(tmp_path)
    PilotPowerManager(config).create_plan(spec_id)
    PilotDatasetBuilder(config).build(spec_id, negative_count=300, positive_count=150)

    result = V22ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["v21_release_gate_passes"] is True
    assert result.requirements["pilot_run_executed"] is False
    assert any("pilot_run_executed" in blocker for blocker in result.blockers)


def test_v22_release_gate_missing_related_work_fails(tmp_path: Path) -> None:
    config, project_id, _spec_id = _complete_v22_fixture(tmp_path)
    related_root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark" / "related_work"
    for path in related_root.glob("*"):
        path.unlink()

    result = V22ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["prior_work_recall_attached"] is False
    assert result.requirements["related_work_matrix_attached"] is False


def test_v22_release_gate_alpha_overclaim_fails(tmp_path: Path) -> None:
    config, project_id, _spec_id = _complete_v22_fixture(tmp_path)
    project_root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir)
    pilot_package = project_root / "selected_benchmark" / "pilot_paper_package"
    (pilot_package / "alpha_overclaim.md").write_text("The pilot validates alpha=0.001 operational specificity.\n", encoding="utf-8")

    result = V22ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_alpha_001_claim_unless_powered"] is False
    assert any("alpha=0.001" in blocker for blocker in result.blockers)


def test_v22_release_gate_synthetic_deployment_overclaim_fails(tmp_path: Path) -> None:
    config, project_id, _spec_id = _complete_v22_fixture(tmp_path)
    project_root = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir)
    pilot_package = project_root / "selected_benchmark" / "pilot_paper_package"
    (pilot_package / "deployment_overclaim.md").write_text(
        "Synthetic pilot data establishes deployment validity for operational monitoring.\n",
        encoding="utf-8",
    )

    result = V22ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_deployment_validity_claim_from_synthetic_pilot"] is False
    assert any("Deployment-validity overclaim" in blocker for blocker in result.blockers)


def test_v22_release_gate_complete_fixture_passes_and_cli_json(tmp_path: Path) -> None:
    config, _project_id, spec_id = _complete_v22_fixture(tmp_path)

    result = V22ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.status == "pass"
    assert result.benchmark_id == spec_id
    assert result.requirements["pilot_result_artifacts_parsed"] is True
    assert result.requirements["pilot_manuscript_package_generated"] is True
    assert result.requirements["underpowered_alpha_targets_preserved"] is True
    assert any("alpha=0.001" in warning for warning in result.warnings)

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v22-release-gate", "--write-report", "--json"],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    payload = json.loads(cli.stdout)
    assert payload["passed"] is True
    assert payload["benchmark_id"] == spec_id
    assert (tmp_path / "data" / "release_gate" / "v22_release_gate_latest.json").exists()


def _complete_v22_fixture(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, project_id, spec_id = _complete_v21_fixture(tmp_path)
    _attach_related_work_run(config, project_id)
    PilotPowerManager(config).create_plan(spec_id)
    dataset = PilotDatasetBuilder(config).build(spec_id, negative_count=300, positive_count=150)
    run_manager = PilotRunManager(config)
    manifest = run_manager.create_manifest(spec_id, dataset.id)
    execution = run_manager.run(spec_id, manifest.id)
    PilotAnalysisManager(config).analyze(execution.id)
    related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
    related_work_manager.build_prior_work_recall(spec_id)
    related_work_manager.build_related_work_matrix(spec_id)
    SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(spec_id)
    SelectedPilotManuscriptManager(config).paper_package(spec_id)
    return config, project_id, spec_id


def _complete_v21_fixture(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _v2_selected_project(tmp_path)
    spec = _benchmark_scaffold(config, selected_project_id)
    workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkExperimentRunner(config).run(workspace.id, run_type="smoke")
    SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)
    SelectedBenchmarkManuscriptManager(config).paper_package(spec.id)
    return config, selected_project_id, spec.id


def _benchmark_scaffold(config: GapForgeConfig, selected_project_id: str):
    manager = SelectedBenchmarkManager(config)
    spec = manager.create_spec(selected_project_id)
    manager.create_threat_model(spec.id)
    manager.create_task_families(spec.id)
    return spec


def _v2_selected_project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("v2 low-FPR collusion idea pilot", description=LOW_FPR_TOPIC)
    project_manager.use_project(program.project.id)
    _write_v1_pass(config)
    _attach_run(config, program.project.id)
    selected_id = _discovery_state(config, program.project.id)
    selected_project = SelectedIdeaProjectManager(config).create_selected_project(selected_id)
    return config, selected_project.project_id


def _write_v1_pass(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "v1_readiness_latest.json").write_text(
        json.dumps({"passed": True, "status": "pass", "recommended_next_version": "v1"}, indent=2) + "\n",
        encoding="utf-8",
    )


def _attach_run(config: GapForgeConfig, project_id: str) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = [Paper(id="paper-prior", title="Prior low-FPR monitor", authors=[], abstract="", year=2025)]
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _discovery_state(config: GapForgeConfig, project_id: str) -> str:
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    store = _base_search_state(config, project_id)
    selected = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-selected",
        title=SELECTED_TITLE,
        summary="Specific benchmark candidate that still requires evidence-gated experiments.",
        contribution_type="benchmark",
        proposed_experiment="Compare rule and sequential threshold monitor baselines on benign and collusive traces.",
        expected_baselines=["rule monitor", "sequential threshold monitor"],
        expected_metrics=["false positive rate", "specificity"],
        closest_prior_work_ids=["paper-prior"],
        novelty_status="plausible",
        evidence_score=0.7,
        idea_yield_score=0.9,
        maturity="candidate",
    )
    store.add_novelty_assessment(
        IdeaNoveltyAssessment(
            id=f"novelty-{selected.id}",
            idea_id=selected.id,
            verdict="pursue",
            novelty_strength="medium",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    store.add_tournament(
        IdeaTournament(
            id=f"tournament-{selected.id}",
            project_id=project_id,
            candidate_ids=[selected.id],
            score_records=[IdeaScoreRecord(idea_id=selected.id, total_score=0.85, blockers=[])],
            selected_candidate_id=selected.id,
            selection_reason="fixture selected idea",
            provenance=Provenance(created_by_skill="test", timestamp=utc_now_iso()),
        )
    )
    IdeaFeedbackManager(config).add_feedback(idea_id=selected.id, action="accept", reviewer="fixture", rationale="Accept candidate.")
    return selected.id


def _base_search_state(config: GapForgeConfig, project_id: str) -> IdeaStore:
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    weak = store.add_candidate(
        project_id=project_id,
        source_topic_id="weak",
        title="Weak low-FPR collusion monitor seed",
        summary="Weak seed to force mutation.",
        contribution_type="method",
        novelty_status="weak",
    )
    store.reject_candidate(weak.id, "fixture rejection before mutation")
    IdeaMutationEngine(config).mutate_rejected_ideas(project_id)
    ConstructiveGapGenerator(config).generate_for_project(project_id)
    _write_codex_task_marker(config, project_id)
    state = store.load_state(project_id)
    state.transfer_candidates = state.transfer_candidates or [
        IdeaTransferCandidate(
            id="transfer-fixture",
            source_field="medicine screening/specificity",
            source_concept="specificity",
            target_problem=LOW_FPR_TOPIC,
            transfer_mechanism="Use screening specificity as an audit threshold mechanism.",
            what_breaks="Collusion labels are noisier.",
            confidence="medium",
        )
    ]
    store._save_state(project_id, state)
    return store


def _write_codex_task_marker(config: GapForgeConfig, project_id: str) -> None:
    program = ProjectMemoryManager(config).load_project(project_id)
    task_dir = Path(program.project.root_dir) / "ideas" / "codex_tasks" / "idea-codex-task-fixture"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(
        json.dumps({"id": "idea-codex-task-fixture", "project_id": project_id, "task_type": "idea_seed_expansion"}, indent=2) + "\n",
        encoding="utf-8",
    )


def _attach_related_work_run(config: GapForgeConfig, project_id: str) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = _related_work_papers()
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)


def _related_work_papers() -> list[Paper]:
    return [
        Paper(
            id="paper-low-fpr",
            title="Low false positive specificity evaluation",
            authors=[],
            abstract="false alarm specificity",
            year=2024,
        ),
        Paper(
            id="paper-collusion",
            title="Multi-agent collusion and covert coordination",
            authors=[],
            abstract="collusion coordination",
            year=2023,
        ),
        Paper(id="paper-evasion", title="Monitor evasion by adversarial agents", authors=[], abstract="monitor evasion", year=2025),
        Paper(
            id="paper-sequential",
            title="Sequential testing and change-point detection",
            authors=[],
            abstract="sequential change-point",
            year=2022,
        ),
        Paper(id="paper-benchmark", title="Benchmark evaluation protocol design", authors=[], abstract="benchmark protocol", year=2025),
        Paper(id="paper-anomaly", title="Anomaly detection specificity", authors=[], abstract="anomaly specificity", year=2021),
        Paper(id="paper-medical", title="Medical screening specificity", authors=[], abstract="screening specificity", year=2020),
        Paper(id="paper-cartel", title="Cartel and covert-channel analogies", authors=[], abstract="cartel covert channel", year=2019),
    ]


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
