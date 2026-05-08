"""Versioned payload migrators for GapForge persisted objects."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.manuscript.models import ManuscriptState
from gapforge.migrations.validation import validate_migrated_payload
from gapforge.migrations.versions import migration_plan, normalize_target
from gapforge.models import (
    ExperimentWorkspace,
    PilotRunRecord,
    ResearchCampaign,
    ResearchProject,
    ResearchRunState,
)
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class MigrationResult:
    payload: dict[str, Any] | list[Any]
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


KNOWN_FIELDS = {
    "run": set(ResearchRunState.__dataclass_fields__),
    "project": set(ResearchProject.__dataclass_fields__) | {"gapforge_version"},
    "campaign": set(ResearchCampaign.__dataclass_fields__) | {"gapforge_version"},
    "workspace": set(ExperimentWorkspace.__dataclass_fields__) | {"gapforge_version"},
    "manuscript": set(ManuscriptState.__dataclass_fields__) | {"gapforge_version"},
    "pilot": set(PilotRunRecord.__dataclass_fields__) | {"gapforge_version"},
    "replication": {
        "package_id",
        "code_version",
        "dataset_records",
        "dataset_download_instructions",
        "environment",
        "commands",
        "expected_outputs",
        "result_hashes",
        "random_seeds",
        "gapforge_version",
    },
    "benchmark": {
        "id",
        "name",
        "description",
        "benchmark_ids",
        "required_tasks",
        "optional_tasks",
        "source_profile",
        "gapforge_version",
    },
}

RENAMED_FIELDS = {
    "run": {"id": "run_id", "artifacts": "paper_artifacts", "evidence": "evidence_spans", "reviews": "human_reviews"},
    "project": {"project_id": "id", "title": "name", "runs": "run_ids"},
    "campaign": {"name": "title", "profile": "source_profile"},
    "workspace": {"path": "root_dir", "state": "status"},
    "manuscript": {"project": "manuscript"},
    "pilot": {"name": "pilot_id"},
    "replication": {"id": "package_id"},
    "benchmark": {},
}


class MigrationValidationError(ValueError):
    """Raised when a migrated payload fails validation."""


def migrate_payload(
    object_type: str,
    payload: dict[str, Any] | list[Any],
    *,
    object_id: str,
    object_dir: Path,
    source_version: str,
    target_version: str = "latest",
) -> MigrationResult:
    target = normalize_target(target_version)
    plan = migration_plan(source_version, target)
    migrated = copy.deepcopy(payload)
    changes: list[str] = []
    warnings: list[str] = []
    for from_version, to_version in plan:
        migrated = _apply_step(
            object_type,
            migrated,
            object_id=object_id,
            object_dir=object_dir,
            target_version=to_version,
            changes=changes,
            warnings=warnings,
        )
        changes.append(f"applied {object_type} migration {from_version}->{to_version}")
    validation = validate_migrated_payload(object_type, payload, migrated, target_version=target)
    warnings.extend(validation.warnings)
    if not validation.ok:
        raise MigrationValidationError("; ".join(validation.errors))
    return MigrationResult(payload=migrated, changes=_dedupe(changes), warnings=_dedupe(warnings))


def _apply_step(
    object_type: str,
    payload: dict[str, Any] | list[Any],
    *,
    object_id: str,
    object_dir: Path,
    target_version: str,
    changes: list[str],
    warnings: list[str],
) -> dict[str, Any] | list[Any]:
    if object_type == "benchmark" and isinstance(payload, list):
        return [
            _migrate_mapping(
                object_type,
                item,
                object_id=object_id,
                object_dir=object_dir,
                target_version=target_version,
                changes=changes,
                warnings=warnings,
            )
            if isinstance(item, dict)
            else item
            for item in payload
        ]
    if not isinstance(payload, dict):
        raise MigrationValidationError(f"{object_type} payload root is not an object")
    return _migrate_mapping(
        object_type,
        payload,
        object_id=object_id,
        object_dir=object_dir,
        target_version=target_version,
        changes=changes,
        warnings=warnings,
    )


def _migrate_mapping(
    object_type: str,
    payload: dict[str, Any],
    *,
    object_id: str,
    object_dir: Path,
    target_version: str,
    changes: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    updated = dict(payload)
    _convert_renamed_fields(object_type, updated, changes=changes)
    if object_type == "run":
        _migrate_run(updated, object_id, object_dir, target_version, changes)
    elif object_type == "project":
        _migrate_project(updated, object_id, object_dir, target_version, changes)
    elif object_type == "campaign":
        _migrate_campaign(updated, object_id, target_version, changes)
    elif object_type == "workspace":
        _migrate_workspace(updated, object_id, object_dir, target_version, changes)
    elif object_type == "manuscript":
        _migrate_manuscript(updated, object_id, target_version, changes)
    elif object_type == "pilot":
        _migrate_pilot(updated, object_id, target_version, changes)
    elif object_type == "replication":
        _migrate_replication(updated, object_id, target_version, changes)
    elif object_type == "benchmark":
        _migrate_benchmark(updated, object_id, target_version, changes)
    else:
        raise MigrationValidationError(f"unsupported object type `{object_type}`")
    _preserve_unknown_fields(object_type, updated, changes=changes)
    warnings.extend(_missing_artifact_warnings(object_dir, updated))
    return updated


def _migrate_run(payload: dict[str, Any], run_id: str, run_dir: Path, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "run_id", run_id, changes)
    if not payload.get("run_dir") or not Path(str(payload.get("run_dir"))).is_absolute():
        payload["run_dir"] = str(run_dir)
        changes.append("filled run field `run_dir`")
    if not isinstance(payload.get("topic"), dict):
        payload["topic"] = {"text": run_id, "slug": slugify(run_id), "created_at": ""}
        changes.append("filled run field `topic`")
    for field_name in [
        "papers",
        "paper_artifacts",
        "paper_sections",
        "evidence_spans",
        "claims",
        "gaps",
        "experiments",
        "experiment_execution_records",
        "experiment_result_artifacts",
        "reviewer_objections",
        "reviewer_summaries",
        "human_reviews",
        "provenance",
    ]:
        _set_default(payload, field_name, [], changes)
    config = payload.get("config")
    if not isinstance(config, dict):
        config = {}
        changes.append("created run config object")
    config["schema_version"] = 2
    config["gapforge_version"] = target_version
    payload["config"] = config
    changes.append(f"set run config gapforge_version to {target_version}")


def _migrate_project(payload: dict[str, Any], project_id: str, project_dir: Path, target_version: str, changes: list[str]) -> None:
    now = utc_now_iso()
    _set_default(payload, "id", project_id, changes)
    _set_default(payload, "name", project_id, changes)
    _set_default(payload, "description", "", changes)
    if not payload.get("root_dir") or not Path(str(payload.get("root_dir"))).is_absolute():
        payload["root_dir"] = str(project_dir)
        changes.append("filled project field `root_dir`")
    _set_default(payload, "created_at", now, changes)
    _set_default(payload, "updated_at", now, changes)
    _set_default(payload, "active_topic_ids", [], changes)
    _set_default(payload, "run_ids", [], changes)
    _set_default(payload, "corpus_id", f"{project_id}-corpus", changes)
    _set_default(payload, "status", "active", changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set project gapforge_version to {target_version}")


def _migrate_campaign(payload: dict[str, Any], campaign_id: str, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "id", campaign_id, changes)
    _set_default(payload, "project_id", "", changes)
    _set_default(payload, "topic", payload.get("title") or campaign_id, changes)
    _set_default(payload, "title", payload.get("topic") or campaign_id, changes)
    _set_default(payload, "status", "planned", changes)
    _set_default(payload, "mode", "deterministic", changes)
    _set_default(payload, "source_profile", "generic", changes)
    _set_default(payload, "budget_id", "small", changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set campaign gapforge_version to {target_version}")


def _migrate_workspace(payload: dict[str, Any], workspace_id: str, workspace_dir: Path, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "id", workspace_id, changes)
    _set_default(payload, "project_id", "", changes)
    _set_default(payload, "campaign_id", "", changes)
    _set_default(payload, "direction_id", "", changes)
    _set_default(payload, "experiment_protocol_id", "", changes)
    if not payload.get("root_dir") or not Path(str(payload.get("root_dir"))).is_absolute():
        payload["root_dir"] = str(workspace_dir)
        changes.append("filled workspace field `root_dir`")
    _set_default(payload, "status", "planned", changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set workspace gapforge_version to {target_version}")


def _migrate_manuscript(payload: dict[str, Any], manuscript_id: str, target_version: str, changes: list[str]) -> None:
    manuscript = payload.get("manuscript")
    if not isinstance(manuscript, dict):
        manuscript = {
            "id": manuscript_id,
            "project_id": "",
            "campaign_id": "",
            "direction_id": "",
            "workspace_id": "",
            "title": manuscript_id,
        }
        payload["manuscript"] = manuscript
        changes.append("filled manuscript state object")
    _set_default(manuscript, "id", manuscript_id, changes)
    _set_default(manuscript, "project_id", "", changes)
    _set_default(manuscript, "campaign_id", "", changes)
    _set_default(manuscript, "direction_id", "", changes)
    _set_default(manuscript, "workspace_id", "", changes)
    _set_default(manuscript, "title", manuscript_id, changes)
    for field_name in ["sections", "claim_uses", "citation_uses", "figure_ids", "table_ids", "review_ids", "provenance"]:
        _set_default(payload, field_name, [], changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set manuscript gapforge_version to {target_version}")


def _migrate_pilot(payload: dict[str, Any], pilot_id: str, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "id", pilot_id, changes)
    _set_default(payload, "pilot_id", pilot_id, changes)
    _set_default(payload, "status", "planned", changes)
    _set_default(payload, "outcome_type", "unknown", changes)
    _set_default(payload, "artifact_paths", {}, changes)
    _set_default(payload, "blockers", [], changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set pilot gapforge_version to {target_version}")


def _migrate_replication(payload: dict[str, Any], package_id: str, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "package_id", package_id, changes)
    _set_default(payload, "dataset_records", [], changes)
    _set_default(payload, "dataset_download_instructions", [], changes)
    _set_default(payload, "commands", [], changes)
    _set_default(payload, "expected_outputs", [], changes)
    _set_default(payload, "result_hashes", {}, changes)
    _set_default(payload, "random_seeds", [], changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set replication gapforge_version to {target_version}")


def _migrate_benchmark(payload: dict[str, Any], benchmark_id: str, target_version: str, changes: list[str]) -> None:
    _set_default(payload, "id", benchmark_id, changes)
    _set_default(payload, "name", benchmark_id, changes)
    payload["gapforge_version"] = target_version
    changes.append(f"set benchmark gapforge_version to {target_version}")


def _convert_renamed_fields(object_type: str, payload: dict[str, Any], *, changes: list[str]) -> None:
    for old_name, new_name in RENAMED_FIELDS.get(object_type, {}).items():
        if old_name in payload and new_name not in payload:
            payload[new_name] = payload[old_name]
            changes.append(f"converted renamed field `{old_name}` to `{new_name}`")


def _preserve_unknown_fields(object_type: str, payload: dict[str, Any], *, changes: list[str]) -> None:
    known = KNOWN_FIELDS.get(object_type, set()) | set(RENAMED_FIELDS.get(object_type, {})) | {"_compatibility"}
    unknown = {key: copy.deepcopy(value) for key, value in payload.items() if key not in known}
    if not unknown:
        return
    compatibility = payload.get("_compatibility")
    if not isinstance(compatibility, dict):
        compatibility = {}
    existing = compatibility.get("unknown_fields")
    if not isinstance(existing, dict):
        existing = {}
    for key, value in unknown.items():
        existing.setdefault(key, value)
    compatibility["unknown_fields"] = existing
    payload["_compatibility"] = compatibility
    changes.append("copied unknown fields into `_compatibility.unknown_fields`")


def _set_default(payload: dict[str, Any], key: str, value: Any, changes: list[str]) -> None:
    if key not in payload or payload.get(key) is None or payload.get(key) == "":
        payload[key] = value
        changes.append(f"filled field `{key}`")


def _missing_artifact_warnings(root: Path, payload: object) -> list[str]:
    warnings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"local_path", "path", "artifact_path"} and isinstance(value, str) and value:
                candidate = root / value
                if not candidate.exists():
                    warnings.append(f"missing artifact reference `{value}`")
            else:
                warnings.extend(_missing_artifact_warnings(root, value))
    elif isinstance(payload, list):
        for item in payload:
            warnings.extend(_missing_artifact_warnings(root, item))
    return warnings


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
