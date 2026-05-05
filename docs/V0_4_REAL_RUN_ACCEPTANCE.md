# v0.4 Real-Run Acceptance

v0.4 real-run acceptance is stricter than v0.3. v0.3 required at least one accepted real Codex/GPT-5.4 canary before claiming actual-run acceptance, but that did not happen. v0.4 raises the bar to multiple accepted real Codex/GPT-5.4 campaigns.

## Validation Levels

### Level 0: Deterministic CI

- no Codex/GPT-5.4
- no provider LLM
- no live network required
- validates schemas, persistence, deterministic skills, reports, fake fixtures, and evaluator harness

### Level 1: Offline Smoke

- no Codex/GPT-5.4
- no network
- validates orchestration safety and fallback labeling

### Level 2: Fake-Agent Campaign Tests

- FakeAgentClient only
- validates campaign state, task lifecycle, schema validators, recovery, and import gates
- never counts as actual-run acceptance

### Level 3: Prompt-Pack Handoff

- no live calls
- writes task packs and expected output schemas
- may become part of real-run acceptance only if real Codex/GPT-5.4 outputs are later imported, validated, and human-reviewed

### Level 4: Real Codex/GPT-5.4 Campaigns

- actual Codex/GPT-5.4 performs campaign tasks
- outputs are validated before import
- campaign records identify agent/model, task IDs, outputs, validations, imports, and failures
- multiple campaigns must complete

### Level 5: Human-Reviewed Acceptance

- human reviewers inspect campaign artifacts
- accepted/rejected status is recorded
- blocking failures prevent acceptance
- release gate reads the recorded artifacts

## v0.4 Release Requirement

To state `v0.4 actual-run acceptance passed`, all of the following must be true:

- at least three real Codex/GPT-5.4 campaigns completed
- at least three real campaigns were accepted by human review
- campaign artifacts are stored and auditable
- each accepted campaign has validated imports or an explicit evidence-backed no-import conclusion
- no accepted campaign contains fake citations
- no accepted campaign contains unsupported high-confidence claims
- no accepted campaign overclaims novelty under poor coverage
- strict report behavior was reviewed
- fake-agent and prompt-pack-only runs are not counted

If these conditions are not met, release notes must say:

`v0.4 actual-run acceptance not completed`

## Required Campaign Coverage

At minimum:

- one literature/novelty campaign
- one local-PDF full-text reading campaign
- one undercoverage strict-refusal campaign

Recommended:

- one reviewer/rebuttal campaign
- one manuscript package review campaign

## Blocking Failures

Any of these blocks campaign acceptance:

- fake citation found
- unsupported high-confidence claim found
- closest prior work missing for a novelty claim
- strict report recommends novelty under poor coverage
- unvalidated Codex output mutates state
- human review missing
- real Codex/GPT-5.4 unavailable but run marked accepted
- task-pack-only workflow counted without imported real Codex output
- fake-agent campaign counted as actual-run acceptance

## Artifact Requirements

Each accepted campaign should provide:

- campaign record JSON
- task specs and task packs
- Codex run records or handoff/import records
- validation results
- imported output summary
- source coverage report
- final or campaign report
- human review record
- acceptance summary

## Commands

Recommended release-gate workflow:

```bash
make ci
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression

export GAPFORGE_ENABLE_REAL_RUNS=1
gapforge campaign-canary-plan --profile agentic_low_fpr_collusion
gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real

gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
gapforge v4-release-gate --project-id <project-id> --write-report --json
```

If using task-pack handoff instead of direct execution:

```bash
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge task-handoff --task-id <task-id>
# Codex/GPT-5.4 writes outputs.
gapforge campaign-validate-output --campaign-id <campaign-id> --task-id <task-id>
gapforge campaign-import-output --campaign-id <campaign-id> --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
```

If direct execution is configured:

```bash
gapforge agent-capabilities
gapforge codex-run --task-id <task-id> --direct
```

Direct execution that produces invalid output still fails acceptance until repaired and validated.

## Release Gate Behavior

The release gate must refuse actual-run acceptance unless campaign records and human review records prove the required accepted real campaigns. The gate should fail closed when artifacts are missing, ambiguous, or inconsistent.

Never fake a canary or campaign pass.
