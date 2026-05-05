# GapForge

GapForge is a Codex-powered Research Ideation OS. It turns a broad topic into auditable research state: papers, notes, claims, evidence, gaps, novelty dossiers, experiment plans, reviewer objections, and reports.

GapForge v0.3 is a semantic, project-memory-aware, optionally LLM-assisted research ideation system. It is still not an exhaustive autonomous literature reviewer. It is full-text-aware and evidence-located, with hybrid retrieval, conservative novelty checking, and manuscript package export. Deterministic and offline-safe paths remain the default.

## Version Lineage

- **v0.1**: deterministic research OS foundation with run state, source connectors, skill orchestration, claim ledger, novelty gate, evals, and reports.
- **v0.2**: full-text evidence and novelty dossier upgrade with PDF artifacts, sections, evidence spans, source coverage, citation graph, gap evidence matrices, human review, and strict reports.
- **v0.3**: semantic plus LLM-assisted plus multi-run project-memory upgrade with hybrid retrieval, source policy profiles, active loop decisions, related-work matrices, direction maturation, protocols, review queues, dashboard, and paper packages.

## Why Not Just Summarization?

A summarizer compresses papers. GapForge tracks beliefs, evidence, uncertainty, and rejected ideas.

GapForge keeps:

- durable run and project directories
- normalized paper metadata, local artifacts, parsed sections, and evidence spans
- a claim ledger with support, counterevidence, confidence, and verification state
- source coverage and stopping assessments
- closest-prior-work novelty dossiers
- human review records and review queues
- research directions that mature from seed to manuscript-ready or rejected
- final reports that distinguish evidence-backed claims from hypotheses

The system is intentionally skeptical. It should attack an idea before recommending it, and it should not claim novelty until closest prior work and missing searches are explicit.

## Installation

Requires Python 3.11+.

```bash
git clone <repo-url> GapForge
cd GapForge
python -m venv .venv
source .venv/bin/activate
make install
```

Equivalent:

```bash
python -m pip install -e ".[dev]"
```

## v0.3 Quickstart

