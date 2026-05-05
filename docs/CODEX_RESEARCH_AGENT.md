# Codex/GPT-5.4 Research Agent Contract

For real GapForge runs, Codex using GPT-5.4 is the intended LLM research agent. In v0.3, this was represented through prompt packs, fake-agent canaries, and validated output import, but accepted actual Codex/GPT-5.4 real-run validation was not completed. v0.4 is intended to turn this into campaign-level actual execution or auditable handoff/import workflows without weakening GapForge's evidence discipline.

## Role

Codex/GPT-5.4 may assist with:

- full-text-aware paper reading
- gap synthesis
- closest-prior-work comparison
- reviewer simulation
- report critique
- direction maturation review
- campaign-level research execution when v0.4 actual-run mode is explicitly enabled

It must not become an unverified source of citations, results, or novelty claims.

## Required Inputs

Prompts or task context should include:

- topic
- relevant paper IDs and metadata
- parsed sections or excerpted text
- EvidenceSpan locators
- current claims/gaps/novelty dossiers
- source coverage and missing searches
- output schema
- citation/evidence rules
- uncertainty rules

## Output Rules

Codex/GPT-5.4 outputs must:

- use JSON when a schema is required
- cite known paper IDs for source-backed statements
- cite EvidenceSpan locators when using full text
- mark unsupported items as unknown, uncertain, or proposed
- include concise public reasoning summaries only
- avoid hidden chain-of-thought
- preserve missing searches and coverage warnings

## Prohibited Behavior

Codex/GPT-5.4 must not:

- invent citations, DOIs, arXiv IDs, venues, datasets, metrics, quotes, or results
- mark novelty strong without closest prior work
- convert abstract claims into demonstrated results
- hide poor coverage
- remove rejected ideas or human decisions
- store hidden chain-of-thought in GapForge artifacts

## Acceptance Implications

Level 4 canary validation requires actual Codex/GPT-5.4 use. Fake LLM and prompt-pack modes are useful but do not count as actual-run validation.

If Codex/GPT-5.4 is unavailable:

- CI may still pass.
- Level 0 through Level 3 validation may still pass.
- v0.3 cannot claim actual-run validation passed.

For v0.4, actual-run acceptance requires multiple accepted real Codex/GPT-5.4 campaigns, not just one task or one fake-agent canary. A campaign must have durable state, task lifecycle records, validated imports, source/strict-report artifacts, and human review.

## Campaign Rules for v0.4

Codex/GPT-5.4 campaign execution must:

- run only under explicit real-run opt-in
- record campaign and task lifecycle state
- preserve task packs, outputs, validations, imports, failures, retries, and human decisions
- support resume or retry after failed agent steps
- fail clearly if Codex/GPT-5.4 is unavailable
- label prompt-pack handoff separately from direct actual execution
- keep fake-agent campaigns out of actual-run acceptance counts
- validate all outputs before import
- make rejected outputs auditable without mutating state

## v0.4 Execution Workflows

### Task-Pack Handoff

Use task-pack mode when a direct Codex runner is not configured:

```bash
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge task-handoff --task-id <task-id>
# Codex/GPT-5.4 reads HANDOFF.md and writes JSON outputs under outputs/.
gapforge campaign-validate-output --campaign-id <campaign-id> --task-id <task-id>
gapforge campaign-import-output --campaign-id <campaign-id> --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
```

Task-pack mode can count as an actual run only after the outputs are produced by Codex/GPT-5.4, validation passes, import records the accepted objects, attestation names Codex/GPT-5.4, and campaign human review accepts the work.

### Direct Runner

Use direct mode only when a trusted command is configured:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack}'
gapforge codex-run --task-id <task-id> --direct
```

If direct execution is unavailable, GapForge should fail clearly or write a handoff. It must not silently use fake-agent output.

### Fake Agent

Fake-agent mode is for CI and regression tests. It may validate lifecycle, schemas, repair, rollback, and release-gate blockers. It never proves Codex/GPT-5.4 behavior and never counts as actual-run acceptance.

## Campaign Task Output Contract

Codex/GPT-5.4 should write only the expected files listed in the task pack, for example:

- `paper_notes_patch.json`
- `gaps_patch.json`
- `novelty_dossiers_patch.json`
- `review_panel_patch.json`
- `stop_condition_patch.json`

Every JSON file must use the top-level key shown in `expected_outputs.json`. Unknown citations should be emitted as search requests or missing searches, not as claimed prior work.

## Repair and Recovery

If validation fails:

```bash
gapforge repair-agent-output --task-id <task-id> --path <bad-output.json> --handoff
```

The repair prompt should include validation errors, known valid IDs, locator rules, and schema examples. It must not instruct Codex to invent evidence, citations, or hidden reasoning.

## Review Standard

Human reviewers should judge Codex/GPT-5.4 outputs by:

- evidence grounding
- citation honesty
- novelty caution
- usefulness of gaps/directions
- clarity of uncertainty
- quality of reviewer objections
- absence of fabricated results

The model's confidence is not an acceptance criterion. Evidence is.
