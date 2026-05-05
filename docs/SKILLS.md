# Skills

GapForge skills exist in two forms:

- Python implementations under `src/gapforge/skills/`
- Codex-readable packages under `skills/*/SKILL.md`

The Python skills transform `ResearchRunState`. The Codex skill packages tell a future agent how to perform the same work safely, with provenance, evidence, and uncertainty discipline.

## Skill Set by Version

| Skill | v0.1 | v0.2 | v0.3 | CLI |
| --- | --- | --- | --- | --- |
| Literature Cartographer | field map | refreshed maps | retrieval/project context aware | `gapforge map` |
| Paper Triage | tiering | role-aware ranking | source/full-text/retrieval-aware prioritization | `gapforge triage`, `gapforge rank-papers` |
| Deep Reading | abstract notes | full-text sections and evidence spans | optional LLM reading with locator validation | `gapforge read`, `gapforge read-llm` |
| Gap Mining | heuristic gaps | evidence matrices | retrieval-backed counterevidence and optional LLM synthesis | `gapforge mine-gaps`, `gapforge mine-gaps-llm` |
| Cross-Domain Analogy | query suggestions | transfer candidates | evidence-backed adjacent-field promotion | `gapforge analogies` |
| Novelty Gate | lexical novelty | novelty dossiers | retrieval/citation/project-memory and optional LLM comparison | `gapforge novelty-check`, `gapforge novelty-check-llm` |
| Experiment Designer | experiment plans | novelty-gated plans | executable protocols and baseline candidates | `gapforge design-experiments`, `gapforge experiment-protocol` |
| Reviewer Simulation | objections | readiness summary | review panel and rebuttal planning | `gapforge review`, `gapforge review-panel` |
| Project Memory | - | - | cross-run corpus, decisions, directions | `gapforge init-project`, `gapforge sync-project-memory` |
| Hybrid Retrieval | - | - | local retrieval index | `gapforge build-index`, `gapforge search-index` |
| Related-Work Matrix | - | - | prior-work taxonomy per direction | `gapforge related-work-matrix` |
| Direction Maturation | - | - | seed to manuscript-ready gates | `gapforge create-direction`, `gapforge mature-direction` |
| Manuscript Export | - | - | paper package and BibTeX | `gapforge export-paper-package` |

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

## Optional LLM Skills

LLM-backed skills are optional and disabled by default.

Modes:

- `GAPFORGE_LLM_MODE=off`: deterministic path only
- `prompt-pack`: write prompts, make no model calls
- `fake`: deterministic fake client for tests
- `provider`: opt-in real provider adapter

LLM outputs must be schema-valid before state changes. Unsupported model claims are rejected, downgraded, or marked uncertain. Model-generated citations are not trusted unless resolved to known paper IDs or recorded source results.

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
