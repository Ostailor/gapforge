"""Version ordering helpers for GapForge storage migrations."""

from __future__ import annotations

LATEST_SCHEMA_VERSION = "latest"
LATEST_STORAGE_VERSION = "v1"
ORDERED_STORAGE_VERSIONS = ["v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7", "v0.8", "v0.9", "v1"]


class AmbiguousVersionError(ValueError):
    """Raised when a persisted object has no safe source-version signal."""


def normalize_version(raw: object) -> str:
    if raw is None or raw == "":
        return "unknown"
    if isinstance(raw, int):
        return "v0.4" if raw <= 1 else "v0.8"
    text = str(raw).strip().lower()
    if text == "latest":
        return LATEST_STORAGE_VERSION
    if text in {"1", "schema-1"}:
        return "v0.4"
    if text in {"2", "schema-2"}:
        return "v0.8"
    if text.startswith("0."):
        return f"v{text}"
    if text.startswith("v"):
        return text
    return text


def normalize_target(target_version: str) -> str:
    if target_version in {"", "latest"}:
        return LATEST_STORAGE_VERSION
    return normalize_version(target_version)


def migration_plan(source_version: str, target_version: str = "latest") -> list[tuple[str, str]]:
    source = normalize_version(source_version)
    target = normalize_target(target_version)
    if source == "unknown":
        raise AmbiguousVersionError("Cannot migrate object with unknown source version")
    if source not in ORDERED_STORAGE_VERSIONS:
        raise AmbiguousVersionError(f"Unsupported source version: {source}")
    if target not in ORDERED_STORAGE_VERSIONS:
        raise AmbiguousVersionError(f"Unsupported target version: {target}")
    source_index = ORDERED_STORAGE_VERSIONS.index(source)
    target_index = ORDERED_STORAGE_VERSIONS.index(target)
    if source_index > target_index:
        raise AmbiguousVersionError(f"Cannot downgrade from {source} to {target}")
    versions = ORDERED_STORAGE_VERSIONS
    return [(versions[index], versions[index + 1]) for index in range(source_index, target_index)]