Run a deterministic, offline-safe v0.3 smoke workflow:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
gapforge report --strict
gapforge coverage
```

Run the full project-level offline v0.3 smoke target:

```bash
make v3-smoke
```

`make v3-smoke` initializes a temporary project, runs the staged v0.3 path offline with a small budget, builds the project retrieval index, writes the project report, and generates the static dashboard. It checks for `project_report.md`, `source_coverage.md`, `final_report.md`, `direction_maturity_report.md`, `related_work_matrix.md`, `review_queue.md`, and `dashboard/index.html`. Active-loop decisions are generated only by `gapforge run --v3 --active` and are written to `active_decisions.md`.

Expected behavior:

- network PDF/search expansion steps skip with coverage warnings
- retrieval index artifacts are built from fallback/offline state
- strict report remains conservative and may refuse a top direction
- outputs are smoke-test artifacts, not real literature conclusions

Current verification status from the May 5, 2026 local pass:

- Deterministic checks passed: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `make coverage`, `make v2-smoke`, and `make v3-smoke`.
- Fake-agent canary passed with valid schema validation.
- Actual Codex/GPT-5.4 canaries did not run because `GAPFORGE_ENABLE_REAL_RUNS` and agent settings were not configured in the environment.
- Real-run acceptance is therefore **not complete** and must not be claimed until a human-reviewed actual Codex/GPT-5.4 canary is accepted.

## Project Memory Workflow

Use project memory when several runs belong to one research program:

```bash
gapforge init-project "monitoring collusion research"
gapforge run "low false positive collusion detection" --v3 --project-id monitoring-collusion-research --max-papers 20
gapforge sync-project-memory --project-id monitoring-collusion-research
gapforge project-status --project-id monitoring-collusion-research
gapforge project-report --project-id monitoring-collusion-research
```

Project memory deduplicates papers across runs, preserves rejected ideas and human decisions, and stores research directions that can mature over time. Prior project memory is context, not newly verified evidence.

## Hybrid Retrieval Workflow

Build and inspect a local hybrid lexical/semantic index:

```bash
gapforge build-index --run-id <run-id>
gapforge search-index --run-id <run-id> "low false positive evaluation benchmark" --top-k 20
gapforge explain-retrieval --run-id <run-id> "closest prior work low FPR"
```

For project memory:

```bash
gapforge build-index --project-id <project-id>
gapforge search-index --project-id <project-id> "monitor evasion limitation" --top-k 20
```

The default semantic path uses deterministic local hash embeddings. Live embedding APIs are not required.

## Optional LLM Workflow

LLM-backed skills are opt-in. Tests and default runs do not require live model calls.

```bash
export GAPFORGE_LLM_MODE=prompt-pack   # off|prompt-pack|fake|provider
gapforge prompt-pack --run-id <run-id> --skill deep-reading
gapforge read-llm --run-id <run-id> --tier 1 --dry-run-prompts
```

Fake mode is deterministic:

```bash
export GAPFORGE_LLM_MODE=fake
gapforge read-llm --run-id <run-id> --tier 1 --fake
gapforge mine-gaps-llm --run-id <run-id> --fake
gapforge novelty-check-llm --run-id <run-id> --all --fake
```

Provider mode is optional and must validate JSON before state is updated. Model outputs must cite paper IDs and EvidenceSpan locators when source-backed. Hidden chain-of-thought must not be requested or stored.

## Codex/GPT-5.4 Agent Run Modes

`gapforge run --v3` supports explicit execution modes:

```bash
gapforge run "topic" --v3 --mode deterministic
gapforge run "topic" --v3 --mode prompt-pack --agent codex --llm-novelty
gapforge run "topic" --v3 --mode fake-agent --agent fake --llm-gaps
gapforge run "topic" --v3 --mode llm-assisted --agent codex --model gpt-5.4 --require-real-agent
```

Deterministic mode is the default. Prompt-pack mode writes Codex task packs without live calls. Fake-agent mode is CI-safe and validates task-pack/schema plumbing. `llm-assisted --agent codex --require-real-agent` requires `GAPFORGE_ENABLE_REAL_RUNS=1`; otherwise the run fails rather than pretending actual validation passed.

## Deterministic Tests vs Actual Runs

GapForge separates automated validation from actual research-agent validation:

- **Level 0 deterministic tests**: no LLM, CI-safe, validates code, schemas, persistence, reports, and evals.
- **Level 1 offline smoke tests**: no LLM and no network, validates orchestration safety.
- **Level 2 fake LLM tests**: fake model only, validates JSON guards and evidence gates.
- **Level 3 prompt-pack dry runs**: no live calls, validates Codex/GPT-5.4 prompts and schemas.
- **Level 4 Codex/GPT-5.4 canary runs**: real model/agent, private/manual, validates actual LLM-assisted research skills.
- **Level 5 human-reviewed acceptance**: human review of canary outputs and recorded decisions.

CI must not require Codex/GPT-5.4. Actual Codex/GPT-5.4 assisted runs are required before a v0.3 release can claim real-run validation, but they are not part of normal automated tests. If Codex/GPT-5.4 is unavailable, actual-run validation has not passed. Never fake a canary pass.

See:

- `docs/V0_3_REAL_RUN_ACCEPTANCE.md`
- `docs/V0_3_CANARY_RUNS.md`
- `docs/CODEX_RESEARCH_AGENT.md`
- `docs/REAL_RUN_REVIEW_CHECKLIST.md`
- `docs/releases/v0.3.0-real-run-acceptance.md`

## Manuscript Package Workflow

Manuscript exports are starter kits, not finished papers:

```bash
gapforge create-direction --project-id <project-id> --gap-id <gap-id>
gapforge related-work-matrix --project-id <project-id> --direction-id <direction-id>
gapforge mature-direction --project-id <project-id> --direction-id <direction-id>
gapforge experiment-protocol --project-id <project-id> --direction-id <direction-id>
gapforge review-panel --project-id <project-id> --direction-id <direction-id>
gapforge export-paper-package --project-id <project-id> --direction-id <direction-id>
```

Exports include outlines, related-work matrix, protocol, limitations, reviewer objections, rebuttal plan, bibliography, claim ledger, and evidence index. They must not invent results.

## Active v0.3 Loop

Use the active loop when GapForge should decide whether to search, parse, read, expand citations, check novelty, request human review, or stop:

```bash
gapforge run "low false positive collusion detection" --v3 --active --budget small --source-profile ai_safety
gapforge active-decisions --run-id <run-id>
```

Every decision is written to `active_decisions.md`.

## Common CLI

```bash
gapforge --help
gapforge init-topic "topic"
gapforge run "topic"
gapforge run "topic" --v2 --max-papers 20
gapforge run "topic" --v3 --project-id <project-id> --build-index --mature-directions
gapforge dashboard --run-id <run-id>
gapforge review-queue --run-id <run-id>
gapforge audit-artifacts --run-id <run-id>
```

## Architecture

Core layers:

- `src/gapforge/models.py`: typed run, project, evidence, retrieval, review, and export models
- `src/gapforge/state.py`: durable run persistence and validation
- `src/gapforge/project_memory.py`: multi-run project memory
- `src/gapforge/orchestrator.py`: v0.1/v0.2/v0.3 orchestration
- `src/gapforge/orchestration/`: active loop decisions and budgets
- `src/gapforge/sources/`: source connectors, coverage, ranking, and policies
- `src/gapforge/skills/`: deterministic and optional LLM-backed skills
- `src/gapforge/retrieval/`: local hybrid retrieval
- `src/gapforge/reporting.py`: conservative Markdown/JSON reports

See `docs/ARCHITECTURE.md`.

## Evaluation Philosophy

Evals are offline and fixture-driven. They measure behavior such as specificity, evidence linkage, duplicate rejection, source coverage transparency, retrieval relevance, direction maturity, and manuscript honesty. They do not prove real scientific usefulness.

```bash
make eval
gapforge eval --v2
gapforge eval --v3
```

## Limitations and Safety Notes

- GapForge does not perform exhaustive literature review.
- Offline fallback outputs are smoke tests.
- Semantic retrieval is a ranking aid, not proof of novelty.
- LLM outputs are untrusted until schema-valid and evidence-located.
- PDFs, transcripts, and generated dashboards may be unsafe to commit.
- Human review is required before treating any direction as research-ready.

Use:

```bash
gapforge audit-artifacts --run-id <run-id>
gapforge export-safe-bundle --project-id <project-id>
```

## Roadmap

- v0.1: deterministic research OS foundation
- v0.2: full-text evidence and novelty dossier upgrade
- v0.3: semantic, optional LLM-assisted, multi-run project-memory upgrade
- Future: stronger real-world evaluations, richer layout/OCR extraction, external reference-manager integration, experiment execution adapters, and collaborative review workflows
