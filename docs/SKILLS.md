# Skills

GapForge skills exist in two forms:

- Python implementations under `src/gapforge/skills/`
- Codex-readable packages under `skills/*/SKILL.md`

The Python skills transform `ResearchRunState`. The Codex skill packages tell a future agent how to perform the same work safely, with provenance, evidence, and uncertainty discipline.

## Skill Set by Version

| Skill | v0.1 | v0.2 | v0.3 | v0.4 | CLI |
| --- | --- | --- | --- | --- | --- |
| Literature Cartographer | field map | refreshed maps | retrieval/project context aware | campaign input artifact | `gapforge map` |
| Paper Triage | tiering | role-aware ranking | source/full-text/retrieval-aware prioritization | campaign reading priority | `gapforge triage`, `gapforge rank-papers` |
| Deep Reading | abstract notes | full-text sections and evidence spans | optional LLM reading with locator validation | Codex campaign task input/output | `gapforge read`, `gapforge read-llm` |
| Gap Mining | heuristic gaps | evidence matrices | retrieval-backed counterevidence and optional LLM synthesis | campaign gap synthesis task | `gapforge mine-gaps`, `gapforge mine-gaps-llm` |
| Cross-Domain Analogy | query suggestions | transfer candidates | evidence-backed adjacent-field promotion | campaign search/gap input | `gapforge analogies` |
| Novelty Gate | lexical novelty | novelty dossiers | retrieval/citation/project-memory and optional LLM comparison | novelty re-search loop | `gapforge novelty-check`, `gapforge novelty-check-llm`, `gapforge novelty-loop` |
| Experiment Designer | experiment plans | novelty-gated plans | executable protocols and baseline candidates | code-task handoff source | `gapforge design-experiments`, `gapforge experiment-protocol` |
| Reviewer Simulation | objections | readiness summary | review panel and rebuttal planning | campaign reviewer loop | `gapforge review`, `gapforge review-panel`, `gapforge reviewer-loop` |
| Project Memory | - | - | cross-run corpus, decisions, directions | campaign parent state | `gapforge init-project`, `gapforge sync-project-memory` |
| Hybrid Retrieval | - | - | local retrieval index | task context selection | `gapforge build-index`, `gapforge build-task-context` |
| Related-Work Matrix | - | - | prior-work taxonomy per direction | campaign readiness gate | `gapforge related-work-matrix` |
| Direction Maturation | - | - | seed to manuscript-ready gates | campaign stop/readiness input | `gapforge create-direction`, `gapforge mature-direction` |
| Manuscript Export | - | - | paper package and BibTeX | campaign package/export step | `gapforge export-paper-package` |
| Campaign Controller | - | - | - | auditable campaign loop | `gapforge campaign-run`, `gapforge campaign-next` |
| Codex Campaign Task | - | - | task packs | campaign task packs/handoff | `gapforge campaign-task`, `gapforge codex-handoff` |
| Agent Output Validator | - | - | validated import | repair/rollback campaign import | `gapforge validate-import-all`, `gapforge codex-doctor` |
| Novelty Research Loop | - | - | novelty dossiers | iterative novelty re-search | `gapforge novelty-loop` |
| Experiment Code Task | - | - | protocols | Codex code task handoff | `gapforge generate-code-tasks`, `gapforge codex-code-task` |
| Campaign Reviewer Panel | - | - | review panels | campaign rebuttal/fix loop | `gapforge reviewer-loop` |
| Real-Run Acceptance | - | - | canary review | campaign release gate | `gapforge campaign-acceptance`, `gapforge v4-release-gate` |

## v2.2 Selected Pilot Benchmark Skills

