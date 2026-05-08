"""Migration commands for older GapForge project and run state."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.migrations.audit import CompatibilityAuditor
from gapforge.migrations.registry import MigrationRegistry
from gapforge.models import MigrationRecord, Provenance, ResearchProject, ResearchRunState, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


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
        target = self.registry.normalize_target(to_version)
        project_dir = self.config.project_root / project_id
        project_path = project_dir / "project.json"
        if not project_path.exists():
            raise FileNotFoundError(f"No project found for {project_id}")
        payload = _load_json(project_path)
        source = self.registry.detect_project_version(payload)
        backup = self._backup_dir(project_dir, "project", project_id)
        changes = [f"backup created at {backup}"]
        warnings = _missing_project_warnings(payload)
        payload = _upgrade_project_payload(payload, project_id, project_dir, target, changes)
        project_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        project = from_dict(ResearchProject, payload)
        program = ProjectMemoryManager(self.config).load_project(project_id)
        program.project = project
        ProjectMemoryManager(self.config).save_project(program)
        record = self._record(
            source_version=source,
            target_version=target,
            object_type="project",
            object_id=project_id,
            status="migrated",
            changes=changes,
            warnings=warnings,
        )
        self._save_record(record)
        CompatibilityAuditor(self.config).audit(write=True)
        return record

    def migrate_run(self, run_id: str, *, to_version: str = "latest") -> MigrationRecord:
        target = self.registry.normalize_target(to_version)
        run_dir = self.config.runs_dir / run_id
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No run found for {run_id}")
        payload = _load_json(state_path)
        source = self.registry.detect_run_version(payload)
        backup = self._backup_dir(run_dir, "run", run_id)
        changes = [f"backup created at {backup}"]
        warnings = _missing_run_warnings(payload)
        payload = _upgrade_run_payload(payload, run_id, run_dir, target, changes)
        state = ResearchRunState.from_dict(payload)
        ResearchStateManager(self.config).save_run(state)
        record = self._record(
            source_version=source,
            target_version=target,
            object_type="run",
            object_id=run_id,
            status="migrated",
            changes=changes,
            warnings=warnings,
        )
        self._save_record(record)
        CompatibilityAuditor(self.config).audit(write=True)
        return record

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

    def _backup_dir(self, source: Path, object_type: str, object_id: str) -> Path:
        destination = self.backup_dir / f"{object_type}-{object_id}-{utc_now_compact()}"
        suffix = 2
        candidate = destination
        while candidate.exists():
            candidate = destination.with_name(f"{destination.name}-{suffix}")
            suffix += 1
        shutil.copytree(source, candidate)
        return candidate

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


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root is not an object")
    return payload


def _upgrade_project_payload(
    payload: dict[str, Any],
    project_id: str,
    project_dir: Path,
    target: str,
    changes: list[str],
) -> dict[str, Any]:
    updated = dict(payload)
    defaults: dict[str, Any] = {
        "id": project_id,
        "name": project_id,
        "description": "",
        "root_dir": str(project_dir),
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "active_topic_ids": [],
        "run_ids": [],
        "corpus_id": f"{project_id}-corpus",
        "status": "active",
    }
    for key, value in defaults.items():
        if key not in updated or updated.get(key) in {None, ""}:
            updated[key] = value
            changes.append(f"filled project field `{key}`")
    updated["gapforge_version"] = target
    changes.append(f"set project gapforge_version to {target}")
    return updated


def _upgrade_run_payload(
    payload: dict[str, Any],
    run_id: str,
    run_dir: Path,
    target: str,
    changes: list[str],
) -> dict[str, Any]:
    updated = dict(payload)
    if "run_id" not in updated or not updated.get("run_id"):
        updated["run_id"] = run_id
        changes.append("filled run field `run_id`")
    if "run_dir" not in updated or not updated.get("run_dir"):
        updated["run_dir"] = str(run_dir)
        changes.append("filled run field `run_dir`")
    if "topic" not in updated:
        updated["topic"] = {"text": run_id, "slug": run_id, "created_at": ""}
        changes.append("filled run field `topic`")
    if "config" not in updated or not isinstance(updated.get("config"), dict):
        updated["config"] = {}
        changes.append("created run config object")
    config = dict(updated["config"])
    config["schema_version"] = 2
    config["gapforge_version"] = target
    updated["config"] = config
    changes.append(f"set run config gapforge_version to {target}")
    return updated


def _missing_project_warnings(payload: dict[str, Any]) -> list[str]:
    fields = ["id", "name", "root_dir", "created_at", "updated_at", "run_ids"]
    return [f"project field `{field}` was missing before migration" for field in fields if field not in payload]


def _missing_run_warnings(payload: dict[str, Any]) -> list[str]:
    fields = ["run_id", "topic", "run_dir", "config", "papers", "claims", "gaps", "experiments"]
    return [f"run field `{field}` was missing before migration" for field in fields if field not in payload]
