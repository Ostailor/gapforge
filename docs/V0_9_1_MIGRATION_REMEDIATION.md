# GapForge v0.9.1 Migration Remediation

v0.9.0 passed the external pilot as an accepted correct refusal, but it was not v1-ready. The blocker was not the pilot result. The blocker was migration and backward compatibility: old run, project, campaign, workspace, benchmark, replication, manuscript, and pilot state did not have enough tested migration coverage for v1 readiness.

v0.9.1 is scoped to remediation only. It must not add new research features or weaken release gates. Its purpose is to make old GapForge state load or migrate safely, with auditable backups and honest warnings.

## What v0.9.1 Fixes

- Adds historical fixture coverage for v0.1 through v0.9.
- Adds ordered versioned migrators to the current schema.
- Adds backup snapshots before mutation.
- Preserves claims, evidence, results, manuscript state, review records, blockers, and provenance where possible.
- Preserves unknown legacy fields under a compatibility namespace instead of silently deleting them.
- Treats ambiguous migrations as failures, not best guesses.
- Adds a v2 compatibility audit for v1 readiness.

## Commands

Run the compatibility audit first:

```bash
gapforge compatibility-audit --v2 --write-report
```

Preview migrations:

```bash
gapforge migrate-all --dry-run
```

Apply migrations only after reviewing the dry run:

```bash
gapforge migrate-all --apply
```

Inspect migration records and the latest compatibility report:

```bash
gapforge migration-report
```

Recheck readiness after the audit and other release gates are present:

```bash
gapforge v1-readiness --write-report --json
```

## Backup Behavior

Every applied migration writes a snapshot under:

```text
data/migrations/backups/
```

Backups are created before the primary JSON is mutated. Directory-backed objects, such as projects and runs, are copied as directories. File-backed objects, such as benchmark suite JSON, are copied into a backup directory containing the original file.

Do not delete backups until the migrated state has loaded, reports have been reviewed, and the compatibility audit has passed.

## Warnings

Warnings mean the audit found something visible but not necessarily blocking.

Examples:

- a historical fixture intentionally references a missing generated artifact
- an ignored local transcript or cache exists outside curated release evidence
- an unknown legacy field was preserved in `_compatibility.unknown_fields`
- a local generated artifact is unsafe to commit but ignored and not curated v1 evidence

Warnings should be reviewed. They do not block v1 unless they point to curated release evidence, data loss risk, current-schema load failure, or a failed migration.

## What Blocks v1

The v1 readiness gate blocks if any of these are true:

- v4, v5, v6, v7, or v8 release gate evidence is missing or failed
- the v0.9 pilot is not accepted as a defensible direction or correct refusal
- compatibility audit v2 is missing, not v2, failed, or has migration failures
- CLI, docs, or artifact hygiene audit fails
- unresolved product failures remain
- a migration would drop claims, evidence, results, manuscript objects, review records, blockers, or provenance
- a current-schema object cannot load
- an unsafe artifact is part of curated release evidence

Ignored/generated local artifacts can be warnings when they are not curated evidence.

## Intentionally Not Migrated

v0.9.1 does not migrate raw PDFs, datasets, prompt packs, LLM transcripts, caches, dashboards, large generated bundles, or task output directories. Those artifacts remain generated/private unless separately exported through a safe bundle.

v0.9.1 also does not invent missing evidence. If old state references a missing artifact, the migration keeps the reference and emits a warning. The fix is either to restore the artifact, remove the stale reference in a reviewed follow-up, or document why the missing artifact is not curated evidence.

## Recovery

If migration fails:

1. Stop applying further migrations.
2. Read `gapforge migration-report`.
3. Inspect `data/migrations/records/` for the failed `MigrationRecord`.
4. Restore the affected object from `data/migrations/backups/` if the failure happened after a backup was created.
5. Fix the source-version marker, missing required field, renamed field, or ambiguous artifact reference.
6. Rerun:

```bash
gapforge migrate-all --dry-run
gapforge compatibility-audit --v2 --write-report
```

If the failure is ambiguous source version detection, do not guess. Add an explicit version marker or a dedicated migration rule with tests.
