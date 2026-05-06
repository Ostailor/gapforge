# Codex v0.4.1 Quickstart

This page is the shortest copy-paste path for using Codex/GPT-5.4 with GapForge task packs.

Rules that always apply:

- Fake-agent runs do not count as real Codex/GPT-5.4 acceptance.
- Task-pack and manual-handoff runs count only after Codex output, validation, import, attestation, and human review.
- Direct runs count only after valid output/import and human review.
- Do not ask Codex for hidden chain-of-thought. Store public reasoning summaries only.
- Do not invent citations, paper IDs, EvidenceSpan IDs, quotes, datasets, results, or prior work.

## 1. Diagnose Setup

```bash
gapforge setup-codex
```

Use this before creating real-run canaries. It reports whether direct, task-pack, manual-handoff, and fake modes are available, what environment variables are missing, and which mode GapForge recommends.

For a specific task:

```bash
gapforge codex-doctor --task-id <task-id>
```

For a campaign:

```bash
gapforge codex-doctor --campaign-id <campaign-id>
gapforge actual-run-status --campaign-id <campaign-id>
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
```

## 2. Task-Pack Handoff

Use this when no direct Codex runner is configured. This is the recommended v0.4.1 real-run debugging path.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge latest-codex-task --campaign-id <campaign-id>
gapforge codex-handoff --task-id <task-id> --print-prompt
```

Paste the printed prompt into Codex/GPT-5.4. Codex must write the required JSON files into the task pack `outputs/` directory shown by the handoff.

Then validate, import, attest, and review:

```bash
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

If this was a single-task canary, complete it:

```bash
gapforge campaign-canary-complete --canary-id <canary-id>
```

Task-pack output does not count as actual-run acceptance until all of these are true:

- the output was produced by Codex/GPT-5.4
- validation passed or passed with safe warnings
- the output was imported
- a human attested the task with `--agent codex --model gpt-5.4`
- campaign review accepted the result

## 3. Direct Command Dry Run

Use this only when a local Codex command runner exists and can write outputs to `{outputs_dir}`.

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

If the preview is correct, run direct execution:

```bash
gapforge codex-run --task-id <task-id> --direct
gapforge validate-import-all --task-id <task-id>
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

If the command exits successfully but writes no expected outputs, direct mode fails. Fix the command template or use task-pack handoff:

```bash
gapforge codex-handoff --task-id <task-id>
```

## 4. Repair Invalid Output

Start with the doctor:

```bash
gapforge codex-doctor --task-id <task-id>
```

Create a repair task from the latest invalid validation:

```bash
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

The repair handoff includes the original task, invalid output path, exact validation errors, known paper IDs, known EvidenceSpan IDs/locators, accepted partial fields, files to rewrite, and minimal JSON skeletons.

Paste the repair prompt into Codex/GPT-5.4. Codex must not invent missing citations or evidence. Unknown citations should become `search_requests`, `missing_searches`, or uncertainty.

After Codex writes repaired outputs:

```bash
gapforge validate-repair-output --repair-id <repair-id>
gapforge import-repair-output --repair-id <repair-id>
gapforge actual-run-status --campaign-id <campaign-id>
```

Repair does not weaken validation. Invalid repaired output remains rejected.
