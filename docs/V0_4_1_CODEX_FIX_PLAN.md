# v0.4.1 Codex Workflow Fix Plan

v0.4.1 is a patch release focused only on Codex/GPT-5.4 usability and actual-run workflow reliability. It should not add new research skills, new research outputs, or new scientific claims.

## Why v0.4.1 Exists

v0.4.0 added campaign-level task packs, direct/task-pack/manual-handoff execution modes, validated import, rollback, repair, canaries, and release gates. The deterministic and fake-agent paths worked, but actual Codex/GPT-5.4 acceptance did not complete.

The practical gap is not another research feature. It is the path from:

```text
campaign task pack -> Codex/GPT-5.4 output -> validation -> import -> attestation -> human review -> release gate
```

being too easy to misunderstand or execute incorrectly.

## Patch Scope

Must fix or document:

- direct runner setup diagnostics
- copy-paste-ready Codex handoff
- task output location clarity
- expected JSON file/schema clarity
- validation error repair guidance
- attestation/import/review order
- release-gate status clarity

Must not add:

- new research skills
- new gap/novelty/experiment methodology
- live model calls in CI
- weaker validation rules
- fake-agent acceptance shortcuts

## Failure Class 1: Direct Runner Setup Confusion

Observed or likely problems:

- `GAPFORGE_CODEX_COMMAND` is unset.
- The command template omits `{task_pack}`, `{outputs_dir}`, or `{model}`.
- The configured command runs in the wrong working directory.
- The command exits `0` but writes no files to `{outputs_dir}`.
- The command writes markdown instead of the expected JSON patches.
- The command writes valid-looking files outside the task outputs directory.

v0.4.1 fixes:

- Add `gapforge setup-codex`.
- Add `gapforge codex-doctor --task-id <task-id>`.
- `setup-codex` should print all required env vars, current values with secrets redacted, and exactly which execution modes are available.
- `codex-doctor` should inspect a task pack, command template, expected output files, output directory, validation state, import state, attestation, and human review state.
- Direct command docs must show a template that writes to `{outputs_dir}`.

Target command shape:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=codex
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'

gapforge setup-codex
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge codex-doctor --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct
gapforge codex-doctor --task-id <task-id>
```

## Failure Class 2: Handoff Confusion

Observed or likely problems:

- The user does not know which text to paste into Codex.
- Codex writes output to the wrong directory.
- Codex writes prose markdown instead of JSON.
- Codex writes one JSON file when the validator expects several.
- The user imports before validation.
- The user attests before validated import.
- The user accepts a campaign review before confirming the run was actual.

v0.4.1 fixes:

- Add `gapforge codex-handoff --task-id <task-id>` as a clearer alias/successor to `task-handoff`.
- Generate a short `HANDOFF.md` with:
  - exact task objective
  - exact files Codex must read
  - exact files Codex must write
  - absolute output directory
  - minimal valid JSON examples
  - validation/import/attestation/review commands
  - failure conditions
- Include a final copy-paste block labeled `Paste this into Codex/GPT-5.4`.

Target task-pack flow:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge codex-handoff --task-id <task-id>
# Paste HANDOFF.md into Codex/GPT-5.4.
# Ensure Codex writes JSON to the task outputs directory.
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
```

Manual-handoff mode uses the same sequence, but the attestation method should be `manual_handoff`.

## Failure Class 3: Validation Friction

Observed or likely problems:

- Validation errors are correct but too hard to act on.
- Required output files are too strict for partial tasks.
- Unknown IDs are rejected without showing valid examples.
- Fake citations are rejected without explaining how to convert them into search requests.
- Repair prompts do not include enough schema context.

v0.4.1 fixes:

- `codex-doctor` should summarize missing files, invalid JSON, invalid IDs, fake citations, unsupported claims, missing prior work, and import blockers.
- Validation errors should include:
  - failing file
  - JSON path
  - reason
  - valid ID examples
  - repair suggestion
- Repair prompts should preserve accepted partial fields where safe and ask Codex only to fix rejected fields.
- Minimal valid output examples should be included for each task type.

Minimal valid output example for a novelty task:

```json
{
  "novelty_dossiers": [
    {
      "target_id": "gap-001",
      "idea_summary": "Unknown until closest prior work is checked.",
      "query_plan": ["exact title query", "method metric query"],
      "candidates_considered": [],
      "top_prior_work": [],
      "comparison_table": [],
      "decisive_difference_needed": "Run additional closest-prior-work search.",
      "missing_searches": ["Semantic Scholar related work", "OpenReview exact method search"],
      "verdict": "unknown",
      "confidence": "low",
      "evidence_spans": [],
      "reviewer_objection": "Coverage is too weak to claim novelty.",
      "recommended_action": "search_more"
    }
  ]
}
```

## Failure Class 4: Actual-Run Acceptance Confusion

Observed or likely problems:

- Fake-agent canary passing is mistaken for real acceptance.
- Task-pack output is imported without attestation.
- Human review accepts a non-actual campaign.
- Release gate output is long and the key blocker is missed.

v0.4.1 fixes:

- `setup-codex` should say whether the current environment can produce actual-run evidence.
- `codex-doctor` should say whether a task can count as actual-run evidence.
- Campaign review should warn when no actual Codex/GPT-5.4 attestation/import exists.
- Release gate docs should state the exact blocker summary at the top.
- Fake-agent artifacts should be visibly labeled `fake_not_actual`.

## Implementation Checklist

- [ ] Add `gapforge setup-codex`.
- [ ] Add `gapforge codex-handoff --task-id <task-id>`.
- [ ] Add `gapforge codex-doctor --task-id <task-id>`.
- [ ] Improve `HANDOFF.md` with copy-paste prompt and exact output paths.
- [ ] Add minimal valid JSON examples for each supported task type.
- [ ] Improve validation errors with JSON path, valid IDs, and repair suggestions.
- [ ] Ensure partial tasks can validate partial expected outputs only when the task spec allows them.
- [ ] Add tests for direct-run no-output success failure.
- [ ] Add tests for markdown-output instead of JSON.
- [ ] Add tests for wrong output directory.
- [ ] Add tests for fake-agent canary not counting as real acceptance.

## Out of Scope

- New paper sources.
- New retrieval models.
- New LLM research skills.
- New manuscript features.
- Any CI dependency on Codex/GPT-5.4.
- Any acceptance path that bypasses validation, attestation, or human review.
