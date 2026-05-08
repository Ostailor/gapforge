from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.migrations import (
    CompatibilityAuditor,
    HistoricalMigrationFixture,
    MigrationManager,
    list_historical_migration_fixtures,
    load_historical_migration_fixture,
)
from gapforge.migrations.registry import MigrationRegistry

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "migrations"
EXPECTED_FIXTURES = [
    "v0_1_run",
    "v0_2_fulltext_run",
    "v0_3_project_memory",
    "v0_4_campaign",
    "v0_5_real_literature_campaign",
    "v0_6_experiment_workspace",
    "v0_7_benchmark_replication",
    "v0_8_manuscript_package",
    "v0_9_pilot_project",
]
UNSAFE_NAMES = {"llm_transcripts.json", "llm_transcripts.md"}
UNSAFE_PARTS = {".gapforge_cache", "prompt_packs", "safe_bundles", "paper_packages", "task_outputs"}
UNSAFE_SUFFIXES = {".pdf", ".sqlite", ".db", ".parquet", ".zip", ".tar", ".gz", ".cache"}


def test_historical_fixture_suite_is_complete_and_safe() -> None:
    config = GapForgeConfig.from_cwd(REPO_ROOT)
    fixtures = list_historical_migration_fixtures(config)

    assert [fixture.id for fixture in fixtures] == EXPECTED_FIXTURES
    assert [fixture.version for fixture in fixtures] == [f"v0.{index}" for index in range(1, 10)]

    for fixture in fixtures:
        fixture_path = REPO_ROOT / fixture.path
        assert fixture.safe_to_commit is True
        assert (fixture_path / fixture.primary_json).exists()
        assert _directory_size(fixture_path) < 20_000
        for path in fixture_path.rglob("*"):
            if not path.is_file():
                continue
            assert path.suffix.lower() not in UNSAFE_SUFFIXES, path
            assert path.name not in UNSAFE_NAMES, path
            assert not (set(path.parts) & UNSAFE_PARTS), path


def test_historical_fixtures_load_and_versions_are_recognized() -> None:
    config = GapForgeConfig.from_cwd(REPO_ROOT)
    registry = MigrationRegistry()

    for fixture in list_historical_migration_fixtures(config):
        result = load_historical_migration_fixture(config, fixture)

        assert result.loaded_object_id
        assert registry.detect_run_version({"config": {"gapforge_version": result.detected_version}}) == fixture.version
        assert result.detected_version == fixture.version
        assert all("missing" in warning or "not migrated" not in warning for warning in result.warnings)


def test_historical_fixtures_migrate_to_current_schema_with_migrate_all(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(REPO_ROOT)

    for fixture in list_historical_migration_fixtures(config):
        workspace_config = GapForgeConfig.from_cwd(tmp_path / fixture.id)
        primary_path = _install_fixture_workspace(workspace_config, fixture)
        before = json.loads(primary_path.read_text(encoding="utf-8"))

        records = MigrationManager(workspace_config).migrate_all(dry_run=False)

        assert any(record.status == "migrated" and record.source_version == fixture.version for record in records), fixture.id
        assert not [record for record in records if record.status == "failed"]
        migrated = json.loads(primary_path.read_text(encoding="utf-8"))
        assert _payload_version(migrated, fixture.object_type) == "v1"
        _assert_protected_payload_preserved(before, migrated)


def test_compatibility_audit_with_fixtures_reports_warnings_not_crashes() -> None:
    config = GapForgeConfig.from_cwd(REPO_ROOT)

    audit = CompatibilityAuditor(config).audit(write=False, include_fixtures=True)

    for fixture_id in EXPECTED_FIXTURES:
        assert any(f"fixture:{fixture_id}:" in item for item in audit.migration_required)
    assert not any(item.startswith("fixture:") for item in audit.migration_failures)
    assert any("missing artifact reference" in warning for warning in audit.warnings)
    assert any("object type is not migrated" in warning for warning in audit.warnings)


def test_migration_fixture_clis() -> None:
    listed = _run_cli("migration-fixtures-list", "--json")
    assert listed.returncode == 0, listed.stderr
    listed_payload = json.loads(listed.stdout)
    assert [item["id"] for item in listed_payload] == EXPECTED_FIXTURES

    audited = _run_cli("compatibility-audit", "--fixtures", "--json")
    assert audited.returncode == 1
    audit_payload = json.loads(audited.stdout)
    assert any(item.startswith("fixture:v0_1_run:v0.1->v1") for item in audit_payload["migration_required"])
    assert not any(item.startswith("fixture:") for item in audit_payload["migration_failures"])

    audited_v2 = _run_cli("compatibility-audit", "--v2", "--fixtures", "--json")
    assert audited_v2.returncode == 0, audited_v2.stderr
    audit_v2_payload = json.loads(audited_v2.stdout)
    assert audit_v2_payload["status"] == "pass"
    assert audit_v2_payload["migration_failure_count"] == 0


def _install_fixture_workspace(config: GapForgeConfig, fixture: HistoricalMigrationFixture) -> Path:
    fixture_dir = REPO_ROOT / fixture.path
    primary_parts = Path(fixture.primary_json).parts
    if primary_parts[0] == "run":
        state_path = fixture_dir / fixture.primary_json
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        run_id = str(payload["run_id"])
        destination = config.runs_dir / run_id
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(state_path, destination / "state.json")
        return destination / "state.json"
    if primary_parts[0] == "project":
        project_source = fixture_dir / "project"
        project_payload = json.loads((project_source / "project.json").read_text(encoding="utf-8"))
        destination = config.project_root / str(project_payload["id"])
        shutil.copytree(project_source, destination)
        return destination / Path(*primary_parts[1:])
    if primary_parts[0] == "pilot":
        pilot_path = fixture_dir / fixture.primary_json
        payload = json.loads(pilot_path.read_text(encoding="utf-8"))
        pilot_id = str(payload["pilot_id"])
        destination = config.data_dir / "pilots" / pilot_id
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pilot_path, destination / "pilot_run_record.json")
        return destination / "pilot_run_record.json"
    raise AssertionError(f"Unsupported fixture primary path: {fixture.primary_json}")


def _copy_project_fixture(config: GapForgeConfig, project_dir: Path) -> str:
    payload = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    project_id = payload["id"]
    destination = config.project_root / project_id
    shutil.copytree(project_dir, destination)
    return str(project_id)


def _payload_version(payload: object, object_type: str) -> str:
    if object_type == "run" and isinstance(payload, dict) and isinstance(payload.get("config"), dict):
        return str(payload["config"].get("gapforge_version", ""))
    if isinstance(payload, dict):
        return str(payload.get("gapforge_version", ""))
    return ""


PROTECTED_KEYS = {
    "artifact_paths",
    "blockers",
    "claims",
    "evidence_spans",
    "paper_artifacts",
    "sections",
}


def _assert_protected_payload_preserved(before: object, after: object) -> None:
    if isinstance(before, dict):
        assert isinstance(after, dict)
        for key, value in before.items():
            if key in PROTECTED_KEYS:
                assert key in after
                if isinstance(value, list):
                    assert isinstance(after[key], list)
                    assert len(after[key]) >= len(value)
                elif isinstance(value, dict):
                    assert isinstance(after[key], dict)
                    for protected_item_key in value:
                        assert protected_item_key in after[key]
            _assert_protected_payload_preserved(value, after.get(key))
    elif isinstance(before, list):
        assert isinstance(after, list)
        assert len(after) >= len(before)
        for index, item in enumerate(before):
            _assert_protected_payload_preserved(item, after[index])


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "gapforge.cli", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
