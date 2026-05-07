# Codex/GPT-5.4 Research Agent Contract

Codex using GPT-5.4 is the intended real research agent for GapForge actual-run workflows. GapForge treats Codex as an external agent whose outputs must be validated before import. Codex is not a trusted source of citations, novelty, results, or evidence by itself.

For the shortest command sequence, see `docs/CODEX_QUICKSTART.md`.

## What Codex May Do

Codex/GPT-5.4 may assist with:

- full-text paper reading
- gap synthesis
- closest-prior-work comparison
- reviewer simulation
- related-work organization
- experiment protocol critique
- campaign task execution through task packs or a configured direct runner

Codex output may become GapForge state only after schema validation and import. For task-pack/manual-handoff actual-run acceptance, human attestation and campaign review are also required.

## Non-Negotiable Rules

Codex/GPT-5.4 must:

- use only known paper IDs, EvidenceSpan IDs, and locators from the task pack
- write JSON when the output contract requires JSON
- mark unsupported items as unknown, uncertain, proposed, or search requests
- list missing searches instead of inventing prior work
- cite EvidenceSpan locators for full-text-backed claims
- store concise public reasoning summaries only

Codex/GPT-5.4 must not:

- invent citations, papers, DOIs, arXiv IDs, venues, quotes, datasets, metrics, baselines, or results
- claim strong novelty without closest prior work
- convert abstract-only evidence into demonstrated full-text results
- hide poor source coverage or missing searches
- remove rejected ideas, human decisions, or blocking issues
- request or persist hidden chain-of-thought

## Execution Modes

### Fake Agent

Fake-agent mode is for CI and regression tests. It validates orchestration, schemas, import, repair, rollback, dashboards, and release-gate blockers. It never counts as real Codex/GPT-5.4 acceptance.

```bash
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
```

### Task-Pack Handoff

Task-pack mode is the recommended v0.4.1 real-run debugging workflow when no direct runner is configured.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 manually and write outputs into outputs/.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
```

Task-pack output can count only after Codex/GPT-5.4 produced it, validation/import passed, attestation records Codex/GPT-5.4 as the producer, and campaign review accepted it.

### Manual Handoff

Manual handoff follows the same acceptance rules as task-pack mode. It is useful when Codex is run outside GapForge entirely. Handoff alone does not count.

### Direct Runner

Direct mode requires an explicit local command template. Preview it before execution.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=direct
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'

gapforge codex-command-preview --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct --dry-run
```

Direct runs count only after valid output/import and human review. If the command exits successfully but writes no valid output files, the run fails and should be repaired or rerun through task-pack handoff.

## Output Contract

The task pack tells Codex exactly which files to write. Examples include:

- `paper_notes_patch.json`
- `claims_patch.json`
- `evidence_spans_patch.json`
- `gaps_patch.json`
- `gap_evidence_matrices_patch.json`
- `novelty_dossiers_patch.json`
- `rejected_ideas_patch.json`
- `reviewer_objections_patch.json`
- `related_work_matrix_patch.json`

Codex should write only the expected output files into the task `outputs/` directory. Unknown citations should become `search_requests`, `missing_searches`, or uncertainty.

## Validation, Import, Attestation, Review

For task-pack/manual-handoff workflows:

