from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.migrations import (
    CompatibilityAuditor,
    MigrationManager,
    build_migration_blocker_report,
    render_compatibility_audit,
    render_compatibility_audit_v2,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_migration_blocker_report_identifies_v08_and_unknown_fixtures(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.8")
    unknown_project_dir = config.project_root / "legacy-project"
    unknown_project_dir.mkdir(parents=True, exist_ok=True)
    (unknown_project_dir / "project.json").write_text(
        json.dumps({"id": "legacy-project", "name": "Legacy project"}, indent=2) + "\n",
        encoding="utf-8",
    )
    unknown_run_dir = config.runs_dir / "legacy-run"
    unknown_run_dir.mkdir(parents=True, exist_ok=True)
    (unknown_run_dir / "state.json").write_text(
        json.dumps(
            {
                "run_id": "legacy-run",
                "topic": {"text": "Legacy", "slug": "legacy", "created_at": ""},
                "run_dir": str(unknown_run_dir),
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

    report = build_migration_blocker_report(config)

    assert report.passed is False
    assert report.failing_requirement == "migration_audit_passed"
    assert any(blocker.failing_object_type == "run" and blocker.affected_versions == ["v0.8"] for blocker in report.blockers)
    assert any(blocker.failing_object_type == "project" and blocker.affected_versions == ["unknown"] for blocker in report.blockers)
    assert any(blocker.failing_object_type == "fixture coverage" and blocker.report_only for blocker in report.blockers)


def test_migration_blockers_cli_json_and_write_report(tmp_path: Path) -> None:
    _version_fixture(tmp_path, "v0.8")

    json_result = _run_cli(tmp_path, "migration-blockers", "--json")

    assert json_result.returncode == 1, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["passed"] is False
    assert payload["failing_requirement"] == "migration_audit_passed"
    assert any(blocker["failing_object_type"] == "run" for blocker in payload["blockers"])

    report_result = _run_cli(tmp_path, "migration-blockers", "--write-report")
    report_path = tmp_path / "docs" / "V0_9_1_MIGRATION_BLOCKER_AUDIT.md"

    assert report_result.returncode == 1, report_result.stderr
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "This is a focused blocker audit" in report
    assert "It does not claim v1 readiness" in report


def test_migration_backup_created(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.4")
    manager = MigrationManager(config)

    project_record = manager.migrate_project("project-v04")
    run_record = manager.migrate_run("run-v04")

    assert project_record.status == "migrated"
    assert run_record.status == "migrated"
    project_backups = list((config.data_dir / "migrations" / "backups").glob("project-project-v04-*"))
    run_backups = list((config.data_dir / "migrations" / "backups").glob("run-run-v04-*"))
    assert project_backups
    assert run_backups
    project_backup = json.loads((project_backups[0] / "project.json").read_text(encoding="utf-8"))
    run_backup = json.loads((run_backups[0] / "state.json").read_text(encoding="utf-8"))
    assert project_backup["gapforge_version"] == "v0.4"
    assert run_backup["config"]["gapforge_version"] == "v0.4"
    assert json.loads((config.project_root / "project-v04" / "project.json").read_text(encoding="utf-8"))["gapforge_version"] == "v1"
    state = json.loads((config.runs_dir / "run-v04" / "state.json").read_text(encoding="utf-8"))
    assert state["config"]["gapforge_version"] == "v1"


def test_ambiguous_migration_fails_without_mutation_or_backup(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    run_dir = config.runs_dir / "ambiguous-run"
    run_dir.mkdir(parents=True, exist_ok=True)
    original = {
        "run_id": "ambiguous-run",
        "topic": {"text": "Ambiguous", "slug": "ambiguous", "created_at": ""},
        "run_dir": str(run_dir),
        "claims": [{"id": "claim-1", "text": "Preserve this claim."}],
    }
    state_path = run_dir / "state.json"
    state_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown source version"):
        MigrationManager(config).migrate_run("ambiguous-run")

    assert json.loads(state_path.read_text(encoding="utf-8")) == original
    assert not list((config.data_dir / "migrations" / "backups").glob("run-ambiguous-run-*"))


def test_migrate_all_cli_dry_run_and_apply(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v0.5")

    dry_run = _run_cli(tmp_path, "migrate-all", "--dry-run")

    assert dry_run.returncode == 0, dry_run.stderr
    dry_run_payload = json.loads(dry_run.stdout)
    assert {record["status"] for record in dry_run_payload} == {"planned"}
    project_before = json.loads((config.project_root / "project-v05" / "project.json").read_text(encoding="utf-8"))
    assert project_before["gapforge_version"] == "v0.5"

    applied = _run_cli(tmp_path, "migrate-all", "--apply")

    assert applied.returncode == 0, applied.stderr
    applied_payload = json.loads(applied.stdout)
    assert {record["status"] for record in applied_payload} == {"migrated"}
    project = json.loads((config.project_root / "project-v05" / "project.json").read_text(encoding="utf-8"))
    run = json.loads((config.runs_dir / "run-v05" / "state.json").read_text(encoding="utf-8"))
    assert project["gapforge_version"] == "v1"
    assert run["config"]["gapforge_version"] == "v1"


def test_migrate_all_dry_run_warns_for_generated_unknown_local_state(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_dir = config.project_root / "generated-legacy-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(json.dumps({"id": "generated-legacy-project"}) + "\n", encoding="utf-8")

    dry_run = _run_cli(tmp_path, "migrate-all", "--dry-run")

    assert dry_run.returncode == 0, dry_run.stderr
    payload = json.loads(dry_run.stdout)
    assert payload[0]["status"] == "warning"
    assert "ignored/generated local object" in payload[0]["warnings"][0]


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


def test_compatibility_audit_v2_fixture_pass_leads_to_audit_pass() -> None:
    config = GapForgeConfig.from_cwd(REPO_ROOT)

    audit = CompatibilityAuditor(config).audit_v2(write=False, include_fixtures=True, include_local=False)

    assert audit.status == "pass"
    assert audit.migration_failure_count == 0
    assert len(audit.fixture_results) >= 10
    assert all(result["status"] == "pass" for result in audit.fixture_results)


def test_compatibility_audit_v2_migration_failure_blocks(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    fixture_root = tmp_path / "tests" / "fixtures" / "migrations" / "v0_bad_ambiguous"
    run_dir = fixture_root / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (fixture_root / "manifest.json").write_text(
        json.dumps(
            {
                "id": "v0_bad_ambiguous",
                "version": "v0.1",
                "object_type": "run",
                "primary_json": "run/state.json",
                "safe_to_commit": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "state.json").write_text(
        json.dumps({"run_id": "bad-run", "topic": {"text": "Bad", "slug": "bad", "created_at": ""}}, indent=2) + "\n",
        encoding="utf-8",
    )

    audit = CompatibilityAuditor(config).audit_v2(write=False, include_fixtures=True, include_local=False)

    assert audit.status == "fail"
    assert audit.migration_failure_count == 1
    assert any("v0_bad_ambiguous" in blocker for blocker in audit.blockers)


def test_compatibility_audit_v2_generated_artifact_warning_does_not_block(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v1")
    transcript = config.runs_dir / "run-v1" / "llm_transcripts.json"
    transcript.write_text('{"generated": true}\n', encoding="utf-8")

    audit = CompatibilityAuditor(config).audit_v2(write=True, include_fixtures=False, include_local=True)
    release_payload = json.loads((config.data_dir / "release_gate" / "migration_audit.json").read_text(encoding="utf-8"))

    assert audit.status == "warning"
    assert audit.blockers == []
    assert any("ignored/generated local artifact" in warning for warning in audit.warnings)
    assert release_payload["passed"] is True
    assert release_payload["status"] == "warning"


def test_compatibility_audit_v2_report_renders(tmp_path: Path) -> None:
    config = _version_fixture(tmp_path, "v1")
    audit = CompatibilityAuditor(config).audit_v2(write=True, include_fixtures=False, include_local=True)
    rendered = render_compatibility_audit_v2(audit)

    assert "# GapForge Compatibility Audit V2" in rendered
    assert "Local Runs" in rendered
    assert (config.data_dir / "migrations" / "compatibility_audit_v2_latest.md").exists()
    assert (config.data_dir / "release_gate" / "migration_audit.json").exists()


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


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "gapforge.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
