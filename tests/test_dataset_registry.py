from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import BaselineCandidate, ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_register_fixture_dataset_and_render_card(tmp_path: Path) -> None:
    config, workspace_id, csv_path = _dataset_workspace(tmp_path)
    registry = DatasetRegistry(config)

    record = registry.register_dataset(
        workspace_id=workspace_id,
        name="Fixture Evaluation Dataset",
        path=csv_path,
        dataset_type="fixture",
        license="CC0",
        intended_use="Validate experiment plumbing.",
    )
    card = registry.render_card(record.id)
    records = registry.list_datasets(workspace_id)

    assert record.dataset_type == "fixture"
    assert record.size_summary == "3 rows, 3 columns"
    assert record.split_names == ["test", "train"]
    assert records[0].id == record.id
    assert "Fixture data is for workflow validation" in card
    assert record.provenance.source_ids[0] == workspace_id


def test_validate_simple_csv_fixture_and_unknown_license_warning(tmp_path: Path) -> None:
    config, workspace_id, csv_path = _dataset_workspace(tmp_path)
    registry = DatasetRegistry(config)
    record = registry.register_dataset(workspace_id=workspace_id, name="Unknown License Fixture", path=csv_path, dataset_type="fixture")

    result = registry.validate_dataset(record.id)

    assert result.status == "warning"
    assert result.row_count == 3
    assert result.column_count == 3
    assert "Dataset license is unknown." in result.issues
    assert any("fixture" in issue for issue in result.issues)
    assert result.split_integrity == "ok: test, train"


def test_validate_json_dataset(tmp_path: Path) -> None:
    config, workspace_id, _csv_path = _dataset_workspace(tmp_path)
    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps([{"text": "a", "label": 1, "split": "train"}, {"text": "b", "label": 0, "split": "test"}]), encoding="utf-8"
    )
    registry = DatasetRegistry(config)
    record = registry.register_dataset(
        workspace_id=workspace_id,
        name="Synthetic JSON Dataset",
        path=dataset,
        dataset_type="synthetic",
        license="MIT",
    )

    result = registry.validate_dataset(record.id)
    card = registry.render_card(record.id)

    assert result.status == "warning"
    assert result.row_count == 2
    assert result.column_count == 3
    assert "Synthetic data must be labeled" in card
    assert any("synthetic" in issue for issue in result.issues)


def test_real_dataset_without_split_warns_about_leakage(tmp_path: Path) -> None:
    config, workspace_id, _csv_path = _dataset_workspace(tmp_path)
    dataset = tmp_path / "real.csv"
    dataset.write_text("text,label\nalpha,1\nbeta,0\n", encoding="utf-8")
    registry = DatasetRegistry(config)
    record = registry.register_dataset(
        workspace_id=workspace_id,
        name="Real Dataset",
        path=dataset,
        dataset_type="real",
        license="ODC-BY",
    )

    result = registry.validate_dataset(record.id)

    assert result.status == "warning"
    assert any("No `split` column" in item for item in result.leakage_warnings)


def test_dataset_cli_register_card_validate_list(tmp_path: Path) -> None:
    _config, workspace_id, csv_path = _dataset_workspace(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "dataset-register",
            "--workspace-id",
            workspace_id,
            "--name",
            "CLI Fixture Dataset",
            "--path",
            str(csv_path),
            "--dataset-type",
            "fixture",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert registered.returncode == 0, registered.stderr
    dataset_id = json.loads(registered.stdout)["id"]

    card = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-card", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    validation = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-validate", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    listing = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-list", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert card.returncode == 0, card.stderr
    assert validation.returncode == 0, validation.stderr
    assert listing.returncode == 0, listing.stderr
    assert "Dataset Card" in card.stdout
    assert "Dataset Validation" in validation.stdout
    assert "CLI Fixture Dataset" in listing.stdout


def _dataset_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str, Path]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Dataset Registry Project")
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id="direction-1",
        linked_experiment_plan_id="experiment-1",
        objective="Validate dataset registry.",
        hypothesis="Dataset registry should preserve data identity.",
        datasets=["fixture"],
        baselines=[BaselineCandidate(paper_id="paper-1", baseline_name="baseline")],
        metrics=["accuracy"],
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-1")
    csv_path = tmp_path / "fixture.csv"
    csv_path.write_text("text,label,split\nalpha,1,train\nbeta,0,test\n,1,train\n", encoding="utf-8")
    return config, workspace.id, csv_path