```bash
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

For direct workflows, use the same validation/import and campaign review checks after the runner completes.

## Repair

If validation fails:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

The repair handoff includes exact validation errors, known valid paper IDs, known EvidenceSpan IDs/locators, accepted partial fields, files to rewrite, and minimal JSON skeletons. Repair cannot bypass validation.

## Acceptance Standard

Human reviewers should judge Codex/GPT-5.4 output by:

- evidence grounding
- citation honesty
- novelty caution
- source coverage transparency
- usefulness of gaps and directions
- clarity of uncertainty
- absence of fabricated results

The model's confidence is not an acceptance criterion. Evidence is.

## v0.5 Live-Literature Role

For v0.5, Codex/GPT-5.4 should be evaluated as a research campaign assistant over live literature, not just as a task-pack output generator. The bar is higher than v0.4.1 workflow acceptance.

Codex may help:

- propose source-policy-aware search queries
- read and compare retrieved papers
- identify closest prior work
- synthesize evidence-backed gaps
- classify related work
- critique experiment protocols
- recommend refusal when novelty or coverage is weak

Codex still may not:

- invent papers, citations, quotes, datasets, metrics, or results
- claim novelty without closest prior work
- treat fixture-only canaries as research-quality evidence
- override source coverage warnings
- convert model confidence into claim confidence

v0.5 live-literature acceptance requires human expert review of source coverage, closest-prior-work recall, citation grounding, gap quality, experiment protocol quality, and rejection behavior. See `docs/V0_5_REAL_LITERATURE_CAMPAIGNS.md` and `docs/V0_5_QUALITY_GATES.md`.

## v0.5 Codex Task Discipline

For live-literature campaigns, Codex should be asked to synthesize only after GapForge has recorded source health, search strategy, search rounds, canonicalization, retrieval, and prior-work recall status.

Codex task prompts should include:

- topic and source policy profile
- live source diagnostic status and missing sources
- search rounds completed and missing prior-work rounds
- allowed paper IDs, EvidenceSpan locators, and closest-prior-work candidates
- rejected ideas and human constraints
- exact JSON output contracts and validation rules

Codex outputs must:

- propose at most the requested number of directions
- cite only known paper IDs and evidence locators
- mark novelty unknown when closest prior work is missing
- turn unknown citations into search requests
- label expected results as hypothetical
- store public reasoning summaries only

Fake-agent, fixture-only, or dry-run outputs are useful for CI and usability checks. They do not count as v0.5 real-literature quality.

## v0.6 Experiment Execution Role

For v0.6, Codex/GPT-5.4 may help turn an experiment-ready direction into executable code tasks and analysis scripts. Codex remains an implementation assistant, not a source of empirical results.

Codex may help:

- scaffold experiment workspaces
- implement dataset adapters when dataset cards identify the source and access rules
- implement baselines from the baseline registry
- implement metric functions from the metric registry
- write smoke tests and validation commands
- write analysis scripts for recorded result artifacts
- summarize failed or negative runs from logs and artifacts
- critique empirical design as a reviewer

Codex must not:

- invent datasets, baselines, metrics, logs, plots, tables, p-values, confidence intervals, or result artifacts
- mark an experiment as executed
- convert a scaffold or smoke test into empirical success
- hide failed runs or negative results
- remove reproducibility warnings
- write paper package language that presents expected results as observed

For v0.6 task packs, prompts should include:

- experiment protocol ID and direction ID
- dataset cards, baseline registry, and metric registry
- run manifest schema
- expected commands and output paths
- artifact hygiene rules
- result-claim ledger rules
- explicit instruction that empirical claims require run records and result artifacts

Any Codex-generated experiment code must be validated by execution records before supporting empirical claims. If no run record and result artifact exist, the output remains scaffold or analysis preparation only.

## v0.7 Benchmark and Replication Role

For v0.7, Codex/GPT-5.4 may help implement benchmark adapters, sweep scripts, analysis utilities, and replication instructions. Codex remains an implementation and review assistant, not a benchmark authority.

Codex may help:

- implement benchmark dataset loaders after dataset cards and download/cache rules are recorded
- implement benchmark baselines from the baseline registry
- implement sweep and ablation scripts under the experiment workspace
- write comparison table and error-analysis code for existing result artifacts
- draft replication instructions from recorded manifests and environment data
- diagnose failed jobs from logs
- propose power/sample-size checks for low-FPR benchmark plans

Codex must not:

- auto-download large datasets without explicit user approval metadata
- invent benchmark results, comparison tables, error examples, p-values, confidence intervals, or replication outcomes
- hide failed jobs, missing baselines, or underpowered slices
- present fixture smoke as benchmark performance
- claim independent replication without a recorded rerun or review
- bypass v5 literature gates or v6 empirical artifact gates

For v0.7 task packs, prompts should include:

- benchmark card and dataset card
- download/cache policy and approved local paths
- compute mode and resource constraints
- run manifests and expected outputs
- baseline and metric requirements
- low-FPR power/sample-size requirements when applicable
- artifact safety rules for large data, predictions, checkpoints, and logs
- replication package requirements

Any Codex-generated benchmark code or analysis must be validated by execution records, result artifacts, and benchmark review before supporting benchmark claims.
