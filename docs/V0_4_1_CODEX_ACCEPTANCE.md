# v0.4.1 Codex Acceptance Criteria

v0.4.1 acceptance is about usability and reliability of actual Codex/GPT-5.4 workflow execution. It does not require the v0.4 full release gate to pass, but it must make at least one real task-pack canary completable by a user.

This patch must not add new research features. It should improve setup, handoff, diagnosis, validation repair, attestation, review ordering, and release-gate clarity.

## Required CLI Behavior

### `gapforge setup-codex`

Pass criteria:

- Prints whether real runs are enabled.
- Prints current agent mode, agent name, and Codex model.
- Prints whether `GAPFORGE_CODEX_COMMAND` is configured.
- Prints whether direct, task-pack, manual-handoff, and fake modes are available.
- Redacts secrets.
- Prints exact next commands for the recommended path.
- Does not claim actual-run readiness when real-run env vars are missing.

### `gapforge codex-handoff --task-id <task-id>`

Pass criteria:

- Writes or refreshes `HANDOFF.md`.
- Includes a copy-paste-ready prompt for Codex/GPT-5.4.
- Includes exact output directory.
- Lists expected output filenames.
- Includes minimal valid JSON examples.
- Includes validation, import, attestation, review, and doctor commands.
- States that markdown-only output is invalid for JSON patch tasks.

### `gapforge codex-doctor --task-id <task-id>`

Pass criteria:

- Detects missing task pack.
- Detects missing output directory.
- Detects no output files.
- Detects invalid JSON.
- Detects markdown/prose output where JSON is required.
- Detects missing expected files.
- Detects unknown paper IDs, evidence span IDs, and prior-work IDs.
- Detects fake citations.
- Detects imported-without-attestation status.
- Detects reviewed-but-not-actual status.
- Prints repair commands and next action.

## Required End-to-End Task-Pack Canary

A user must be able to complete at least one real Codex/GPT-5.4 task-pack canary:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-plan --profile agentic_low_fpr_collusion
gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge codex-handoff --task-id <task-id>
# Run the handoff in Codex/GPT-5.4 and write JSON outputs to outputs_dir.
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
```

The accepted task must have:

- real Codex/GPT-5.4 output files
- validation record
- import record
- attestation record
- human review record
- no fake citations
- no unsupported high-confidence claims
- no unvalidated state mutation

## Direct Runner Acceptance

Direct runner is accepted for v0.4.1 only if:

- `setup-codex` reports direct mode available.
- `GAPFORGE_CODEX_COMMAND` includes required placeholders or an equivalent configured contract.
- `codex-run --direct` records command, status, stdout/stderr preview, timeout status, and output paths.
- A successful command with no output files is treated as failure.
- Output validation and import still run.
- Direct execution does not bypass human review.

Example:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=codex
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'

gapforge setup-codex
gapforge codex-doctor --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct
gapforge codex-doctor --task-id <task-id>
```

## Negative Acceptance Criteria

v0.4.1 fails if:

- fake-agent canaries are described as real acceptance
- task-pack output can be accepted without attestation
- campaign review can mark non-actual output as actual
- direct runner success with no output files is accepted
- markdown-only output passes JSON validation
- fake citations are not explained with repair guidance
- CI requires Codex/GPT-5.4

## CI Requirements

CI remains deterministic/offline:

```bash
make ci
gapforge eval --v4 --write-report
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
```

CI may test fake clients, fixture outputs, validators, doctors, and handoff generation. CI must not call live Codex/GPT-5.4.

## Release Note Requirement

v0.4.1 release notes must say one of:

- `v0.4.1 task-pack Codex usability canary completed`
- `v0.4.1 task-pack Codex usability canary not completed`

This is narrower than full v0.4 actual-run acceptance. Full acceptance still requires the v4 release gate and multiple accepted real campaigns.
