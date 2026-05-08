"""Validation checks for migrated GapForge persisted objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MigrationValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


REQUIRED_FIELDS = {
    "run": ["run_id", "topic", "run_dir", "config"],
    "project": ["id", "name", "root_dir", "run_ids", "gapforge_version"],
    "campaign": ["id", "project_id", "topic", "gapforge_version"],
    "workspace": ["id", "project_id", "direction_id", "root_dir", "gapforge_version"],
    "manuscript": ["manuscript", "gapforge_version"],
    "pilot": ["id", "pilot_id", "status", "gapforge_version"],
    "replication": ["package_id", "gapforge_version"],
    "benchmark": ["gapforge_version"],
}

PROTECTED_LIST_KEYS = {
    "agent_actual_run_attestations",
    "agent_repair_records",
    "agent_run_records",
    "agent_validation_results",
    "artifact_paths",
    "baseline_results",
    "blockers",
    "caption",
    "captions",
    "citation_uses",
    "claim_uses",
    "claims",
    "evidence_spans",
    "experiment_execution_records",
    "experiment_result_artifacts",
    "experiments",
    "gaps",
    "human_reviews",
    "novelty_assessments",
    "paper_artifacts",
    "proposed_method_results",
    "references",
    "review_ids",
    "reviewer_objections",
    "reviewer_summaries",
    "sections",
    "tables",
}


def validate_migrated_payload(
    object_type: str,
    before: dict[str, Any] | list[Any],
    after: dict[str, Any] | list[Any],
    *,
    target_version: str,
) -> MigrationValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if isinstance(after, dict):
        for field_name in REQUIRED_FIELDS.get(object_type, []):
            value = after.get(field_name)
            if field_name not in after or value is None or value == "":
                errors.append(f"missing required field `{field_name}` after migration")
        actual_version = _payload_version(after, object_type)
        if actual_version != target_version:
            errors.append(f"expected migrated version `{target_version}`, found `{actual_version}`")
    elif object_type == "benchmark":
        for index, item in enumerate(after):
            if not isinstance(item, dict):
                errors.append(f"benchmark item {index} is not an object")
            elif item.get("gapforge_version") != target_version:
                errors.append(f"benchmark item {index} missing target version `{target_version}`")
    else:
        errors.append("migrated payload root is not an object")
    errors.extend(_protected_loss_errors(before, after))
    return MigrationValidationResult(ok=not errors, errors=errors, warnings=warnings)


def _payload_version(payload: dict[str, Any], object_type: str) -> str:
    config = payload.get("config", {})
    if object_type == "run" and isinstance(config, dict):
        return str(config.get("gapforge_version", ""))
    return str(payload.get("gapforge_version", ""))


def _protected_loss_errors(before: object, after: object, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(before, dict):
        if not isinstance(after, dict):
            return [f"protected data under `{path or '<root>'}` would be lost"]
        for key, value in before.items():
            child_path = f"{path}.{key}" if path else key
            if key in PROTECTED_LIST_KEYS and key not in after:
                errors.append(f"protected field `{child_path}` was dropped")
                continue
            if key in PROTECTED_LIST_KEYS and isinstance(value, list):
                migrated_value = after.get(key)
                if not isinstance(migrated_value, list) or len(migrated_value) < len(value):
                    errors.append(f"protected list `{child_path}` lost entries")
            errors.extend(_protected_loss_errors(value, after.get(key), child_path))
    elif isinstance(before, list):
        if not isinstance(after, list) or len(after) < len(before):
            if any(_contains_protected_data(item) for item in before):
                errors.append(f"protected list under `{path or '<root>'}` lost entries")
            return errors
        for index, item in enumerate(before):
            errors.extend(_protected_loss_errors(item, after[index], f"{path}[{index}]"))
    return errors


def _contains_protected_data(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in PROTECTED_LIST_KEYS for key in value) or any(_contains_protected_data(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_protected_data(item) for item in value)
    return False
