# GapForge v1 Migration and Compatibility

v1 readiness requires compatibility evidence, not just a successful v0.9 pilot. The compatibility audit must show that historical state loads, migrates, validates, creates backups, preserves protected records, and distinguishes curated release evidence from ignored local generated artifacts.

## Required Audit

Run:

```bash
gapforge compatibility-audit --v2 --write-report
```

The v2 audit checks:

- historical fixtures load
- historical fixtures migrate to the current schema
- current version local project and run state loads
- migrated state validates
- backup behavior works
- artifact safety remains intact
- unknown legacy fields are handled safely
- old CLI aliases resolve or are documented as deprecated
- a migration report can be generated

The release gate consumes `data/release_gate/migration_audit.json`. For v1 readiness, this file must be produced by compatibility audit v2 and must have no blockers or migration failures.

## Migration Workflow

Use the dry run first:

```bash
gapforge migrate-all --dry-run
```

Review the planned `MigrationRecord` changes. Then apply:

```bash
gapforge migrate-all --apply
```

After applying, inspect:

```bash
gapforge migration-report
gapforge compatibility-audit --v2 --write-report
gapforge v1-readiness --write-report --json
```

Individual migration commands remain available when a narrow fix is safer:

```bash
gapforge migrate-run --run-id <run-id> --to-version latest
gapforge migrate-project --project-id <project-id> --to-version latest
```

## Protected Data

Migration must never silently drop:

- claims
- evidence spans
- paper artifacts
- experiment records and result artifacts
- benchmark and replication records
- manuscript sections, claim uses, citation uses, figures, and tables
- reviewer objections, review summaries, and human reviews
- blockers and pilot outcome records
- provenance

If preservation is ambiguous, migration fails safely.

## Unknown Fields

Unknown legacy fields should be preserved under `_compatibility.unknown_fields` when practical. This is a warning, not a blocker, unless the field appears to contain protected data that could be lost or reinterpreted incorrectly.

## Backups

Applied migrations write backup snapshots to:

```text
data/migrations/backups/
```

Migration records are written to:

```text
data/migrations/records/
```

These records are part of the audit trail. Keep them until v1 readiness has been reviewed.

## Warnings Versus Blockers

Warnings are non-blocking when they describe ignored/generated local artifacts, expected missing fixture artifacts, or preserved unknown fields.

Blockers include:

- fixture load or migration failure
- current schema load failure
- validation failure after migration
- missing backup snapshot before mutation
- protected data loss risk
- unsafe curated release evidence
- unresolved product failure
- missing v2 compatibility audit report

## Intentionally Out of Scope

Migration does not import or regenerate:

- raw PDFs
- datasets
- transcripts
- prompt packs
- caches
- dashboards
- generated task outputs
- unsafe local bundles

Those artifacts remain outside the durable schema. If a release depends on one, it must be restored, safely bundled, or documented as missing evidence.

## Recovery From Failure

Use this sequence:

```bash
gapforge migration-report
gapforge migrate-all --dry-run
```

Then inspect the failed object and its backup. Restore from `data/migrations/backups/` if needed. Add a version marker or a dedicated migrator for ambiguous legacy state. Rerun the v2 audit before rerunning v1 readiness.

Do not claim v1 readiness until:

```bash
gapforge v1-readiness --write-report --json
```

returns a passing result.
