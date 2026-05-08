# v0.9.1 Migration Blocker Audit

This is a focused blocker audit for making the v1 readiness gate pass safely. It does not claim v1 readiness.

## Summary

- Status: `blocked`
- Passed: false
- Source audit: `compatibility-audit-20260508T045833Z`
- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- v1 readiness command: `PYTHONPATH=src python -m gapforge.cli v1-readiness --json`
- Migration-required objects: 205
- Migration load failures: 0
- Audit warnings: 2

## Blockers

### project (unknown)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `project`
- Affected versions: unknown
- Object count: 98
- Example objects: `benchmark-canary-fixture-benchmark-failure`, `benchmark-canary-fixture-benchmark-failure-2`, `benchmark-canary-fixture-benchmark-failure-3`, `benchmark-canary-fixture-benchmark-failure-4`, `benchmark-canary-fixture-benchmark-failure-5`
- Root cause: Legacy project.json files load with ResearchProject defaults, but they do not persist `gapforge_version`, `storage_version`, `version`, or `schema_version`; MigrationRegistry.detect_project_version therefore returns `unknown`.
- Required fix: Back up and migrate each affected project.json to persist `gapforge_version: v1`, or add a deliberate legacy-project version inference before migration and still write the version during the migration pass.
- Data mutation required: true
- Report-only blocker: false
- v1 readiness impact: The v1 readiness gate reads data/release_gate/migration_audit.json; any migration_required entry keeps `migration_audit_passed` false and blocks v1 readiness.
- Tests to add:
  - A project fixture with the current ResearchProject shape but no `gapforge_version` is reported as a migration blocker.
  - migrate-project fills `gapforge_version: v1` without deleting project artifacts or nested run/campaign directories.
  - After migration, compatibility-audit no longer reports the project in migration_required.

### run (unknown)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `run`
- Affected versions: unknown
- Object count: 2
- Example objects: `20260504T231644Z-low-false-positive-collusion-detection`, `20260504T231704Z-low-false-positive-collusion-detection`
- Root cause: Pre-schema run state lacks `config`, so version detection has no version field and returns `unknown`.
- Required fix: Back up and migrate each run to add `config.schema_version: 2` and `config.gapforge_version: v1` while preserving run artifacts.
- Data mutation required: true
- Report-only blocker: false
- v1 readiness impact: The v1 readiness gate reads data/release_gate/migration_audit.json; any migration_required entry keeps `migration_audit_passed` false and blocks v1 readiness.
- Tests to add:
  - A no-config run fixture remains loadable before migration.
  - migrate-run fills config defaults and keeps papers, claims, gaps, experiments, and generated artifacts unchanged.
  - After migration, compatibility-audit no longer reports the run in migration_required.

### run (v0.4)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `run`
- Affected versions: v0.4
- Object count: 13
- Example objects: `20260504T232420Z-low-false-positive-collusion-detection`, `20260504T232420Z-low-false-positive-collusion-detection-2`, `20260504T233204Z-low-false-positive-collusion-detection`, `20260504T235440Z-low-false-positive-collusion-detection`, `20260504T235838Z-low-false-positive-collusion-detection`
- Root cause: Schema-1 run state is detected as v0.4. It loads, but persisted state has not been migrated to the latest storage version.
- Required fix: Back up and migrate schema-1 runs to v1 using the existing run migration path, preserving artifacts and state lists.
- Data mutation required: true
- Report-only blocker: false
- v1 readiness impact: The v1 readiness gate reads data/release_gate/migration_audit.json; any migration_required entry keeps `migration_audit_passed` false and blocks v1 readiness.
- Tests to add:
  - A v0.4/schema-1 fixture migrates to `config.gapforge_version: v1`.
  - Artifact references and core state lists survive migration byte-for-byte where no schema default is required.
  - compatibility-audit passes after migrating the v0.4 fixture project and run pair.

### run (v0.8)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `run`
- Affected versions: v0.8
- Object count: 92
- Example objects: `20260505T012915Z-pdf-artifact-smoke`, `20260505T033316Z-low-false-positive-collusion-detection`, `20260505T033653Z-low-false-positive-collusion-detection`, `20260505T033706Z-low-false-positive-collusion-detection`, `20260505T034115Z-low-false-positive-collusion-detection`
- Root cause: Schema-2 run state normalizes to v0.8 when no explicit `gapforge_version` is present. Those runs load, but the audit requires persisted `config.gapforge_version: v1` before v1 readiness can pass.
- Required fix: Add and run a v0.8-to-v1 migration/backfill that writes `config.gapforge_version: v1` without changing empirical, benchmark, manuscript, or pilot artifacts.
- Data mutation required: true
- Report-only blocker: false
- v1 readiness impact: The v1 readiness gate reads data/release_gate/migration_audit.json; any migration_required entry keeps `migration_audit_passed` false and blocks v1 readiness.
- Tests to add:
  - A v0.8/schema-2 run fixture is reported as requiring migration.
  - migrate-run on the v0.8 fixture writes only version/default metadata and preserves artifact references.
  - Readiness fixture includes migrated v0.8 runs before asserting migration_audit_passed.

