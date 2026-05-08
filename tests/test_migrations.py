from __future__ import annotations

import json
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.migrations import CompatibilityAuditor, MigrationManager, render_compatibility_audit


def test_compatibility_audit_loads_v04_fixture(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.4")

    audit = CompatibilityAuditor(config).audit()

    assert "project-v04" in audit.loaded_projects
    assert "run-v04" in audit.loaded_runs
    assert any("project:project-v04:v0.4->v1" == item for item in audit.migration_required)
    assert audit.migration_failures == []


def test_compatibility_audit_loads_v05_fixture(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.5")

    audit = CompatibilityAuditor(config).audit()

    assert "project-v05" in audit.loaded_projects
    assert "run-v05" in audit.loaded_runs
    assert any(item.endswith(":v0.5->v1") for item in audit.migration_required)
    assert audit.migration_failures == []


def test_compatibility_audit_loads_v06_fixture(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.6")

    audit = CompatibilityAuditor(config).audit()

    assert "project-v06" in audit.loaded_projects
    assert "run-v06" in audit.loaded_runs
    assert any(item.endswith(":v0.6->v1") for item in audit.migration_required)
    assert audit.migration_failures == []


def test_compatibility_audit_loads_v07_fixture(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.7")

    audit = CompatibilityAuditor(config).audit()

    assert "project-v07" in audit.loaded_projects
    assert "run-v07" in audit.loaded_runs
    assert any(item.endswith(":v0.7->v1") for item in audit.migration_required)
    assert audit.migration_failures == []


def test_migration_backup_created(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.4")
    manager = MigrationManager(config)

    project_record = manager.migrate_project("project-v04")
    run_record = manager.migrate_run("run-v04")

    assert project_record.status == "migrated"
    assert run_record.status == "migrated"
    assert list((config.data_dir / "migrations" / "backups").glob("project-project-v04-*"))
    assert list((config.data_dir / "migrations" / "backups").glob("run-run-v04-*"))
    assert json.loads((config.project_root / "project-v04" / "project.json").read_text(encoding="utf-8"))["gapforge_version"] == "v1"
    state = json.loads((config.runs_dir / "run-v04" / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["gapforge_version"] == "v1"


def test_compatibility_audit_report_renders(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.5")
    audit = CompatibilityAuditor(config).audit()

    rendered = render_compatibility_audit(audit)
    report = MigrationManager(config).report()

    assert "# GapForge Compatibility Audit" in rendered
    assert "project-v05" in rendered
    assert "# GapForge Migration Report" in report
    assert "Latest Compatibility Audit" in report


def test_compatibility_audit_marks_v1_migration_audit_passed_after_migration(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.6")
    manager = MigrationManager(config)
    manager.migrate_project("project-v06")
    manager.migrate_run("run-v06")

    audit = CompatibilityAuditor(config).audit()
    release_payload = json.loads((config.data_dir / "release_gate" / "migration_audit.json").read_text(encoding="utf-8"))

    assert audit.migration_required == []
    assert release_payload["passed"] is True


@pytest.mark.parametrize("version", ["v0.4", "v0.5", "v0.6", "v0.7"])
def test_migrate_preserves_existing_artifacts(tmp_path: Path, version: str) -> None:
    config = _version_fixture(tmp_path, version)
    suffix = version.replace(".", "")
    artifact = config.project_root / f"project-{suffix}" / "artifact.txt"
    artifact.write_text("preserve me\n", encoding="utf-8")

    MigrationManager(config).migrate_project(f"project-{suffix}")

    assert artifact.read_text(encoding="utf-8") == "preserve me\n"


def _version_fixture(tmp_path: Path, version: str) -> GapForgeConfig:
    config = GapForgeConfig.from_cwd(tmp_path)
    suffix = version.replace(".", "")
    project_dir = config.project_root / f"project-{suffix}"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        json.dumps(
            {
                "id": f"project-{suffix}",
                "name": f"Project {version}",
                "gapforge_version": version,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = config.runs_dir / f"run-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(
        json.dumps(
            {
                "run_id": f"run-{suffix}",
                "topic": {"text": f"Topic {version}", "slug": f"topic-{suffix}", "created_at": ""},
                "run_dir": str(run_dir),
                "config": {"schema_version": 1, "gapforge_version": version},
                "papers": [],
                "claims": [],
                "gaps": [],
                "experiments": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config
