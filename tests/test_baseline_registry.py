from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentProtocol, RelatedWorkEntry, RelatedWorkMatrix, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager


def test_register_baseline_and_render_card(tmp_path: Path) -> None:
    config, workspace_id, _project_id, _direction_id = _baseline_workspace(tmp_path)
    registry = BaselineRegistry(config)

    record = registry.register_baseline(
        workspace_id=workspace_id,
        name="Rule-based detector",
        baseline_type="heuristic",
        required_for_submission=True,
        implementation_path="code/baselines/rule_based.py",
        risk_if_missing="Reviewer cannot interpret proposed detector gains.",
    )
    card = registry.render_card(record.id)
    records = registry.list_baselines(workspace_id)

    assert record.id in {item.id for item in records}
    assert record.required_for_submission is True
    assert "Rule-based detector" in card
    assert "Reviewer cannot interpret" in card


def test_baseline_from_related_work_materializes_required_baseline(tmp_path: Path) -> None:
    config, workspace_id, project_id, direction_id = _baseline_workspace(tmp_path)
    registry = BaselineRegistry(config)

    records = registry.from_related_work(project_id=project_id, direction_id=direction_id)
    listed = registry.list_baselines(workspace_id)

    assert records
    assert listed[0].source_paper_ids == ["paper-baseline"]
    assert listed[0].required_for_submission is True
    assert listed[0].related_work_entry_ids
    assert "baseline omission is fatal" in listed[0].risk_if_missing


def test_missing_required_related_work_baseline_blocks_readiness(tmp_path: Path) -> None:
    config, workspace_id, _project_id, _direction_id = _baseline_workspace(tmp_path)
    registry = BaselineRegistry(config)

    blockers = registry.readiness_blockers(workspace_id)
    registry.register_baseline(
        workspace_id=workspace_id,
        name="Closest prior work",
        baseline_type="prior_work",
        source_paper_ids=["paper-baseline"],
        implementation_path="code/baselines/closest_prior.py",
        required_for_submission=True,
    )
    cleared = registry.readiness_blockers(workspace_id)

    assert any("paper-baseline" in blocker for blocker in blockers)
    assert cleared == []


def test_registered_baselines_feed_experiment_manifest(tmp_path: Path) -> None:
    config, workspace_id, _project_id, _direction_id = _baseline_workspace(tmp_path)
    registry = BaselineRegistry(config)
    baseline = registry.register_baseline(
        workspace_id=workspace_id,
        name="Submission baseline",
        baseline_type="prior_work",
        source_paper_ids=["paper-baseline"],
        implementation_path="code/baselines/submission.py",
    )

    manifest = ExperimentWorkspaceManager(config).create_manifest(workspace_id=workspace_id, run_type="smoke")

    assert baseline.id in manifest.baseline_ids


def test_baseline_cli_register_from_related_work_list_card(tmp_path: Path) -> None:
    _config, workspace_id, project_id, direction_id = _baseline_workspace(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "baseline-register",
            "--workspace-id",
            workspace_id,
            "--name",
            "CLI baseline",
            "--baseline-type",
            "heuristic",
            "--implementation-path",
            "code/baselines/cli.py",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    from_related = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "baseline-from-related-work",
            "--project-id",
            project_id,
            "--direction-id",
            direction_id,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    baseline_id = json.loads(registered.stdout)["id"]
    listing = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "baseline-list", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    card = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "baseline-card", "--baseline-id", baseline_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert registered.returncode == 0, registered.stderr
    assert from_related.returncode == 0, from_related.stderr
    assert listing.returncode == 0, listing.stderr
    assert card.returncode == 0, card.stderr
    assert "CLI baseline" in listing.stdout
    assert "Baseline Card" in card.stdout


def _baseline_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Baseline Registry Project")
    direction = ResearchDirection(
        id="direction-1",
        project_id=program.project.id,
        title="Baseline direction",
        summary="Evaluate a method against closest prior work.",
        maturity="experiment_ready",
    )
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id=direction.id,
        linked_experiment_plan_id="experiment-1",
        objective="Compare proposed method against prior work.",
        hypothesis="The proposed method improves the metric.",
        datasets=["fixture"],
        metrics=["accuracy"],
    )
    matrix = RelatedWorkMatrix(
        direction_id=direction.id,
        entries=[
            RelatedWorkEntry(
                direction_id=direction.id,
                paper_id="paper-baseline",
                relationship="baseline_to_include",
                relevance_score=0.9,
                baseline_candidate=True,
                must_cite=True,
                what_it_contributes="Closest prior-work method.",
                reviewer_risk_if_omitted="baseline omission is fatal",
            )
        ],
        baseline_paper_ids=["paper-baseline"],
        must_read_paper_ids=["paper-baseline"],
    )
    program.research_directions.append(direction)
    program.experiment_protocols.append(protocol)
    program.related_work_matrices.append(matrix)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction.id)
    return config, workspace.id, program.project.id, direction.id
