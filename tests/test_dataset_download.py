from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.datasets.cache import clean_dataset_cache, dataset_cache_info, render_dataset_cache_info
from gapforge.datasets.consent import DatasetConsentManager
from gapforge.datasets.download import DatasetDownloadManager
from gapforge.datasets.registry import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import ExperimentProtocol
from gapforge.project_memory import ProjectMemoryManager


def test_small_mocked_download_works_and_hashes(tmp_path: Path) -> None:
    config, workspace_id = _download_workspace(tmp_path)
    source = tmp_path / "small.csv"
    source.write_text("text,label,split\nalpha,0,test\n", encoding="utf-8")
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Small Benchmark Dataset",
        path=tmp_path / "missing.csv",
        dataset_type="benchmark",
        source_url=source.as_uri(),
        license="MIT",
    )

    record = DatasetDownloadManager(config).download(dataset.id)
    updated = DatasetRegistry(config).load_dataset(dataset.id)

    assert record.status == "downloaded"
    assert record.bytes_downloaded == source.stat().st_size
    assert record.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert Path(record.local_path).exists()
    assert updated.local_path == record.local_path
    assert ".gapforge_cache" in record.local_path


def test_large_download_requires_consent_then_accepts(tmp_path: Path, monkeypatch) -> None:
    config, workspace_id = _download_workspace(tmp_path)
    source = tmp_path / "large.csv"
    source.write_text("text,label,split\n" + "x,0,test\n" * 10, encoding="utf-8")
    monkeypatch.setenv("GAPFORGE_DATASET_LARGE_DOWNLOAD_BYTES", "10")
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Large Benchmark Dataset",
        path=tmp_path / "missing-large.csv",
        dataset_type="benchmark",
        source_url=source.as_uri(),
        license="MIT",
    )
    manager = DatasetDownloadManager(config)

    skipped = manager.download(dataset.id)
    downloaded = manager.download(dataset.id, accept_license=True, user="tester")

    assert skipped.status == "skipped"
    assert "Explicit consent" in skipped.error
    assert downloaded.status == "downloaded"
    assert DatasetConsentManager(config).has_consent(dataset.id)


def test_license_missing_warns_without_forcing_small_download_consent(tmp_path: Path) -> None:
    config, workspace_id = _download_workspace(tmp_path)
    source = tmp_path / "unknown-license.csv"
    source.write_text("text,label,split\nalpha,0,test\n", encoding="utf-8")
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Unknown License Dataset",
        path=tmp_path / "missing-unknown.csv",
        dataset_type="benchmark",
        source_url=source.as_uri(),
        license="",
    )

    plan = DatasetDownloadManager(config).build_plan(dataset.id)

    assert plan.consent_required is False
    assert "Dataset license is missing" in "\n".join(plan.safety_warnings)


def test_manual_required_dataset_produces_instructions(tmp_path: Path) -> None:
    config, workspace_id = _download_workspace(tmp_path)
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Manual Dataset",
        path=tmp_path / "manual-missing.csv",
        dataset_type="benchmark",
        source="provider portal",
        source_url="",
        license="restricted terms",
    )
    manager = DatasetDownloadManager(config)

    plan = manager.build_plan(dataset.id)
    record = manager.download(dataset.id, accept_license=True)

    assert plan.requires_manual_download is True
    assert plan.consent_required is True
    assert "Manual download required" in "\n".join(plan.safety_warnings)
    assert record.status == "manual_required"


def test_cache_info_and_clean_render(tmp_path: Path) -> None:
    config, workspace_id = _download_workspace(tmp_path)
    source = tmp_path / "cache.csv"
    source.write_text("text,label,split\nalpha,0,test\n", encoding="utf-8")
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="Cache Dataset",
        path=tmp_path / "missing-cache.csv",
        dataset_type="benchmark",
        source_url=source.as_uri(),
        license="MIT",
    )
    DatasetDownloadManager(config).download(dataset.id)

    info = dataset_cache_info(config)
    rendered = render_dataset_cache_info(info)
    cleaned = clean_dataset_cache(config)

    assert info["files"] >= 2
    assert "Dataset Cache" in rendered
    assert cleaned["after"]["files"] == 0


def test_dataset_download_cli_plan_download_consent_cache(tmp_path: Path) -> None:
    _config, workspace_id = _download_workspace(tmp_path)
    source = tmp_path / "cli.csv"
    source.write_text("text,label,split\nalpha,0,test\n", encoding="utf-8")
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
            "CLI Download Dataset",
            "--path",
            str(tmp_path / "missing-cli.csv"),
            "--dataset-type",
            "benchmark",
            "--source-url",
            source.as_uri(),
            "--license",
            "MIT",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert registered.returncode == 0, registered.stderr

    dataset_id = json.loads(registered.stdout)["id"]

    planned = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-download-plan", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    consent = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-consent", "--dataset-id", dataset_id, "--accept", "--user", "tester"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    downloaded = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-download", "--dataset-id", dataset_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    cache = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dataset-cache-info"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert planned.returncode == 0, planned.stderr
    assert consent.returncode == 0, consent.stderr
    assert downloaded.returncode == 0, downloaded.stderr
    assert cache.returncode == 0, cache.stderr
    assert "Dataset Download Plan" in planned.stdout
    assert "Dataset Consent" in consent.stdout
    assert "Status: `downloaded`" in downloaded.stdout
    assert "Dataset Cache" in cache.stdout


def _download_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Dataset Download Project")
    protocol = ExperimentProtocol(
        id="protocol-1",
        direction_id="direction-1",
        linked_experiment_plan_id="experiment-1",
        objective="Validate dataset download management.",
        hypothesis="Explicit download records preserve dataset provenance.",
    )
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id="direction-1")
    return config, workspace.id
