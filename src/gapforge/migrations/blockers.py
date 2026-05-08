"""Focused migration blocker reporting for v0.9.1 readiness work."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.migrations.audit import CompatibilityAuditor
from gapforge.migrations.fixtures import list_historical_migration_fixtures
from gapforge.models import CompatibilityAudit
from gapforge.state import utc_now_iso

DEFAULT_BLOCKER_REPORT_PATH = Path("docs") / "V0_9_1_MIGRATION_BLOCKER_AUDIT.md"


@dataclass(slots=True)
class MigrationBlocker:
    failing_requirement: str
    failing_command: str
    failing_object_type: str
    affected_versions: list[str]
    root_cause: str
    required_fix: str
    tests_to_add: list[str]
    data_mutation_required: bool
    v1_readiness_impact: str
    object_count: int = 0
    example_objects: list[str] = field(default_factory=list)
    report_only: bool = False


@dataclass(slots=True)
class MigrationBlockerReport:
    id: str
    generated_at: str
    status: str
    passed: bool
    source_audit_id: str
    failing_requirement: str
    failing_command: str
    readiness_command: str
    migration_required_count: int
    migration_failure_count: int
    warning_count: int
    blockers: list[MigrationBlocker] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    report_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_migration_blocker_report(config: GapForgeConfig, *, audit: CompatibilityAudit | None = None) -> MigrationBlockerReport:
    compatibility_audit = audit or CompatibilityAuditor(config).audit(write=False)
    blockers = _migration_required_blockers(compatibility_audit)
    blockers.extend(_migration_failure_blockers(compatibility_audit))
    blockers.extend(_warning_blockers(compatibility_audit))
    blockers.extend(_coverage_gap_blockers(config, compatibility_audit))
    blockers.extend(_loader_scope_blockers(config))
    passed = not compatibility_audit.migration_required and not compatibility_audit.migration_failures
    return MigrationBlockerReport(
        id=f"migration-blockers-{compatibility_audit.id}",
        generated_at=utc_now_iso(),
        status="pass" if passed else "blocked",
        passed=passed,
        source_audit_id=compatibility_audit.id,
        failing_requirement="migration_audit_passed",
        failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
        readiness_command="PYTHONPATH=src python -m gapforge.cli v1-readiness --json",
        migration_required_count=len(compatibility_audit.migration_required),
        migration_failure_count=len(compatibility_audit.migration_failures),
        warning_count=len(compatibility_audit.warnings),
        blockers=blockers,
        warnings=list(compatibility_audit.warnings),
        notes=[
            "This audit identifies v0.9.1 migration blockers only.",
            "It does not claim v1 readiness and does not migrate persisted project or run data.",
        ],
    )


def write_migration_blocker_report(config: GapForgeConfig, report: MigrationBlockerReport) -> Path:
    path = config.root / DEFAULT_BLOCKER_REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    report.report_path = str(path)
    path.write_text(render_migration_blocker_report(report), encoding="utf-8")
    return path


def render_migration_blocker_report(report: MigrationBlockerReport) -> str:
    lines = [
        "# v0.9.1 Migration Blocker Audit",
        "",
        "This is a focused blocker audit for making the v1 readiness gate pass safely. It does not claim v1 readiness.",
        "",
        "## Summary",
        "",
        f"- Status: `{report.status}`",
        f"- Passed: {str(report.passed).lower()}",
        f"- Source audit: `{report.source_audit_id}`",
        f"- Failing requirement: `{report.failing_requirement}`",
        f"- Failing command: `{report.failing_command}`",
        f"- v1 readiness command: `{report.readiness_command}`",
        f"- Migration-required objects: {report.migration_required_count}",
        f"- Migration load failures: {report.migration_failure_count}",
        f"- Audit warnings: {report.warning_count}",
        "",
        "## Blockers",
        "",
    ]
    if not report.blockers:
        lines.append("- none")
    for blocker in report.blockers:
        lines.extend(
            [
                f"### {blocker.failing_object_type} ({', '.join(blocker.affected_versions)})",
                "",
                f"- Failing requirement: `{blocker.failing_requirement}`",
                f"- Failing command: `{blocker.failing_command}`",
                f"- Failing object type: `{blocker.failing_object_type}`",
                f"- Affected versions: {', '.join(blocker.affected_versions)}",
                f"- Object count: {blocker.object_count}",
                f"- Example objects: {', '.join(f'`{item}`' for item in blocker.example_objects) if blocker.example_objects else 'none'}",
                f"- Root cause: {blocker.root_cause}",
                f"- Required fix: {blocker.required_fix}",
                f"- Data mutation required: {str(blocker.data_mutation_required).lower()}",
                f"- Report-only blocker: {str(blocker.report_only).lower()}",
                f"- v1 readiness impact: {blocker.v1_readiness_impact}",
                "- Tests to add:",
            ]
        )
        lines.extend([f"  - {test}" for test in blocker.tests_to_add] or ["  - none"])
        lines.append("")
    lines.extend(["## Warnings", ""])
    lines.extend([f"- {warning}" for warning in report.warnings] or ["- none"])
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {note}" for note in report.notes] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _migration_required_blockers(audit: CompatibilityAudit) -> list[MigrationBlocker]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in audit.migration_required:
        parsed = _parse_required_item(item)
        if parsed is None:
            continue
        object_type, object_id, source_version = parsed
        grouped[(object_type, source_version)].append(object_id)
    blockers: list[MigrationBlocker] = []
    for (object_type, source_version), object_ids in sorted(grouped.items()):
        blockers.append(_required_group_blocker(object_type, source_version, object_ids))
    return blockers


def _migration_failure_blockers(audit: CompatibilityAudit) -> list[MigrationBlocker]:
    if not audit.migration_failures:
        return []
    by_type = Counter(item.split(":", 1)[0] for item in audit.migration_failures)
    blockers: list[MigrationBlocker] = []
    for object_type, count in sorted(by_type.items()):
        examples = [item for item in audit.migration_failures if item.startswith(f"{object_type}:")][:5]
        blockers.append(
            MigrationBlocker(
                failing_requirement="migration_audit_passed",
                failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
                failing_object_type=object_type,
                affected_versions=["unknown"],
                object_count=count,
                example_objects=examples,
                root_cause="At least one persisted object cannot be parsed or loaded by the current compatibility audit.",
                required_fix=(
                    "Reproduce each load failure with its persisted JSON file, add a targeted loader/migration fallback, "
                    "and keep malformed-object failures reportable."
                ),
                tests_to_add=[
                    "A regression fixture for each load failure shape.",
                    "A CLI assertion that migration-blockers reports migration_failures with the failing object type and path.",
                ],
                data_mutation_required=False,
                v1_readiness_impact="Any migration failure keeps migration_audit_passed false and blocks v1 readiness.",
            )
        )
    return blockers


def _warning_blockers(audit: CompatibilityAudit) -> list[MigrationBlocker]:
    if not audit.warnings:
        return []
    run_config_warnings = [warning for warning in audit.warnings if "missing field `config`" in warning]
    if not run_config_warnings:
        return []
    return [
        MigrationBlocker(
            failing_requirement="migration_audit_passed",
            failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
            failing_object_type="run",
            affected_versions=["unknown"],
            object_count=len(run_config_warnings),
            example_objects=[warning.split(": ", 1)[0].split(":", 1)[1] for warning in run_config_warnings[:5]],
            root_cause=(
                "The earliest run state files predate the persisted `config` object. The audit can synthesize a default for loadability, "
                "but version detection remains `unknown` until the run is migrated or the detector maps this legacy shape."
            ),
            required_fix=(
                "Migrate the affected runs with backup, filling `config.schema_version` and `config.gapforge_version`, "
                "or add an explicit non-mutating legacy-shape detector before migration."
            ),
            tests_to_add=[
                "A fixture run with no `config` that loads, reports unknown-version migration required, and migrates to v1.",
                "A loader test proving ResearchStateManager.load_run can still read the pre-config fixture before migration.",
            ],
            data_mutation_required=True,
            report_only=True,
            v1_readiness_impact=(
                "This warning is not independently pass-blocking, but the same objects are in migration_required and keep the audit failed."
            ),
        )
    ]


def _coverage_gap_blockers(config: GapForgeConfig, audit: CompatibilityAudit) -> list[MigrationBlocker]:
    if not audit.migration_required and not audit.migration_failures:
        return []
    versions = {
        source_version for _, _, source_version in (_parse_required_item(item) or ("", "", "") for item in audit.migration_required)
    }
    fixture_versions = {fixture.version for fixture in list_historical_migration_fixtures(config)}
    missing_fixture_versions = sorted(version for version in versions if version != "unknown" and version not in fixture_versions)
    if "unknown" in versions:
        missing_fixture_versions.insert(0, "unknown")
    if not missing_fixture_versions:
        return []
    return [
        MigrationBlocker(
            failing_requirement="migration_audit_passed",
            failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
            failing_object_type="fixture coverage",
            affected_versions=missing_fixture_versions,
            object_count=0,
            example_objects=[],
            root_cause=(
                "At least one live migration-required object has no exact historical fixture version match. "
                "Unknown-version objects still need dedicated legacy-shape coverage because they cannot be mapped to a declared version."
            ),
            required_fix=(
                "Add or refine focused older-state fixtures for the affected version or legacy shape, then assert both loadability "
                "and blocker classification."
            ),
            tests_to_add=[
                "Compatibility audit tests for unknown project.json without `gapforge_version`.",
                "Compatibility audit and migration tests for v0.8 run state.",
                "No-op compatibility audit tests for v0.9/v1 current project and run state.",
                "CLI tests for `gapforge migration-blockers`, `--json`, and `--write-report`.",
            ],
            data_mutation_required=False,
            report_only=True,
            v1_readiness_impact=(
                "The missing fixtures do not directly flip the readiness gate, but they make the v0.9.1 migration fix unsafe to claim."
            ),
        )
    ]


def _loader_scope_blockers(config: GapForgeConfig) -> list[MigrationBlocker]:
    scoped_files: list[Path] = []
    for pattern in ["*/campaigns/*/campaign.json", "*/experiment_workspaces/*/workspace.json", "*/manuscripts/*/manuscript.json"]:
        scoped_files.extend(sorted(config.project_root.glob(pattern)))
    if not scoped_files:
        return []
    examples = [str(path.relative_to(config.root)) if path.is_relative_to(config.root) else str(path) for path in scoped_files[:5]]
    return [
        MigrationBlocker(
            failing_requirement="migration_audit_passed",
            failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
            failing_object_type="loader coverage",
            affected_versions=["campaign", "workspace", "manuscript"],
            object_count=len(scoped_files),
            example_objects=examples,
            root_cause=(
                "Project and run loaders are exercised by the compatibility audit, but project-scoped campaign, experiment workspace, "
                "and manuscript loaders are not scanned even though those persisted object files can exist under projects/."
            ),
            required_fix=(
                "Extend the migration audit to load project-scoped campaign, workspace, and manuscript state files or explicitly document "
                "why they are derived/non-blocking for v1 storage compatibility."
            ),
            tests_to_add=[
                "A project fixture with campaign state under campaigns/*/campaign.json.",
                "A project fixture with experiment workspace state under experiment_workspaces/*/workspace.json.",
                "A manuscript state fixture once manuscript directories exist in compatibility data.",
                "A negative test proving loader-scope gaps are reported until the audit covers or intentionally excludes them.",
            ],
            data_mutation_required=False,
            report_only=True,
            v1_readiness_impact=(
                "This is report-only for the current gate because compatibility-audit does not inspect these files today, "
                "but it is required before safely claiming the migration audit covers all persisted v1-relevant objects."
            ),
        )
    ]


def _required_group_blocker(object_type: str, source_version: str, object_ids: list[str]) -> MigrationBlocker:
    if object_type == "project" and source_version == "unknown":
        root_cause = (
            "Legacy project.json files load with ResearchProject defaults, but they do not persist `gapforge_version`, `storage_version`, "
            "`version`, or `schema_version`; MigrationRegistry.detect_project_version therefore returns `unknown`."
        )
        required_fix = (
            "Back up and migrate each affected project.json to persist `gapforge_version: v1`, or add a deliberate legacy-project "
            "version inference before migration and still write the version during the migration pass."
        )
        tests = [
            "A project fixture with the current ResearchProject shape but no `gapforge_version` is reported as a migration blocker.",
            "migrate-project fills `gapforge_version: v1` without deleting project artifacts or nested run/campaign directories.",
            "After migration, compatibility-audit no longer reports the project in migration_required.",
        ]
        data_mutation = True
    elif object_type == "run" and source_version == "unknown":
        root_cause = "Pre-schema run state lacks `config`, so version detection has no version field and returns `unknown`."
        required_fix = (
            "Back up and migrate each run to add `config.schema_version: 2` and `config.gapforge_version: v1` "
            "while preserving run artifacts."
        )
        tests = [
            "A no-config run fixture remains loadable before migration.",
            "migrate-run fills config defaults and keeps papers, claims, gaps, experiments, and generated artifacts unchanged.",
            "After migration, compatibility-audit no longer reports the run in migration_required.",
        ]
        data_mutation = True
    elif object_type == "run" and source_version == "v0.4":
        root_cause = (
            "Schema-1 run state is detected as v0.4. It loads, but persisted state has not been migrated to the latest storage version."
        )
        required_fix = (
            "Back up and migrate schema-1 runs to v1 using the existing run migration path, preserving artifacts and state lists."
        )
        tests = [
            "A v0.4/schema-1 fixture migrates to `config.gapforge_version: v1`.",
            "Artifact references and core state lists survive migration byte-for-byte where no schema default is required.",
            "compatibility-audit passes after migrating the v0.4 fixture project and run pair.",
        ]
        data_mutation = True
    elif object_type == "run" and source_version == "v0.8":
        root_cause = (
            "Schema-2 run state normalizes to v0.8 when no explicit `gapforge_version` is present. Those runs load, "
            "but the audit requires persisted `config.gapforge_version: v1` before v1 readiness can pass."
        )
        required_fix = (
            "Add and run a v0.8-to-v1 migration/backfill that writes `config.gapforge_version: v1` without changing empirical, "
            "benchmark, manuscript, or pilot artifacts."
        )
        tests = [
            "A v0.8/schema-2 run fixture is reported as requiring migration.",
            "migrate-run on the v0.8 fixture writes only version/default metadata and preserves artifact references.",
            "Readiness fixture includes migrated v0.8 runs before asserting migration_audit_passed.",
        ]
        data_mutation = True
    else:
        root_cause = f"Persisted {object_type} objects are at {source_version}, which differs from the latest storage version."
        required_fix = f"Migrate the affected {object_type} objects to v1 with backups and regression coverage."
        tests = [f"A {source_version} {object_type} fixture migrates to v1 and then disappears from migration_required."]
        data_mutation = True
    return MigrationBlocker(
        failing_requirement="migration_audit_passed",
        failing_command="PYTHONPATH=src python -m gapforge.cli compatibility-audit --json",
        failing_object_type=object_type,
        affected_versions=[source_version],
        object_count=len(object_ids),
        example_objects=object_ids[:5],
        root_cause=root_cause,
        required_fix=required_fix,
        tests_to_add=tests,
        data_mutation_required=data_mutation,
        v1_readiness_impact=(
            "The v1 readiness gate reads data/release_gate/migration_audit.json; any migration_required entry keeps "
            "`migration_audit_passed` false and blocks v1 readiness."
        ),
    )


def _parse_required_item(item: str) -> tuple[str, str, str] | None:
    parts = item.split(":")
    if len(parts) != 3 or "->" not in parts[2]:
        return None
    return parts[0], parts[1], parts[2].split("->", 1)[0]


def report_to_json(report: MigrationBlockerReport) -> str:
    return json.dumps(report.to_dict(), indent=2) + "\n"