| Skill | Purpose | CLI |
| --- | --- | --- |
| Pilot Power Plan | Power-gate pilot and main alpha targets | `gapforge selected-pilot-power-plan`, `gapforge selected-pilot-power-check` |
| Honest Null Distribution | Expand benign/null traces and hard negatives | `gapforge honest-null-scenarios`, `gapforge generate-honest-null`, `gapforge honest-null-report` |
| Collusive Alternative Distribution | Expand positive collusive scenarios | `gapforge collusive-scenarios`, `gapforge generate-collusive-traces`, `gapforge collusive-distribution-report` |
| Pilot Trace Dataset | Build pilot dataset cards and alpha support fields | `gapforge build-pilot-trace-dataset`, `gapforge pilot-trace-dataset-report` |
| Pilot Baseline Calibration | Calibrate and run pilot baselines without leakage | `gapforge calibrate-monitor`, `gapforge run-pilot-baselines`, `gapforge pilot-baseline-report` |
| Pilot Result Analysis | Analyze pilot metrics, low-FPR caveats, and errors | `gapforge selected-pilot-analysis`, `gapforge selected-pilot-report` |
| Selected Related Work | Attach prior-work recall and related-work matrix | `gapforge selected-benchmark-prior-work`, `gapforge selected-benchmark-related-work`, `gapforge selected-benchmark-novelty-report` |
| Pilot Reviewer | Generate pilot reviewer panel and fix list | `gapforge selected-pilot-review`, `gapforge selected-pilot-fix-list` |
| Pilot Manuscript | Generate pilot manuscript and paper package | `gapforge selected-pilot-manuscript`, `gapforge selected-pilot-paper-package` |

These skills preserve v2.2 result discipline: smoke, pilot, and main maturity stay separate; synthetic pilot data does not prove deployment validity; `alpha=0.001` remains blocked unless powered; prior-work gaps and reviewer blockers stay visible.

## Shared Rules

- Do not invent citations, quotes, datasets, metrics, results, or venues.
- Separate metadata/abstract-only notes from full-text notes.
- Use EvidenceSpan locators whenever full-text evidence exists.
- Add claim ledger entries for nontrivial claims.
- Store concise public reasoning summaries only; never store hidden chain-of-thought.
- Mark uncertainty explicitly.
- Find closest prior work before claiming novelty.
- Preserve rejected ideas and human decisions.
- Prefer decisive experiments over vague ideas.
- Attack an idea before recommending it.
- Distinguish deterministic, fake-agent, task-pack/manual-handoff, and direct Codex modes.
- Never count fake-agent outputs as real Codex/GPT-5.4 acceptance.

## Optional LLM Skills

LLM-backed skills are optional and disabled by default.

Modes:

- `GAPFORGE_LLM_MODE=off`: deterministic path only
- `prompt-pack`: write prompts, make no model calls
- `fake`: deterministic fake client for tests
- `provider`: opt-in real provider adapter

LLM outputs must be schema-valid before state changes. Unsupported model claims are rejected, downgraded, or marked uncertain. Model-generated citations are not trusted unless resolved to known paper IDs or recorded source results.

## v0.4 Campaign Skills

The v0.4 skill packages guide campaign-level work. They do not authorize unvalidated model output. Use them with:

```bash
gapforge campaign-task --campaign-id <campaign-id> --type <task-type>
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge validate-import-all --task-id <task-id>
gapforge campaign-review --campaign-id <campaign-id>
gapforge v4-release-gate --project-id <project-id>
```

Fake-agent mode validates workflow plumbing only. Task-pack/manual-handoff can support real acceptance only after real Codex/GPT-5.4 output is imported, validated, attested, and human-reviewed.

## Codex Skill Package Requirements

Every `skills/*/SKILL.md` must include:

- purpose
- when to use
- inputs
- outputs
- required artifacts
- procedure
- validation checklist
- failure modes
- examples
- citation/evidence rules
- uncertainty rules
- no hidden chain-of-thought storage

Skill frontmatter descriptions must say when to load the skill, not summarize the workflow.

## Idempotence

The orchestrator may run skills multiple times after new papers, citation expansion, or project-memory sync. Skills should update stable IDs or replace their own artifacts, not blindly duplicate records.
