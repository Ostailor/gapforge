"""Migration commands for older GapForge project and run state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.migrations.audit import CompatibilityAuditor
from gapforge.migrations.backups import create_backup_snapshot
from gapforge.migrations.migrators import MigrationValidationError, migrate_payload
from gapforge.migrations.registry import MigrationRegistry
from gapforge.migrations.versions import AmbiguousVersionError
from gapforge.models import MigrationRecord, Provenance, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


class MigrationManager:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.registry = MigrationRegistry()
        self.root = config.data_dir / "migrations"
        self.records_dir = self.root / "records"
        self.backup_dir = self.root / "backups"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def migrate_project(self, project_id: str, *, to_version: str = "latest") -> MigrationRecord:
        project_dir = self.config.project_root / project_id
        project_path = project_dir / "project.json"
        if not project_path.exists():
            raise FileNotFoundError(f"No project found for {project_id}")
        record = self._migrate_path(
            object_type="project",
            object_id=project_id,
            primary_path=project_path,
            backup_source=project_dir,
            to_version=to_version,
            apply=True,
        )
        CompatibilityAuditor(self.config).audit(write=True)
        return record

    def migrate_run(self, run_id: str, *, to_version: str = "latest") -> MigrationRecord:
        run_dir = self.config.runs_dir / run_id
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No run found for {run_id}")
        record = self._migrate_path(
            object_type="run",
            object_id=run_id,
            primary_path=state_path,
            backup_source=run_dir,
            to_version=to_version,
            apply=True,
        )
        CompatibilityAuditor(self.config).audit(write=True)
        return record

    def migrate_all(self, *, dry_run: bool = True, to_version: str = "latest") -> list[MigrationRecord]:
        records: list[MigrationRecord] = []
        for item in self._discover_objects():
            object_type, object_id, primary_path, backup_source = item
            try:
                record = self._migrate_path(
                    object_type=object_type,
                    object_id=object_id,
                    primary_path=primary_path,
                    backup_source=backup_source,
                    to_version=to_version,
                    apply=not dry_run,
                )
            except (AmbiguousVersionError, MigrationValidationError, ValueError) as exc:
                payload = _load_json_any(primary_path)
                source = self.registry.detect_object_version(object_type, payload)
                status = "failed"
                warnings = [str(exc)]
                if dry_run and _is_generated_migration_path(primary_path, self.config.root):
                    status = "warning"
                    warnings = [f"ignored/generated local object was not migrated during dry run: {exc}"]
                record = self._record(
                    source_version=source,
                    target_version=self.registry.normalize_target(to_version),
                    object_type=object_type,
                    object_id=object_id,
                    status=status,
                    changes=[],
                    warnings=warnings,
                )
                if not dry_run:
                    self._save_record(record)
            records.append(record)
        if not dry_run:
            CompatibilityAuditor(self.config).audit(write=True)
        return records

    def load_records(self) -> list[MigrationRecord]:
        records = []
        for path in sorted(self.records_dir.glob("*.json")):
            try:
                records.append(from_dict(MigrationRecord, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def report(self) -> str:
        audit_text = CompatibilityAuditor(self.config).latest_report()
        return render_migration_report(self.load_records(), audit_text)

    def _migrate_path(
        self,
        *,
        object_type: str,
        object_id: str,
        primary_path: Path,
        backup_source: Path,
        to_version: str,
        apply: bool,
    ) -> MigrationRecord:
        payload = _load_json_any(primary_path)
        source = self.registry.detect_object_version(object_type, payload)
        target = self.registry.normalize_target(to_version)
        if source == target:
            return self._record(
                source_version=source,
                target_version=target,
                object_type=object_type,
                object_id=object_id,
                status="skipped",
                changes=[],
                warnings=["object already at target version"],
            )
        migrated = migrate_payload(
            object_type,
            payload,
            object_id=object_id,
            object_dir=primary_path.parent,
            source_version=source,
            target_version=target,
        )
        changes = list(migrated.changes)
        if apply:
            backup = create_backup_snapshot(backup_source, self.backup_dir, object_type, object_id)
            changes.insert(0, f"backup created at {backup}")
            primary_path.write_text(json.dumps(migrated.payload, indent=2) + "\n", encoding="utf-8")
        else:
            changes.insert(0, "dry run; no files mutated")
        record = self._record(
            source_version=source,
            target_version=target,
            object_type=object_type,
            object_id=object_id,
            status="migrated" if apply else "planned",
            changes=changes,
            warnings=migrated.warnings,
        )
        if apply:
            self._save_record(record)
        return record

    def _discover_objects(self) -> list[tuple[str, str, Path, Path]]:
        objects: list[tuple[str, str, Path, Path]] = []
        for path in sorted(self.config.project_root.glob("*/project.json")):
            objects.append(("project", path.parent.name, path, path.parent))
        for path in sorted(self.config.runs_dir.glob("*/state.json")):
            objects.append(("run", path.parent.name, path, path.parent))
        for path in sorted(self.config.project_root.glob("*/campaigns/*/campaign.json")):
            objects.append(("campaign", path.parent.name, path, path.parent))
        for path in sorted(self.config.project_root.glob("*/experiment_workspaces/*/workspace.json")):
            objects.append(("workspace", path.parent.name, path, path.parent))
        for path in sorted(self.config.project_root.glob("*/experiment_workspaces/*/replication_package/replication_manifest.json")):
            objects.append(("replication", path.parent.name, path, path.parent))
        for path in sorted(self.config.project_root.glob("*/benchmark_suites.json")):
            objects.append(("benchmark", f"{path.parent.name}-benchmark-suites", path, path))
        for path in sorted(self.config.project_root.glob("*/manuscripts/*/manuscript.json")):
            objects.append(("manuscript", path.parent.name, path, path.parent))
        for path in sorted(self.config.data_dir.glob("pilots/*/pilot_run_record.json")):
            objects.append(("pilot", path.parent.name, path, path.parent))
        return objects

    def _record(
        self,
        *,
        source_version: str,
        target_version: str,
        object_type: str,
        object_id: str,
        status: str,
        changes: list[str],
        warnings: list[str],
    ) -> MigrationRecord:
        return MigrationRecord(
            id=f"migration-{object_type}-{object_id}-{utc_now_compact()}",
            source_version=source_version,
            target_version=target_version,
            object_type=object_type,
            object_id=object_id,
            status=status,
            changes=changes,
            warnings=warnings,
            provenance=Provenance(
                created_by_skill="migration",
                source_ids=[object_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Migrated persisted object after creating a whole-directory backup.",
            ),
        )

    def _save_record(self, record: MigrationRecord) -> Path:
        path = self.records_dir / f"{record.id}.json"
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        return path


def render_migration_report(records: list[MigrationRecord], audit_text: str = "") -> str:
    lines = ["# GapForge Migration Report", ""]
    if audit_text:
        lines.extend(["## Latest Compatibility Audit", "", audit_text.rstrip(), ""])
    lines.extend(["## Migration Records", ""])
    if not records:
        lines.append("- none")
    for record in records:
        lines.extend(
            [
                f"### `{record.id}`",
                "",
                f"- Object: `{record.object_type}:{record.object_id}`",
                f"- Status: `{record.status}`",
                f"- Source version: `{record.source_version}`",
                f"- Target version: `{record.target_version}`",
                "",
                "Changes:",
                "",
            ]
        )
        lines.extend([f"- {change}" for change in record.changes] or ["- none"])
        lines.extend(["", "Warnings:", ""])
        lines.extend([f"- {warning}" for warning in record.warnings] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_json_any(path: Path) -> dict[str, Any] | list[Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, (dict, list)):
        raise ValueError("JSON root is not an object or array")
    return payload


def _is_generated_migration_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    if not relative.parts:
        return False
    return relative.parts[0] in {"runs", "projects", "campaigns", "data"}
