"""Compatibility audit for older GapForge projects and runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.migrations.registry import MigrationRegistry
from gapforge.models import CompatibilityAudit, Provenance, ResearchProject, ResearchRunState, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


class CompatibilityAuditor:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.registry = MigrationRegistry()
        self.root = config.data_dir / "migrations"
        self.root.mkdir(parents=True, exist_ok=True)

    def audit(self, *, write: bool = True) -> CompatibilityAudit:
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
            self.write_outputs(audit)
        return audit

    def write_outputs(self, audit: CompatibilityAudit) -> tuple[Path, Path]:
        json_path = self.root / "compatibility_audit_latest.json"
        md_path = self.root / "compatibility_audit_latest.md"
        json_path.write_text(json.dumps(to_plain(audit), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_compatibility_audit(audit), encoding="utf-8")
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

    def latest_report(self) -> str:
        path = self.root / "compatibility_audit_latest.json"
        if not path.exists():
            return render_compatibility_audit(self.audit(write=True))
        audit = from_dict(CompatibilityAudit, json.loads(path.read_text(encoding="utf-8")))
        return render_compatibility_audit(audit)


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


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root is not an object")
    return payload


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
