"""Version detection and normalization for GapForge persisted objects."""

from __future__ import annotations

from typing import Any

LATEST_SCHEMA_VERSION = "latest"
LATEST_STORAGE_VERSION = "v1"
SUPPORTED_SCHEMA_VERSIONS = ["v0.4", "v0.5", "v0.6", "v0.7", "v0.8", "v0.9", "v1"]


class MigrationRegistry:
    """Small registry for known persisted-object versions."""

    def latest(self) -> str:
        return LATEST_STORAGE_VERSION

    def normalize_target(self, target_version: str) -> str:
        if target_version in {"", "latest"}:
            return self.latest()
        return _normalize_version(target_version)

    def detect_project_version(self, payload: dict[str, Any]) -> str:
        raw = payload.get("gapforge_version") or payload.get("storage_version") or payload.get("version") or payload.get("schema_version")
        return _normalize_version(raw)

    def detect_run_version(self, payload: dict[str, Any]) -> str:
        config = payload.get("config", {})
        if not isinstance(config, dict):
            config = {}
        raw = (
            config.get("gapforge_version")
            or config.get("storage_version")
            or config.get("version")
            or payload.get("gapforge_version")
            or payload.get("version")
            or config.get("schema_version")
            or payload.get("schema_version")
        )
        return _normalize_version(raw)

    def migration_required(self, source_version: str, target_version: str) -> bool:
        return _normalize_version(source_version) != self.normalize_target(target_version)

    def checked_versions(self) -> list[str]:
        return list(SUPPORTED_SCHEMA_VERSIONS)


def _normalize_version(raw: object) -> str:
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
