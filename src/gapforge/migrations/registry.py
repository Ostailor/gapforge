"""Version detection and normalization for GapForge persisted objects."""

from __future__ import annotations

from typing import Any

from gapforge.migrations.versions import (
    LATEST_STORAGE_VERSION,
    ORDERED_STORAGE_VERSIONS,
    normalize_target,
    normalize_version,
)


class MigrationRegistry:
    """Registry for known persisted-object versions and ordered migration plans."""

    def latest(self) -> str:
        return LATEST_STORAGE_VERSION

    def normalize_target(self, target_version: str) -> str:
        return normalize_target(target_version)

    def detect_project_version(self, payload: dict[str, Any]) -> str:
        raw = payload.get("gapforge_version") or payload.get("storage_version") or payload.get("version") or payload.get("schema_version")
        return normalize_version(raw)

    def detect_run_version(self, payload: dict[str, Any]) -> str:
        return self.detect_object_version("run", payload)

    def detect_object_version(self, object_type: str, payload: dict[str, Any] | list[Any], *, fallback: str = "") -> str:
        if isinstance(payload, list):
            versions = {self.detect_object_version(object_type, item, fallback=fallback) for item in payload if isinstance(item, dict)}
            versions.discard("unknown")
            return sorted(versions)[0] if len(versions) == 1 else normalize_version(fallback)
        if not isinstance(payload, dict):
            return normalize_version(fallback)
        config = payload.get("config", {})
        if not isinstance(config, dict):
            config = {}
        if object_type == "run":
            raw = (
                config.get("gapforge_version")
                or config.get("storage_version")
                or config.get("version")
                or payload.get("gapforge_version")
                or payload.get("version")
                or config.get("schema_version")
                or payload.get("schema_version")
            )
        else:
            raw = (
                payload.get("gapforge_version") or payload.get("storage_version") or payload.get("version") or payload.get("schema_version")
            )
        return normalize_version(raw or fallback)

    def migration_required(self, source_version: str, target_version: str) -> bool:
        return normalize_version(source_version) != self.normalize_target(target_version)

    def checked_versions(self) -> list[str]:
        return list(ORDERED_STORAGE_VERSIONS)


SUPPORTED_SCHEMA_VERSIONS = list(ORDERED_STORAGE_VERSIONS)
