# GapForge v0.3 Architecture

v0.3 extends the v0.2 full-text evidence architecture with semantic retrieval, optional LLM-backed skills, multi-run project memory, stronger source policies, and idea maturation workflows. Deterministic/offline operation remains a first-class path.

## Design Principles

- Evidence first: every source-backed claim should point to a paper, section, table, reference, or evidence span.
- Retrieval is inspectable: lexical, semantic, and citation expansion results must be recorded with scores and provenance.
- LLMs are optional assistants: model outputs are candidates until schema validation and citation checks pass.
- Memory is contextual, not truth: cross-run memory can guide search and comparison, but it does not automatically verify a current-run claim.
- Coverage is policy-aware: different fields require different source mixes and stopping criteria.
- Reports stay conservative: weak coverage should produce next search steps, not confident novelty claims.

## v0.2 Baseline

v0.2 already provides:

- `PaperArtifact`, `PaperSection`, `EvidenceSpan`, and locator-backed notes
- source coverage reports and query ledgers
- citation graphs and related-work expansion hooks
- novelty dossiers and rejected ideas
- gap evidence matrices
- cross-domain transfer candidates
- human review records
- prompt packs and fake LLM clients
- strict final reports

v0.3 should build on those artifacts rather than duplicate them.

## New Architectural Layers

### Semantic Retrieval Layer

The retrieval layer should index:

- paper titles, abstracts, metadata, and roles
- parsed sections
- evidence spans
- paper notes
- claims
- gaps, hypotheses, and novelty dossiers
- selected project-memory records

Retrieval should return auditable records:

- query text
- retrieval mode: lexical, semantic, hybrid, citation, or manual
- index name and version
- object IDs and object types
- scores and score components where practical
- created timestamp and provenance

Semantic retrieval should be optional and testable with local deterministic fixtures. Live embedding providers can be added behind adapters, but tests must not require them.

### Project Memory Layer

Project memory sits above run state:

```text
projects/{project_id}/
  project.json
  memory.json
  papers.json
  claims.json
  evidence_index.json
  rejected_ideas.json
  human_reviews.json
  retrieval_index/
```

Run state remains durable and self-contained. Project memory imports and links run records, preserving original run IDs and provenance. A current run can consult project memory for:

- previously seen papers
- known duplicates
- contested claims
- rejected ideas
- human-approved gaps
- prior novelty dossiers
- useful source policies

Reports must distinguish current-run evidence from project-memory context.

### LLM Adapter and Validation Layer

The existing prompt-pack and fake-client abstractions should grow into a guarded model-output path:

```text
PromptPack -> LLMClient -> raw output -> schema validation -> citation validation -> state write
```

Important boundaries:

- model output must not directly mutate state
- invalid or uncited outputs are quarantined
- generated citations must resolve to known or newly verified paper records
- public reasoning summaries are allowed; hidden chain-of-thought is not requested or stored
- deterministic skills remain available for all core workflows

### Extraction Layer

The full-text layer should support richer artifacts:

- page text
- sections
- tables and captions
- references and bibliography entries
- extraction warnings
- resolver candidates for references

Table and reference extraction should feed:

- Paper Triage: identify benchmark, dataset, survey, and method papers
- Deep Reading: support datasets, metrics, baselines, and results
- Gap Mining: detect missing baselines, metrics, datasets, and reproducibility gaps
- Novelty Gate: compare proposed experiments against prior evaluations

### Source Policy and Coverage Layer

Source policies should define expected behavior for a field:

- source connectors to use
- minimum query families
- recency and historical coverage expectations
- required citation-neighborhood expansion
- full-text expectations
- source diversity thresholds
- fallback/offline rules
- stopping criteria

Coverage reports should evaluate a run against the selected policy and feed strict report decisions.

### Idea Maturation Layer

The core state machine should mature ideas through:

```text
gap -> hypothesis -> experiment -> manuscript skeleton -> rebuttal plan
```

Each transition should require:

- evidence links
- novelty status
- source coverage status
- reviewer blockers
- human decisions when present
- explicit uncertainty

Rejected or retired ideas stay in the run or project memory to avoid repeated work.

## v0.3 Orchestration Shape

A v0.3 run should support this loop:

```text
initialize topic
-> apply source policy
-> search lexical sources
-> build/update coverage
-> retrieve from project memory
-> rank and triage
-> download/parse full text
-> extract sections/tables/references
-> build semantic index
-> deep read deterministic and/or LLM-assisted
-> mine gaps with evidence matrices
-> expand citations and related work
-> run hybrid closest-prior-work retrieval
-> produce novelty dossiers
-> mature selected gaps into hypotheses and experiments
-> simulate reviewers
-> export report/manuscript/rebuttal artifacts
```

Every stage should save state before the next stage begins. Failed sources, downloads, parsers, model calls, and resolvers should produce warnings and partial artifacts rather than collapsing the full run.

## Data Boundaries

- Run-local state remains under `runs/{run_id}/`.
- Project-level memory should not overwrite run-local artifacts.
- Cache files remain under `.gapforge_cache/` or an explicit configured cache directory.
- Prompt packs and raw model outputs should be audit artifacts, not trusted claims.
- Extracted references are unresolved until a resolver confirms them.

## Testing Architecture

v0.3 tests should include:

- deterministic lexical/semantic retrieval fixtures
- fake LLM outputs that pass and fail schema validation
- project-memory import and duplicate reconciliation
- source policy pass/fail cases
- table/reference extraction fixtures
- curated real-world eval fixtures with licensing notes
- strict report refusal under poor coverage

No test should require live source APIs, live LLM calls, hosted embedding services, or paid credentials.
