"""Schema migration and compatibility audit helpers."""

from gapforge.migrations.audit import CompatibilityAuditor, render_compatibility_audit, render_compatibility_audit_v2
from gapforge.migrations.blockers import (
    MigrationBlockerReport,
    build_migration_blocker_report,
    render_migration_blocker_report,
    report_to_json,
    write_migration_blocker_report,
)
from gapforge.migrations.fixtures import (
    HistoricalFixtureLoadResult,
    HistoricalMigrationFixture,
    list_historical_migration_fixtures,
    load_historical_migration_fixture,
    render_migration_fixtures_list,
)
from gapforge.migrations.migrate import MigrationManager, render_migration_report
from gapforge.migrations.migrators import MigrationResult, MigrationValidationError, migrate_payload
from gapforge.migrations.registry import SUPPORTED_SCHEMA_VERSIONS, MigrationRegistry
from gapforge.migrations.versions import LATEST_SCHEMA_VERSION, AmbiguousVersionError, migration_plan

__all__ = [
    "LATEST_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CompatibilityAuditor",
    "HistoricalFixtureLoadResult",
    "HistoricalMigrationFixture",
    "MigrationBlockerReport",
    "MigrationManager",
    "MigrationRegistry",
    "MigrationResult",
    "MigrationValidationError",
    "AmbiguousVersionError",
    "build_migration_blocker_report",
    "list_historical_migration_fixtures",
    "load_historical_migration_fixture",
    "migrate_payload",
    "migration_plan",
    "render_compatibility_audit",
    "render_compatibility_audit_v2",
    "render_migration_blocker_report",
    "render_migration_fixtures_list",
    "render_migration_report",
    "report_to_json",
    "write_migration_blocker_report",
]
