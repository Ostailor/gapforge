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
from gapforge.release_gate.v21 import V21ReleaseGateEnforcer
from gapforge.selected_benchmark import (
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkWorkspaceManager,
)
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"
SELECTED_TITLE = "Sequential specificity benchmark for low-FPR collusion audits"


def test_v21_release_gate_missing_benchmark_spec_fails(tmp_path: Path) -> None:
    config, _project_id = _v2_selected_project(tmp_path)

    result = V21ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["benchmark_spec_exists"] is False
    assert any("benchmark_spec_exists" in blocker for blocker in result.blockers)


def test_v21_release_gate_missing_smoke_run_fails(tmp_path: Path) -> None:
    config, project_id = _v2_selected_project(tmp_path)
    spec = _benchmark_scaffold(config, project_id)
    SelectedBenchmarkWorkspaceManager(config).create_workspace(spec.id)
    SelectedBenchmarkReviewerPanelBuilder(config).review(spec.id)
    SelectedBenchmarkManuscriptManager(config).paper_package(spec.id)

    result = V21ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["smoke_run_completed"] is False
    assert any("smoke_run_completed" in blocker for blocker in result.blockers)


def test_v21_release_gate_fake_result_fails(tmp_path: Path) -> None:
    config, project_id, spec_id = _complete_v21_fixture(tmp_path)
    benchmark_dir = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"
    fake_path = benchmark_dir / "reports" / "fake_result.md"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text("fake result: fabricated benchmark win presented as empirical evidence.\n", encoding="utf-8")

    result = V21ReleaseGateEnforcer(config).evaluate()

    assert spec_id == result.benchmark_id
    assert result.passed is False
    assert result.requirements["no_fake_results"] is False
    assert any("fake-result" in blocker for blocker in result.blockers)


def test_v21_release_gate_underpowered_overclaim_fails(tmp_path: Path) -> None:
    config, project_id, _spec_id = _complete_v21_fixture(tmp_path)
    benchmark_dir = Path(ProjectMemoryManager(config).load_project(project_id).project.root_dir) / "selected_benchmark"
    overclaim = benchmark_dir / "paper_package" / "overclaim.md"
    overclaim.write_text("The smoke run supports strong low-FPR claims.\n", encoding="utf-8")

    result = V21ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_strong_low_fpr_claim_from_underpowered_smoke"] is False
    assert any("Underpowered smoke low-FPR overclaim" in blocker for blocker in result.blockers)


def test_v21_release_gate_complete_fixture_passes_and_cli_json(tmp_path: Path) -> None:
    config, _project_id, spec_id = _complete_v21_fixture(tmp_path)

    result = V21ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.status == "pass"
    assert result.benchmark_id == spec_id
    assert result.requirements["v2_release_gate_passes"] is True
    assert result.requirements["smoke_run_completed"] is True
    assert result.requirements["result_artifacts_parsed"] is True
    assert any("underpowered" in warning for warning in result.warnings)

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v21-release-gate", "--write-report", "--json"],
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
    assert (tmp_path / "data" / "release_gate" / "v21_release_gate_latest.json").exists()


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


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
