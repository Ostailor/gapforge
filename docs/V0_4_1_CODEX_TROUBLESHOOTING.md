# v0.4.1 Codex Troubleshooting

Use this when a Codex/GPT-5.4 task-pack, manual handoff, direct runner, validation, import, attestation, review, or release gate step fails.

Start with:

```bash
gapforge setup-codex
gapforge codex-doctor --task-id <task-id>
```

For release-gate blockers:

```bash
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
gapforge actual-run-status --campaign-id <campaign-id>
```

## Direct Runner Setup

### `GAPFORGE_CODEX_COMMAND` Is Missing

Symptoms:

- `gapforge setup-codex` says direct mode is unavailable.
- `gapforge codex-run --task-id <task-id> --direct` fails.

Fix:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=direct
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'

gapforge setup-codex
gapforge codex-command-preview --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct --dry-run
```

If no direct Codex runner exists, use task-pack handoff instead:

```bash
gapforge codex-handoff --task-id <task-id> --print-prompt
```

### Command Template Is Wrong

Recommended placeholders:

- `{task_pack}`
- `{outputs_dir}`
- `{model}`
- `{task_id}`
- `{run_id}`

Preview before running:

```bash
gapforge codex-command-preview --task-id <task-id>
```

If `{outputs_dir}` is missing, Codex may complete without writing files where GapForge validates them.

### Command Exits 0 but No Outputs Exist

Symptoms:

- command appears successful
- `outputs/` is empty
- validation says no useful output files were found

Fix:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge codex-handoff --task-id <task-id> --print-prompt
```

Then run Codex manually and ensure it writes the exact required filenames into the shown `outputs/` directory.

## Task-Pack Handoff

### User Does Not Know What To Paste Into Codex

Use the copy-paste prompt:

```bash
gapforge codex-handoff --task-id <task-id> --print-prompt
```

Tell Codex to read the task pack, inspect the listed artifacts, and write only the required JSON files to `outputs/`.

### Codex Writes Output In The Wrong Directory

Find the expected directory:

```bash
gapforge codex-doctor --task-id <task-id>
```

Move the files into that task's `outputs/` directory, then run:

```bash
gapforge validate-import-all --task-id <task-id>
```

### Codex Writes Markdown Instead of JSON

Most task outputs must be JSON. Create a repair prompt:

```bash
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

Ask Codex to rewrite the output as the exact JSON filenames required by the task pack.

### Codex Writes One File but Several Are Listed

Partial output is allowed only when the task output contract marks the missing files optional or one-of. Check:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
```

Missing optional files are warnings. Missing all useful files is invalid.

## Validation Errors

### Fake Citation or Unknown Prior Work

Do not add the citation as prior work. Convert it to a search request or missing search:

```json
{
  "missing_searches": ["exact title or author/method query"],
  "verdict": "unknown",
  "confidence": "low"
}
```

Then repair:

```bash
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff
```

### Unknown Paper ID or EvidenceSpan Locator

Use the known IDs printed by:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

If no evidence locator exists, downgrade the claim to uncertain or request parsing/search. Do not invent evidence.

### Unsupported High-Confidence Claim

Fix one of two ways:

- add valid EvidenceSpan IDs/locators from the task pack
- downgrade the claim to uncertain/low confidence

Never ask Codex to invent supporting evidence.

## Repair Workflow

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
# Run Codex/GPT-5.4 on the repair prompt.
gapforge validate-repair-output --repair-id <repair-id>
gapforge import-repair-output --repair-id <repair-id>
```

Repair cannot bypass validation. Invalid repaired output remains rejected.

## Acceptance and Release Gate

### Fake-Agent Canary Passed but Release Gate Failed

This is correct. Fake-agent canaries test plumbing only.

Actual acceptance requires:

- Codex/GPT-5.4 output
- validation
- import
- attestation
- human review
- release gate

### Imported but Not Attested

```bash
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

Only attest if Codex/GPT-5.4 actually produced the output.

### Attested but Not Reviewed

```bash
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
```

### Missing Required Campaign Type

The release gate explains missing campaign types:

```bash
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
```

Common next canaries:

```bash
gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real
gapforge campaign-canary-run --profile agentic_undercovered_refusal --real
gapforge campaign-canary-run --profile manual_pdf_codex_reading_handoff --real
```

## Golden Path

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 and write JSON outputs to outputs/.
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-canary-complete --canary-id <canary-id>
```

If a step fails, do not skip it. Use the doctor and repair workflow.
