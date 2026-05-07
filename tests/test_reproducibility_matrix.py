from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, ReplicationManifest, ReproductionRecord, to_plain
from gapforge.replication.matrix import ReproducibilityMatrixBuilder, render_reproducibility_matrix_markdown


def test_matrix_from_fixture_reproduction_records(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    workspace_id, package_id, package_dir = _matrix_package(tmp_path)
    _write_reproduction_record(package_dir, package_id, "local", "pass", {"results/metrics.json": "match"})

    matrix = ReproducibilityMatrixBuilder(config).for_workspace(workspace_id)

    assert matrix.workspace_id == workspace_id
    assert matrix.package_id == package_id
    assert matrix.pass_count == 1
    assert matrix.environments == ["local"]
    assert matrix.reproduction_records


def test_matrix_makes_failures_visible(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _workspace_id, package_id, package_dir = _matrix_package(tmp_path)
    _write_reproduction_record(package_dir, package_id, "docker", "fail", {"results/metrics.json": "hash_mismatch"})

    matrix = ReproducibilityMatrixBuilder(config).for_package_id(package_id)

    assert matrix.fail_count == 1
    assert any("hash_mismatch" in difference for difference in matrix.differences)


def test_matrix_environment_labels_are_preserved(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    workspace_id, package_id, package_dir = _matrix_package(tmp_path)
    _write_reproduction_record(package_dir, package_id, "local", "pass", {"results/metrics.json": "match"})
    _write_reproduction_record(package_dir, package_id, "gpu", "warning", {"results/metrics.json": "not_checked"})

    matrix = ReproducibilityMatrixBuilder(config).for_workspace(workspace_id)

    assert matrix.environments == ["gpu", "local"]
    assert matrix.pass_count == 1
    assert matrix.warning_count == 1


def test_matrix_report_renders_and_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    workspace_id, package_id, package_dir = _matrix_package(tmp_path)
    _write_reproduction_record(package_dir, package_id, "local", "pass", {"results/metrics.json": "match"})
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    matrix = ReproducibilityMatrixBuilder(config).for_workspace(workspace_id)
    by_workspace = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproducibility-matrix", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    by_package = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproducibility-matrix", "--package-id", package_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Reproducibility Matrix" in render_reproducibility_matrix_markdown(matrix)
    assert by_workspace.returncode == 0, by_workspace.stderr
    assert by_package.returncode == 0, by_package.stderr
    assert "No single environment" in by_workspace.stdout


def _matrix_package(tmp_path: Path) -> tuple[str, str, Path]:
    workspace_id = "workspace-matrix"
    package_id = "replication-package-workspace-matrix"
    package_dir = tmp_path / "projects" / "matrix-project" / "experiment_workspaces" / workspace_id / "replication_packages" / package_id
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest = ReplicationManifest(
        package_id=package_id,
        environment={"resource_environment": "local"},
        commands=["python code/run.py"],
        expected_outputs=["results/metrics.json"],
        result_hashes={"results/metrics.json": "abc123"},
        random_seeds=[123],
    )
    (package_dir / "replication_manifest.json").write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
    return workspace_id, package_id, package_dir


def _write_reproduction_record(
    package_dir: Path,
    package_id: str,
    environment: str,
    status: str,
    result_comparison: dict[str, str],
) -> None:
    reproductions = package_dir / "reproductions"
    reproductions.mkdir(parents=True, exist_ok=True)
    record = ReproductionRecord(
        id=f"reproduction-{environment}-{status}",
        package_id=package_id,
        environment=environment,
        status=status,
        result_comparison=result_comparison,
        provenance=Provenance(created_by_skill="test", source_ids=[package_id, f"environment:{environment}"]),
    )
    (reproductions / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
