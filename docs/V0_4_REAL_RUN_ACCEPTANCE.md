# v0.4 Real-Run Acceptance

v0.4 real-run acceptance is campaign-level. Fake-agent tests and prompt-pack generation are useful, but they do not prove actual Codex/GPT-5.4 research behavior.

For the operational command sequence, see `docs/CODEX_QUICKSTART.md`.

## Validation Levels

### Level 0: Deterministic CI

- no Codex/GPT-5.4
- no provider LLM
- no live network required
- validates schemas, persistence, deterministic skills, reports, fake fixtures, and evals

### Level 1: Offline Smoke

- no Codex/GPT-5.4
- no network
- validates orchestration safety and fallback labeling

### Level 2: Fake-Agent Tests

- uses fake agent output only
- validates task packs, schema validation, import gates, repair, rollback, dashboards, and release-gate blockers
- never counts as actual-run acceptance

### Level 3: Prompt-Pack or Task-Pack Dry Run

- no live model call required
- validates that prompts, schemas, artifact links, and citation rules are usable
- can become part of actual-run acceptance only after real Codex/GPT-5.4 writes outputs that are validated, imported, attested, and human-reviewed

### Level 4: Actual Codex/GPT-5.4 Campaign

- Codex/GPT-5.4 performs one or more campaign tasks
- outputs are validated before import
- task-pack/manual-handoff runs include human attestation of agent, model, and method
- direct runs include runner records and valid imports

### Level 5: Human-Reviewed Acceptance

- human reviewer inspects campaign artifacts
- fake citations, unsupported high-confidence claims, and novelty overclaims block acceptance
- review is recorded with `campaign-review`

## What Counts as Actual

Task-pack or manual-handoff can count only if all are true:

- Codex/GPT-5.4 actually produced the output
- `gapforge validate-import-all --task-id <task-id>` accepted/imported it
- `gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"` was recorded
- `gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"` accepted the campaign

Direct execution can count only if all are true:

- `GAPFORGE_ENABLE_REAL_RUNS=1`
- direct runner command was configured and executed
- outputs were valid/imported
- campaign human review accepted the result

Fake-agent output never counts. Prompt-pack files without Codex-produced outputs never count.

## v0.4 Release Requirement

To state `v0.4 actual-run acceptance passed`, the release gate must pass:

```bash
gapforge v4-release-gate --write-report
```

The gate requires:

- deterministic CI evidence
- passed fake-agent campaign canary
- at least three accepted real Codex/GPT-5.4 campaigns
- at least one accepted experiment-ready campaign
- at least one accepted refusal campaign for poor coverage or novelty uncertainty
- at least one accepted manual-PDF/full-text campaign
- validated imported agent outputs
- actual-run attestation where task-pack/manual-handoff was used
- source coverage
- retrieval index
- novelty dossier for recommended direction or explicit refusal reason
- human review acceptance
- campaign report
- explicit stop reason

If the gate fails, use:

```bash
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
gapforge actual-run-status --campaign-id <campaign-id>
gapforge actual-run-status --project-id <project-id>
```

## Blocking Failures

Any of these blocks acceptance:

- fake citation found
- unsupported high-confidence claim found
- closest prior work missing for a novelty claim
- strong novelty claimed without prior work
- strict report recommends novelty under poor coverage
- unvalidated Codex output mutates state
- imported task-pack output lacks Codex/GPT-5.4 attestation
- human review missing
- fake-agent campaign counted as actual-run acceptance
- campaign lacks explicit stop reason

## v0.4.1 Minimal Actual-Run Debug Path

v0.4.1 adds a smaller canary for debugging task-pack usage:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 manually.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-canary-complete --canary-id <canary-id>
```

This can validate the actual handoff workflow. It is not by itself enough for full v0.4 release acceptance unless the release gate requirements are also met.

## Safety Rules

- Do not request or store hidden chain-of-thought.
- Do not invent citations, paper IDs, EvidenceSpan IDs, quotes, datasets, metrics, baselines, or results.
- Unknown citations become search requests or missing searches.
- Unsupported claims become uncertain or rejected.
- Never fake a canary, campaign, attestation, or review pass.