### run (unknown)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `run`
- Affected versions: unknown
- Object count: 2
- Example objects: `20260504T231644Z-low-false-positive-collusion-detection`, `20260504T231704Z-low-false-positive-collusion-detection`
- Root cause: The earliest run state files predate the persisted `config` object. The audit can synthesize a default for loadability, but version detection remains `unknown` until the run is migrated or the detector maps this legacy shape.
- Required fix: Migrate the affected runs with backup, filling `config.schema_version` and `config.gapforge_version`, or add an explicit non-mutating legacy-shape detector before migration.
- Data mutation required: true
- Report-only blocker: true
- v1 readiness impact: This warning is not independently pass-blocking, but the same objects are in migration_required and keep the audit failed.
- Tests to add:
  - A fixture run with no `config` that loads, reports unknown-version migration required, and migrates to v1.
  - A loader test proving ResearchStateManager.load_run can still read the pre-config fixture before migration.

### fixture coverage (unknown)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `fixture coverage`
- Affected versions: unknown
- Object count: 0
- Example objects: none
- Root cause: At least one live migration-required object has no exact historical fixture version match. Unknown-version objects still need dedicated legacy-shape coverage because they cannot be mapped to a declared version.
- Required fix: Add or refine focused older-state fixtures for the affected version or legacy shape, then assert both loadability and blocker classification.
- Data mutation required: false
- Report-only blocker: true
- v1 readiness impact: The missing fixtures do not directly flip the readiness gate, but they make the v0.9.1 migration fix unsafe to claim.
- Tests to add:
  - Compatibility audit tests for unknown project.json without `gapforge_version`.
  - Compatibility audit and migration tests for v0.8 run state.
  - No-op compatibility audit tests for v0.9/v1 current project and run state.
  - CLI tests for `gapforge migration-blockers`, `--json`, and `--write-report`.

### loader coverage (campaign, workspace, manuscript)

- Failing requirement: `migration_audit_passed`
- Failing command: `PYTHONPATH=src python -m gapforge.cli compatibility-audit --json`
- Failing object type: `loader coverage`
- Affected versions: campaign, workspace, manuscript
- Object count: 88
- Example objects: `projects/canary-agentic-undercovered-refusal/campaigns/campaign-20260505T205129Z-intentionally-sparse-undercovered-research-topic-for-strict-refusal/campaign.json`, `projects/canary-fake-agent-campaign-regression/campaigns/campaign-20260505T205041Z-fake-agent-campaign-regression-for-ci/campaign.json`, `projects/canary-fake-agent-campaign-regression-10/campaigns/campaign-20260506T032828Z-fake-agent-campaign-regression-for-ci/campaign.json`, `projects/canary-fake-agent-campaign-regression-11/campaigns/campaign-20260506T033615Z-fake-agent-campaign-regression-for-ci/campaign.json`, `projects/canary-fake-agent-campaign-regression-12/campaigns/campaign-20260506T071649Z-fake-agent-campaign-regression-for-ci/campaign.json`
- Root cause: Project and run loaders are exercised by the compatibility audit, but project-scoped campaign, experiment workspace, and manuscript loaders are not scanned even though those persisted object files can exist under projects/.
- Required fix: Extend the migration audit to load project-scoped campaign, workspace, and manuscript state files or explicitly document why they are derived/non-blocking for v1 storage compatibility.
- Data mutation required: false
- Report-only blocker: true
- v1 readiness impact: This is report-only for the current gate because compatibility-audit does not inspect these files today, but it is required before safely claiming the migration audit covers all persisted v1-relevant objects.
- Tests to add:
  - A project fixture with campaign state under campaigns/*/campaign.json.
  - A project fixture with experiment workspace state under experiment_workspaces/*/workspace.json.
  - A manuscript state fixture once manuscript directories exist in compatibility data.
  - A negative test proving loader-scope gaps are reported until the audit covers or intentionally excludes them.

## Warnings

- run:20260504T231644Z-low-false-positive-collusion-detection: missing field `config`; default will be used on migration
- run:20260504T231704Z-low-false-positive-collusion-detection: missing field `config`; default will be used on migration

## Notes

- This audit identifies v0.9.1 migration blockers only.
- It does not claim v1 readiness and does not migrate persisted project or run data.
