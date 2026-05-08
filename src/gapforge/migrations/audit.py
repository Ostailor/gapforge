"""Compatibility audit for older GapForge projects and runs."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.migrations.fixtures import list_historical_migration_fixtures, load_historical_migration_fixture
from gapforge.migrations.migrators import MigrationValidationError, migrate_payload
from gapforge.migrations.registry import MigrationRegistry
from gapforge.migrations.versions import AmbiguousVersionError
from gapforge.models import CompatibilityAudit, CompatibilityAuditV2, Provenance, ResearchProject, ResearchRunState, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso

UNSAFE_NAMES = {"llm_transcripts.json", "llm_transcripts.md"}
UNSAFE_PARTS = {".gapforge_cache", "prompt_packs", "safe_bundles", "paper_packages", "task_outputs"}
UNSAFE_SUFFIXES = {".pdf", ".sqlite", ".db", ".parquet", ".zip", ".tar", ".gz", ".cache"}


class CompatibilityAuditor:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.registry = MigrationRegistry()
        self.root = config.data_dir / "migrations"
        self.root.mkdir(parents=True, exist_ok=True)

    def audit(self, *, write: bool = True, include_fixtures: bool = False) -> CompatibilityAudit:
        loaded_projects: list[str] = []
        loaded_runs: list[str] = []
        migration_required: list[str] = []
        migration_failures: list[str] = []
        warnings: list[str] = []
        for path in sorted(self.config.project_root.glob("*/project.json")):
            project_id = path.parent.name
            try:
                payload = _load_json(path)
                project = from_dict(ResearchProject, _project_load_payload(payload, project_id, path.parent))
                loaded_projects.append(project.id or project_id)
                source_version = self.registry.detect_project_version(payload)
                if self.registry.migration_required(source_version, "latest"):
                    migration_required.append(f"project:{project.id or project_id}:{source_version}->v1")
                warnings.extend(_missing_project_field_warnings(project_id, payload))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                migration_failures.append(f"project:{project_id}: {exc}")
        for path in sorted(self.config.runs_dir.glob("*/state.json")):
            run_id = path.parent.name
            try:
                payload = _load_json(path)
                state = ResearchRunState.from_dict(_run_load_payload(payload, run_id, path.parent))
                loaded_runs.append(state.run_id or run_id)
                source_version = self.registry.detect_run_version(payload)
                if self.registry.migration_required(source_version, "latest"):
                    migration_required.append(f"run:{state.run_id or run_id}:{source_version}->v1")
                warnings.extend(_missing_run_field_warnings(run_id, payload))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                migration_failures.append(f"run:{run_id}: {exc}")
        if include_fixtures:
            for fixture in list_historical_migration_fixtures(self.config):
                try:
                    result = load_historical_migration_fixture(self.config, fixture)
                    if fixture.object_type == "project":
                        loaded_projects.append(f"fixture:{result.loaded_object_id}")
                    elif fixture.object_type == "run":
                        loaded_runs.append(f"fixture:{result.loaded_object_id}")
                    else:
                        warnings.append(
                            f"fixture:{fixture.id}: loaded {fixture.object_type} `{result.loaded_object_id}`; "
                            "object type is not migrated by the project/run migration manager"
                        )
                    if self.registry.migration_required(result.detected_version, "latest"):
                        migration_required.append(f"fixture:{fixture.id}:{result.detected_version}->v1")
                    warnings.extend(f"fixture:{fixture.id}: {warning}" for warning in result.warnings)
                except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    migration_failures.append(f"fixture:{fixture.id}: {exc}")
        audit = CompatibilityAudit(
            id=f"compatibility-audit-{utc_now_compact()}",
            checked_versions=self.registry.checked_versions(),
            loaded_projects=_dedupe(loaded_projects),
            loaded_runs=_dedupe(loaded_runs),
            migration_required=_dedupe(migration_required),
            migration_failures=_dedupe(migration_failures),
            warnings=_dedupe(warnings),
            provenance=Provenance(
                created_by_skill="compatibility-audit",
                source_ids=[],
                timestamp=utc_now_iso(),
                reasoning_summary="Checked older persisted project and run objects for loadability and migration needs.",
            ),
        )
        if write:
            self.write_outputs(audit, write_release_gate=not include_fixtures)
        return audit

    def audit_v2(
        self,
        *,
        write: bool = False,
        include_fixtures: bool = True,
        include_local: bool = True,
        target_version: str = "latest",
    ) -> CompatibilityAuditV2:
        target = self.registry.normalize_target(target_version)
        fixture_results: list[dict[str, Any]] = []
        local_project_results: list[dict[str, Any]] = []
        local_run_results: list[dict[str, Any]] = []
        blockers: list[str] = []
        warnings: list[str] = []

        if include_fixtures:
            fixture_results.extend(self._audit_v2_fixtures(target))
            blockers.extend(f"fixture:{result['id']}: {result['message']}" for result in fixture_results if result.get("status") == "fail")
        if include_local:
            local_project_results.extend(self._audit_v2_local_projects(target))
            local_run_results.extend(self._audit_v2_local_runs(target))
            for result in [*local_project_results, *local_run_results]:
                if result.get("status") == "fail":
                    blockers.append(f"{result['object_type']}:{result['id']}: {result['message']}")

        fixture_safety_blockers, fixture_safety_warnings = _artifact_safety_findings(
            self.config.root / "tests" / "fixtures" / "migrations",
            curated=True,
            workspace_root=self.config.root,
        )
        local_safety_blockers: list[str] = []
        local_safety_warnings: list[str] = []
        for root in [self.config.project_root, self.config.runs_dir, self.config.data_dir]:
            root_blockers, root_warnings = _artifact_safety_findings(root, curated=False, workspace_root=self.config.root)
            local_safety_blockers.extend(root_blockers)
            local_safety_warnings.extend(root_warnings)
        blockers.extend(fixture_safety_blockers)
        warnings.extend(fixture_safety_warnings)
        warnings.extend(local_safety_warnings)
        blockers.extend(local_safety_blockers)
        blockers.extend(_cli_alias_blockers())
        warnings.extend(_result_warnings([*fixture_results, *local_project_results, *local_run_results]))

        migration_required_count = sum(
            1 for result in [*fixture_results, *local_project_results, *local_run_results] if result.get("source_version") != target
        )
        migration_failure_count = sum(
            1 for result in [*fixture_results, *local_project_results, *local_run_results] if result.get("status") == "fail"
        )
        warnings = _dedupe(warnings)
        blockers = _dedupe(blockers)
        status = (
            "fail"
            if blockers
            else "warning"
            if any(warning.startswith("ignored/generated local artifact") for warning in warnings)
            else "pass"
        )
        audit = CompatibilityAuditV2(
            id=f"compatibility-audit-v2-{utc_now_compact()}",
            target_version=target,
            fixture_results=fixture_results,
            local_project_results=local_project_results,
            local_run_results=local_run_results,
            migration_required_count=migration_required_count,
            migration_pass_count=sum(
                1 for result in [*fixture_results, *local_project_results, *local_run_results] if result.get("status") == "pass"
            ),
            migration_warning_count=len(warnings),
            migration_failure_count=migration_failure_count,
            blockers=blockers,
            warnings=warnings,
            status=status,
            provenance=Provenance(
                created_by_skill="compatibility-audit-v2",
                source_ids=[],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Checked historical fixture load and migration, local current-state loading, migration validation, "
                    "backup snapshots, artifact safety, unknown fields, CLI compatibility aliases, and report generation."
                ),
            ),
        )
        if write:
            self.write_outputs_v2(audit)
        return audit

    def write_outputs(self, audit: CompatibilityAudit, *, write_release_gate: bool = True) -> tuple[Path, Path]:
        json_path = self.root / "compatibility_audit_latest.json"
        md_path = self.root / "compatibility_audit_latest.md"
        json_path.write_text(json.dumps(to_plain(audit), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_compatibility_audit(audit), encoding="utf-8")
        if write_release_gate:
            release_dir = self.config.data_dir / "release_gate"
            release_dir.mkdir(parents=True, exist_ok=True)
            passed = not audit.migration_required and not audit.migration_failures
            release_payload = {
                "passed": passed,
                "status": "pass" if passed else "fail",
                "audit_id": audit.id,
                "migration_required": audit.migration_required,
                "migration_failures": audit.migration_failures,
                "warnings": audit.warnings,
                "report_path": str(md_path),
            }
            (release_dir / "migration_audit.json").write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        return json_path, md_path

    def write_outputs_v2(self, audit: CompatibilityAuditV2) -> tuple[Path, Path]:
        json_path = self.root / "compatibility_audit_v2_latest.json"
        md_path = self.root / "compatibility_audit_v2_latest.md"
        json_path.write_text(json.dumps(to_plain(audit), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_compatibility_audit_v2(audit), encoding="utf-8")
        release_dir = self.config.data_dir / "release_gate"
        release_dir.mkdir(parents=True, exist_ok=True)
        release_payload = {
            "passed": audit.status in {"pass", "warning"},
            "status": audit.status,
            "audit_version": 2,
            "audit_id": audit.id,
            "target_version": audit.target_version,
            "migration_required_count": audit.migration_required_count,
            "migration_pass_count": audit.migration_pass_count,
            "migration_warning_count": audit.migration_warning_count,
            "migration_failure_count": audit.migration_failure_count,
            "blockers": audit.blockers,
            "warnings": audit.warnings,
            "report_path": str(md_path),
        }
        (release_dir / "migration_audit.json").write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        return json_path, md_path

    def latest_report(self) -> str:
        v2_path = self.root / "compatibility_audit_v2_latest.json"
        if v2_path.exists():
            audit_v2 = from_dict(CompatibilityAuditV2, json.loads(v2_path.read_text(encoding="utf-8")))
            return render_compatibility_audit_v2(audit_v2)
        path = self.root / "compatibility_audit_latest.json"
        if not path.exists():
            return render_compatibility_audit(self.audit(write=True))
        audit = from_dict(CompatibilityAudit, json.loads(path.read_text(encoding="utf-8")))
        return render_compatibility_audit(audit)

    def _audit_v2_fixtures(self, target: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for fixture in list_historical_migration_fixtures(self.config):
            try:
                load_result = load_historical_migration_fixture(self.config, fixture)
                with tempfile.TemporaryDirectory(prefix=f"gapforge-{fixture.id}-") as tmp:
                    temp_config = GapForgeConfig.from_cwd(Path(tmp))
                    primary_path = _install_fixture_workspace(temp_config, self.config.root / fixture.path, fixture.primary_json)
                    source_payload = _load_json_any(primary_path)
                    source_version = self.registry.detect_object_version(fixture.object_type, source_payload)
                    from gapforge.migrations.migrate import MigrationManager

                    records = MigrationManager(temp_config).migrate_all(dry_run=False, to_version=target)
                    failures = [record for record in records if record.status == "failed"]
                    backup_count = len(list((temp_config.data_dir / "migrations" / "backups").glob("*")))
                    migrated_payload = _load_json_any(primary_path)
                    migrated_version = self.registry.detect_object_version(fixture.object_type, migrated_payload)
                    migration_report = MigrationManager(temp_config).report()
                    status = "pass"
                    message = "loaded, migrated, validated, backed up, and rendered migration report"
                    if failures:
                        status = "fail"
                        message = "; ".join(f"{record.object_type}:{record.object_id}: {record.warnings}" for record in failures)
                    elif migrated_version != target:
                        status = "fail"
                        message = f"primary payload migrated to `{migrated_version}`, expected `{target}`"
                    elif backup_count == 0:
                        status = "fail"
                        message = "no backup snapshot was created before fixture migration"
                    elif "# GapForge Migration Report" not in migration_report:
                        status = "fail"
                        message = "migration report was not generated"
                    warnings = [f"load: {warning}" for warning in load_result.warnings]
                    warnings.extend(
                        f"migration: {record.object_type}:{record.object_id}: {warning}"
                        for record in records
                        for warning in record.warnings
                    )
                    results.append(
                        {
                            "id": fixture.id,
                            "object_type": fixture.object_type,
                            "source_version": source_version,
                            "target_version": target,
                            "status": status,
                            "message": message,
                            "backup_count": backup_count,
                            "record_count": len(records),
                            "warnings": _dedupe(warnings),
                        }
                    )
            except (OSError, json.JSONDecodeError, TypeError, ValueError, AmbiguousVersionError, MigrationValidationError) as exc:
                results.append(
                    {
                        "id": fixture.id,
                        "object_type": fixture.object_type,
                        "source_version": fixture.version,
                        "target_version": target,
                        "status": "fail",
                        "message": str(exc),
                        "backup_count": 0,
                        "record_count": 0,
                        "warnings": [],
                    }
                )
        results.append(_unknown_field_probe(target))
        return results

    def _audit_v2_local_projects(self, target: str) -> list[dict[str, Any]]:
        return [
            self._audit_v2_local_payload("project", path.parent.name, path, target)
            for path in sorted(self.config.project_root.glob("*/project.json"))
        ]

    def _audit_v2_local_runs(self, target: str) -> list[dict[str, Any]]:
        return [
            self._audit_v2_local_payload("run", path.parent.name, path, target)
            for path in sorted(self.config.runs_dir.glob("*/state.json"))
        ]

    def _audit_v2_local_payload(self, object_type: str, object_id: str, path: Path, target: str) -> dict[str, Any]:
        try:
            payload = _load_json_any(path)
            if not isinstance(payload, dict):
                raise ValueError("JSON root is not an object")
            source_version = self.registry.detect_object_version(object_type, payload)
            if source_version == target:
                if object_type == "project":
                    from_dict(ResearchProject, _project_load_payload(payload, object_id, path.parent))
                elif object_type == "run":
                    ResearchRunState.from_dict(_run_load_payload(payload, object_id, path.parent))
                return {
                    "id": object_id,
                    "object_type": object_type,
                    "source_version": source_version,
                    "target_version": target,
                    "status": "pass",
                    "message": "current schema loads",
                    "warnings": [],
                }
            migrated = migrate_payload(
                object_type,
                payload,
                object_id=object_id,
                object_dir=path.parent,
                source_version=source_version,
                target_version=target,
            )
            warnings = list(migrated.warnings)
            if any("unknown fields" in change for change in migrated.changes):
                warnings.append("unknown legacy fields preserved under `_compatibility.unknown_fields`")
            return {
                "id": object_id,
                "object_type": object_type,
                "source_version": source_version,
                "target_version": target,
                "status": "warning" if warnings else "pass",
                "message": "local legacy state migrates in memory",
                "warnings": _dedupe(warnings),
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError, AmbiguousVersionError, MigrationValidationError) as exc:
            source_version = "unknown"
            try:
                payload = _load_json_any(path)
                source_version = self.registry.detect_object_version(object_type, payload)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
            generated = _is_generated_path(path, self.config.root)
            return {
                "id": object_id,
                "object_type": object_type,
                "source_version": source_version,
                "target_version": target,
                "status": "warning" if generated and source_version != target else "fail",
                "message": str(exc),
                "warnings": [str(exc)] if generated and source_version != target else [],
            }


def render_compatibility_audit(audit: CompatibilityAudit) -> str:
    passed = not audit.migration_required and not audit.migration_failures
    lines = [
        "# GapForge Compatibility Audit",
        "",
        f"- Audit: `{audit.id}`",
        f"- Passed: {str(passed).lower()}",
        f"- Checked versions: {', '.join(audit.checked_versions)}",
        f"- Loaded projects: {len(audit.loaded_projects)}",
        f"- Loaded runs: {len(audit.loaded_runs)}",
        "",
        "## Migration Required",
        "",
    ]
    lines.extend([f"- {item}" for item in audit.migration_required] or ["- none"])
    lines.extend(["", "## Migration Failures", ""])
    lines.extend([f"- {item}" for item in audit.migration_failures] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in audit.warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_compatibility_audit_v2(audit: CompatibilityAuditV2) -> str:
    lines = [
        "# GapForge Compatibility Audit V2",
        "",
        f"- Audit: `{audit.id}`",
        f"- Status: `{audit.status}`",
        f"- Target version: `{audit.target_version}`",
        f"- Fixture results: {len(audit.fixture_results)}",
        f"- Local project results: {len(audit.local_project_results)}",
        f"- Local run results: {len(audit.local_run_results)}",
        f"- Migration required count: {audit.migration_required_count}",
        f"- Migration passes: {audit.migration_pass_count}",
        f"- Migration warnings: {audit.migration_warning_count}",
        f"- Migration failures: {audit.migration_failure_count}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {blocker}" for blocker in audit.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in audit.warnings] or ["- none"])
    lines.extend(["", "## Fixtures", ""])
    lines.extend(_render_result_line(result) for result in audit.fixture_results)
    lines.extend(["", "## Local Projects", ""])
    lines.extend([_render_result_line(result) for result in audit.local_project_results] or ["- none"])
    lines.extend(["", "## Local Runs", ""])
    lines.extend([_render_result_line(result) for result in audit.local_run_results] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _render_result_line(result: dict[str, Any]) -> str:
    return (
        f"- `{result.get('object_type', 'object')}:{result.get('id', 'unknown')}` "
        f"{result.get('source_version', 'unknown')}->{result.get('target_version', 'unknown')}: "
        f"`{result.get('status', 'unknown')}` - {result.get('message', '')}"
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root is not an object")
    return payload


def _load_json_any(path: Path) -> dict[str, Any] | list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, (dict, list)):
        raise ValueError("JSON root is not an object or array")
    return payload


def _install_fixture_workspace(config: GapForgeConfig, fixture_dir: Path, primary_json: str) -> Path:
    primary_parts = Path(primary_json).parts
    if primary_parts[0] == "run":
        source = fixture_dir / primary_json
        payload = _load_json(source)
        run_id = str(payload["run_id"])
        destination = config.runs_dir / run_id
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination / "state.json")
        return destination / "state.json"
    if primary_parts[0] == "project":
        project_source = fixture_dir / "project"
        payload = _load_json(project_source / "project.json")
        destination = config.project_root / str(payload["id"])
        shutil.copytree(project_source, destination)
        return destination / Path(*primary_parts[1:])
    if primary_parts[0] == "pilot":
        source = fixture_dir / primary_json
        payload = _load_json(source)
        pilot_id = str(payload["pilot_id"])
        destination = config.data_dir / "pilots" / pilot_id
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination / "pilot_run_record.json")
        return destination / "pilot_run_record.json"
    raise ValueError(f"Unsupported fixture primary path: {primary_json}")


def _unknown_field_probe(target: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="gapforge-unknown-field-") as tmp:
        run_dir = Path(tmp) / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "run_id": "unknown-field-probe",
            "topic": {"text": "Probe", "slug": "probe", "created_at": ""},
            "run_dir": str(run_dir),
            "config": {"gapforge_version": "v0.8", "schema_version": 2},
            "claims": [],
            "legacy_scoring_notes": {"kept": True},
        }
        migrated = migrate_payload(
            "run",
            payload,
            object_id="unknown-field-probe",
            object_dir=run_dir,
            source_version="v0.8",
            target_version=target,
        )
        if isinstance(migrated.payload, dict):
            compatibility = migrated.payload.get("_compatibility", {})
            if isinstance(compatibility, dict):
                unknown = compatibility.get("unknown_fields", {})
                if isinstance(unknown, dict) and "legacy_scoring_notes" in unknown:
                    return {
                        "id": "unknown-field-probe",
                        "object_type": "run",
                        "source_version": "v0.8",
                        "target_version": target,
                        "status": "pass",
                        "message": "unknown legacy field preserved in compatibility namespace",
                        "backup_count": 0,
                        "record_count": 0,
                        "warnings": [],
                    }
        return {
            "id": "unknown-field-probe",
            "object_type": "run",
            "source_version": "v0.8",
            "target_version": target,
            "status": "fail",
            "message": "unknown legacy field was not preserved",
            "backup_count": 0,
            "record_count": 0,
            "warnings": [],
        }


def _artifact_safety_findings(root: Path, *, curated: bool, workspace_root: Path) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not root.exists():
        return blockers, warnings
    for path in root.rglob("*"):
        if not path.is_file() or _is_audit_output(path):
            continue
        unsafe_reason = _unsafe_artifact_reason(path)
        if not unsafe_reason:
            continue
        relative = _relative_to_root(path, workspace_root)
        message = f"{relative}: {unsafe_reason}"
        if curated:
            blockers.append(f"curated fixture contains unsafe artifact: {message}")
        elif _is_generated_path(path, workspace_root):
            warnings.append(f"ignored/generated local artifact not counted as curated v1 evidence: {message}")
        else:
            blockers.append(f"local non-generated unsafe artifact: {message}")
    return _dedupe(blockers), _dedupe(warnings)


def _unsafe_artifact_reason(path: Path) -> str:
    parts = set(path.parts)
    if path.name in UNSAFE_NAMES:
        return "model transcript artifact"
    if path.suffix.lower() in UNSAFE_SUFFIXES:
        return f"unsafe suffix `{path.suffix.lower()}`"
    if parts & UNSAFE_PARTS:
        return f"unsafe generated path component `{sorted(parts & UNSAFE_PARTS)[0]}`"
    return ""


def _is_generated_path(path: Path, workspace_root: Path) -> bool:
    relative = _relative_to_root(path, workspace_root)
    return relative.startswith(("runs/", "projects/", "campaigns/", "data/", ".gapforge_cache/")) or any(
        part in UNSAFE_PARTS for part in Path(relative).parts
    )


def _is_audit_output(path: Path) -> bool:
    return path.name in {
        "artifacts_audit.json",
        "artifacts_audit.md",
        "compatibility_audit_latest.json",
        "compatibility_audit_latest.md",
        "compatibility_audit_v2_latest.json",
        "compatibility_audit_v2_latest.md",
    }


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _cli_alias_blockers() -> list[str]:
    try:
        from gapforge.cli import build_parser
        from gapforge.cli_audit import DEPRECATED_COMMANDS, RECOMMENDED_ALIASES

        choices = _parser_choice_names(build_parser())
        return [
            f"CLI compatibility alias `{alias}` is neither resolvable nor documented as deprecated"
            for alias in sorted(RECOMMENDED_ALIASES)
            if alias not in choices and alias not in DEPRECATED_COMMANDS
        ]
    except (ImportError, AttributeError, ValueError):
        return []


def _parser_choice_names(parser: Any) -> set[str]:
    names: set[str] = set()
    for action in getattr(parser, "_actions", []):
        choices = getattr(action, "_name_parser_map", None)
        if isinstance(choices, dict):
            names.update(str(name) for name in choices)
    return names


def _result_warnings(results: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for result in results:
        for warning in result.get("warnings", []):
            warnings.append(f"{result.get('object_type', 'object')}:{result.get('id', 'unknown')}: {warning}")
    return warnings


def _missing_project_field_warnings(project_id: str, payload: dict[str, Any]) -> list[str]:
    required = ["id", "name", "root_dir", "created_at", "updated_at", "run_ids"]
    return [
        f"project:{project_id}: missing field `{field}`; default will be used on migration" for field in required if field not in payload
    ]


def _missing_run_field_warnings(run_id: str, payload: dict[str, Any]) -> list[str]:
    required = ["run_id", "topic", "run_dir", "config", "papers", "claims", "gaps", "experiments"]
    return [f"run:{run_id}: missing field `{field}`; default will be used on migration" for field in required if field not in payload]


def _project_load_payload(payload: dict[str, Any], project_id: str, project_dir: Path) -> dict[str, Any]:
    updated = dict(payload)
    updated.setdefault("id", project_id)
    updated.setdefault("name", project_id)
    updated.setdefault("root_dir", str(project_dir))
    return updated


def _run_load_payload(payload: dict[str, Any], run_id: str, run_dir: Path) -> dict[str, Any]:
    updated = dict(payload)
    updated.setdefault("run_id", run_id)
    updated.setdefault(
        "topic",
        {
            "text": run_id,
            "slug": run_id,
            "created_at": "",
        },
    )
    updated.setdefault("run_dir", str(run_dir))
    updated.setdefault("config", {})
    return updated


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
