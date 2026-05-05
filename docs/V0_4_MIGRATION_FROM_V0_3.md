# Migrating From v0.3 to v0.4

v0.4 builds on v0.3. Existing v0.3 run and project state should remain valid. The main migration is conceptual: v0.3 task packs become one component of v0.4 campaign execution.

## What Carries Forward

- run-local state
- project memory
- corpus paper records
- human review records
- claim graph records
- retrieval indexes, when still valid
- source coverage reports
- novelty dossiers
- related-work matrices
- research directions
- experiment protocols
- paper packages
- fake-agent tests and prompt-pack generation

## What Changes

### Task Packs Become Campaign Steps

v0.3 could generate task packs for individual skills. v0.4 should attach those task packs to campaign steps with durable lifecycle state, validation records, and import decisions.

### Canaries Become Campaigns

v0.3 canaries were mostly single-profile or fake-agent validation surfaces. v0.4 canaries should be multi-step campaigns with source coverage, retrieval, Codex task execution or handoff/import, strict reports, and human acceptance review.

### Actual-Run Acceptance Becomes Stricter

v0.3 did not complete actual Codex/GPT-5.4 real-run acceptance. v0.4 must not claim acceptance unless multiple real campaigns are accepted by human review.

## Compatibility Requirements

- `gapforge run --v3` should remain available.
- deterministic and fake-agent paths should continue to work offline.
- old project directories should load without campaign records.
- campaign state should be optional for old runs.
- v0.3 release notes and real-run acceptance docs should remain historically accurate.

## Recommended Upgrade Flow

1. Load an existing v0.3 project.
2. Build or refresh the retrieval index.
3. Create a v0.4 campaign for a selected topic or direction.
4. Run deterministic preflight checks.
5. Generate or dispatch Codex/GPT-5.4 campaign tasks.
6. Validate and import outputs.
7. Run strict report.
8. Complete human review.
9. Sync accepted decisions back into project memory.

## Data Safety

- Do not import old task-pack outputs unless they pass current validators.
- Do not mark old fake-agent canaries as real campaigns.
- Do not upgrade prompt-pack-only records into actual-run acceptance.
- Preserve rejected ideas and human decisions.
- Keep generated campaign dashboards, transcripts, PDFs, and safe bundles ignored unless intentionally exported.

## Release Note Guidance

v0.4 release notes should explicitly say whether actual-run acceptance passed. If it passed, they should list accepted campaign IDs, source profiles, agent/model, validation summaries, and human review status. If it did not pass, they should say so directly.
