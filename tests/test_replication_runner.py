from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code import ExperimentCodeScaffolderV2
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import ExperimentProtocol, ExperimentRunManifest, ReplicationManifest, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication import ReplicationPackageExporter, ReproductionRunner
from gapforge.replication.runner import render_reproduction_record_markdown


def test_reproduction_dry_run_records_commands_without_running(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    _rewrite_manifest_for_independent_reproduction(package_dir)
    output = package_dir / "results" / "reproduced_metrics.json"
    if output.exists():
        output.unlink()

    record = ReproductionRunner(config).reproduce(package_dir, dry_run=True)

    assert record.status == "planned"
    assert record.commands_run
    assert not output.exists()


def test_fixture_reproduction_passes(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    _rewrite_manifest_for_independent_reproduction(package_dir)

    record = ReproductionRunner(config).reproduce(package_dir)

    assert record.status == "pass"
    assert record.result_comparison["results/reproduced_metrics.json"] == "match"
    assert (package_dir / "reproductions" / f"{record.id}.json").exists()


def test_missing_dataset_fails_with_clear_message(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    _rewrite_manifest_for_independent_reproduction(package_dir)
    (package_dir / "data" / "fixture.csv").unlink()

    record = ReproductionRunner(config).reproduce(package_dir)

    assert record.status == "fail"
    assert any("dataset" in error.lower() and "fixture.csv" in error for error in record.errors)


def test_hash_mismatch_fails(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    _rewrite_manifest_for_independent_reproduction(package_dir, expected_payload={"metric_results": []})

    record = ReproductionRunner(config).reproduce(package_dir)

    assert record.status == "fail"
    assert record.result_comparison["results/reproduced_metrics.json"] == "hash_mismatch"


def test_reproduction_report_and_cli_render(tmp_path: Path) -> None:
    config, workspace_id, _execution_id = _replication_execution(tmp_path)
    package = ReplicationPackageExporter(config).export_workspace(workspace_id)
    package_dir = Path(package.manifest_path).parent
    _rewrite_manifest_for_independent_reproduction(package_dir)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    run_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproduce", "--package-path", str(package_dir)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    record_path = next((package_dir / "reproductions").glob("reproduction-*.json"))
    status_payload = json.loads(record_path.read_text(encoding="utf-8"))
    status_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "reproduce-status", "--reproduction-id", status_payload["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    record = ReproductionRunner(config).load_record(status_payload["id"])

    assert run_result.returncode == 0, run_result.stderr
    assert "Reproduction Record" in run_result.stdout
    assert "Reproduction Record" in render_reproduction_record_markdown(record)
    assert status_result.returncode == 0, status_result.stderr
    assert "Status: `pass`" in status_result.stdout


def _rewrite_manifest_for_independent_reproduction(
    package_dir: Path,
    *,
    expected_payload: dict | None = None,
    actual_payload: dict | None = None,
) -> None:
    manifest_path = package_dir / "replication_manifest.json"
    manifest = from_dict(ReplicationManifest, json.loads(manifest_path.read_text(encoding="utf-8")))
    default_payload = {"metric_results": [{"metric_id": "false positive rate", "value": 0.0, "sample_size": 100}]}
    expected_payload = expected_payload or default_payload
    actual_payload = actual_payload or default_payload
    output = package_dir / "results" / "reproduced_metrics.json"
    expected_output = package_dir / "results" / "expected_reproduced_metrics.json"
    expected_output.write_text(json.dumps(expected_payload) + "\n", encoding="utf-8")
    script = package_dir / "code" / "reproduce_fixture.py"
    script.write_text(
        "from pathlib import Path\n"
        "import json\n"
        "dataset = Path('data/fixture.csv')\n"
        "if not dataset.exists():\n"
        "    raise SystemExit('missing dataset: data/fixture.csv')\n"
        f"Path({str(output.relative_to(package_dir))!r}).write_text({json.dumps(actual_payload)!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest.commands = [f"{sys.executable} {script.relative_to(package_dir)}"]
    manifest.expected_outputs = [str(output.relative_to(package_dir))]
    manifest.result_hashes = {str(output.relative_to(package_dir)): _sha256(expected_output)}
    manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")


def _replication_execution(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Reproduction Runner Project")
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-reproduction-runner",
            direction_id="direction-reproduction-runner",
            linked_experiment_plan_id="experiment-reproduction-runner",
            objective="Attempt package reproduction.",
            hypothesis="Replication package commands can be rerun.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(
        project_id=program.project.id,
        direction_id="direction-reproduction-runner",
    )
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="fixture examples",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        source_url="https://example.test/dataset",
        intended_use="Reproduction fixture.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    ExperimentCodeScaffolderV2(config).scaffold(workspace.id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_reproduction_metrics.py"
    payload = json.dumps({"metric_results": [{"metric_id": "false positive rate", "value": 0.0, "sample_size": 100}]})
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({payload!r} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace.id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0]}
    _write_manifest(workspace, manifest)
    execution = ExperimentRunner(config).run(workspace_id=workspace.id, manifest_id=manifest.id).execution
    return config, workspace.id, execution.id


def _write_manifest(workspace, manifest: ExperimentRunManifest) -> None:
    path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
