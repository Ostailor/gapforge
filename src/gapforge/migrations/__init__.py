"""Schema migration and compatibility audit helpers."""

from gapforge.migrations.audit import CompatibilityAuditor, render_compatibility_audit
from gapforge.migrations.migrate import MigrationManager, render_migration_report
from gapforge.migrations.registry import LATEST_SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS, MigrationRegistry

__all__ = [
    "LATEST_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CompatibilityAuditor",
    "MigrationManager",
    "MigrationRegistry",
    "render_compatibility_audit",
    "render_migration_report",
]
