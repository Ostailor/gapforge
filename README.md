# GapForge

GapForge is a Codex-powered Research Ideation OS. It turns a broad topic into auditable research state: papers, notes, claims, evidence, gaps, novelty dossiers, experiment plans, reviewer objections, and reports.

GapForge v0.4 adds campaign-level Codex/GPT-5.4 actual-run workflows on top of the v0.3 semantic, project-memory-aware, optionally LLM-assisted research system. It is still not an exhaustive autonomous literature reviewer. It is full-text-aware and evidence-located, with hybrid retrieval, conservative novelty checking, manuscript package export, campaign task packs, validated imports, human acceptance review, and a machine-checkable release gate. Deterministic and offline-safe paths remain the default.

## Version Lineage

- **v0.1**: deterministic research OS foundation with run state, source connectors, skill orchestration, claim ledger, novelty gate, evals, and reports.
- **v0.2**: full-text evidence and novelty dossier upgrade with PDF artifacts, sections, evidence spans, source coverage, citation graph, gap evidence matrices, human review, and strict reports.
- **v0.3**: semantic plus LLM-assisted plus multi-run project-memory upgrade with hybrid retrieval, source policy profiles, active loop decisions, related-work matrices, direction maturation, protocols, review queues, dashboard, and paper packages.
- **v0.4**: actual Codex/GPT-5.4 agentic campaign release path with campaign-level state, task packs, direct/handoff runner support, strict validated import, repair/rollback, campaign dashboards/reports, v4 evals, and release gates. Fake-agent success still does not count as real-run acceptance.

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

## v0.4 Campaign Quickstarts

v0.4 introduces project-level campaigns. Campaigns coordinate search, source coverage, retrieval, Codex task packs, validated imports, novelty loops, reviewer loops, experiment protocols, code-task handoff, dashboards, and human acceptance. For the complete Codex command path, see [docs/CODEX_QUICKSTART.md](docs/CODEX_QUICKSTART.md).

### Deterministic Campaign

This is the safest first run. It does not use Codex/GPT-5.4 and does not count as actual-run acceptance.

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge init-project "v4 deterministic campaign"
gapforge campaign-create "low false positive collusion detection" --project-id v4-deterministic-campaign
gapforge campaign-run --campaign-id <campaign-id> --mode deterministic --max-iterations 3
gapforge campaign-report --campaign-id <campaign-id>
gapforge dashboard --project-id v4-deterministic-campaign --include-actual-runs
```

### Fake-Agent Campaign Smoke

Fake-agent mode is CI-safe. It exercises task-pack, schema, validation, import, and campaign-state plumbing. It is never evidence that Codex/GPT-5.4 worked.

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge eval --v4 --write-report
```

### Codex Task-Pack Actual-Run Workflow

Use this when no stable direct Codex runner is configured. It can count as real actual-run evidence only after Codex/GPT-5.4 writes outputs, GapForge validates/imports them, a human attests the task, and campaign review accepts the result.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge latest-codex-task --campaign-id <campaign-id>
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 manually and write JSON outputs into outputs/.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

If validation fails, repair without weakening validation:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
gapforge validate-repair-output --repair-id <repair-id>
gapforge import-repair-output --repair-id <repair-id>
```

### Direct Runner Workflow

Use direct mode only when a trusted local Codex command runner is configured. Preview it before execution.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=direct
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'
gapforge setup-codex
gapforge codex-command-preview --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct --dry-run
gapforge codex-run --task-id <task-id> --direct
gapforge validate-import-all --task-id <task-id>
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
```

### Campaign Acceptance and Release Gate

Campaign completion is not acceptance. Acceptance requires validated imports, actual-run attestation when task-pack/manual-handoff is used, source coverage, explicit stop reason, campaign report, and human review. Fake-agent campaigns are excluded.

```bash
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
gapforge v4-release-gate --project-id <project-id> --write-report
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
```

`gapforge v4-release-gate` requires deterministic CI evidence, a passed fake-agent campaign canary, at least three accepted real Codex/GPT-5.4 campaigns, one experiment-ready campaign, one strict-refusal campaign, and one manual-PDF/full-text campaign. If those artifacts are missing, the gate fails closed.

Current verification status from the May 6, 2026 local pass:

- Deterministic checks passed: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `gapforge eval --v4 --write-report`, `make coverage`, `make v2-smoke`, `make v3-smoke`, and `make v4-smoke`.
- Fake-agent campaign canary passed with valid schema validation.
- Direct Codex/GPT-5.4 execution was available through the local `codex` CLI.
- Three real Codex/GPT-5.4 workflow canaries were validated/imported, attested, and human-reviewed: one refusal canary, one manual-PDF/full-text reading canary, and one fixture-backed experiment-ready canary.
- `gapforge v4-release-gate --write-report --json` passed with 3 accepted real campaigns and no blockers. These are release-gate workflow canaries, not evidence of exhaustive literature-review quality.

### v0.4.1 Codex Workflow Commands

v0.4.1 is scoped to Codex workflow reliability. The main commands are:

```bash
gapforge setup-codex
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

The v0.4.1 golden path is the single-task handoff canary:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 and write JSON outputs to outputs/.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-canary-complete --canary-id <canary-id>
```

See `docs/CODEX_QUICKSTART.md`, `docs/V0_4_1_CODEX_FIX_PLAN.md`, `docs/V0_4_1_CODEX_ACCEPTANCE.md`, and `docs/V0_4_1_CODEX_TROUBLESHOOTING.md`.

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

GapForge separates deterministic runs, fake-agent tests, task-pack handoff, and direct Codex execution:

```bash
gapforge run "topic" --v3 --mode deterministic
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge codex-run --task-id <task-id> --direct --dry-run
```

Deterministic mode is the default. Fake-agent mode is CI-safe and validates task-pack/schema plumbing. Task-pack handoff can count only after real Codex/GPT-5.4 output, validation, import, attestation, and human review. Direct mode can count only after valid output/import and human review.

## Deterministic Tests vs Actual Runs

GapForge separates automated validation from actual research-agent validation:

- **Level 0 deterministic tests**: no LLM, CI-safe, validates code, schemas, persistence, reports, and evals.
- **Level 1 offline smoke tests**: no LLM and no network, validates orchestration safety.
- **Level 2 fake LLM tests**: fake model only, validates JSON guards and evidence gates.
- **Level 3 prompt-pack/task-pack dry runs**: no live calls, validates Codex/GPT-5.4 prompts and schemas.
- **Level 4 Codex/GPT-5.4 canary runs**: real model/agent, private/manual, validates actual LLM-assisted research skills.
- **Level 5 human-reviewed acceptance**: human review of canary outputs and recorded decisions.

CI must not require Codex/GPT-5.4. Actual Codex/GPT-5.4 assisted runs are required before a release can claim real-run validation, but they are not part of normal automated tests. If Codex/GPT-5.4 is unavailable, actual-run validation has not passed. Never fake a canary pass.

For v0.4, the bar is higher: fake-agent tests and prompt-pack dry runs remain necessary but are not sufficient. v0.4 actual-run acceptance requires multiple real Codex/GPT-5.4 agentic campaigns with validated imports, campaign artifacts, strict-report checks, and human acceptance reviews. A task-pack handoff may support acceptance only after real Codex/GPT-5.4 outputs are imported, validated, attested, and reviewed.

See:

- `docs/CODEX_QUICKSTART.md`
- `docs/V0_3_REAL_RUN_ACCEPTANCE.md`
- `docs/V0_3_CANARY_RUNS.md`
- `docs/V0_4_ROADMAP.md`
- `docs/V0_4_ACCEPTANCE_CRITERIA.md`
- `docs/V0_4_REAL_RUN_ACCEPTANCE.md`
- `docs/V0_4_AGENTIC_CAMPAIGNS.md`
- `docs/CODEX_RESEARCH_AGENT.md`
- `docs/REAL_RUN_REVIEW_CHECKLIST.md`
- `docs/releases/v0.3.0-real-run-acceptance.md`
- `docs/releases/v0.4.0-real-run-acceptance.md`
- `docs/releases/v0.4.0.md`

Latest v0.4 validation status: deterministic checks, the fake-agent campaign canary, and the v0.4 actual-run release gate passed locally on May 6, 2026. The accepted real Codex/GPT-5.4 campaigns were workflow canaries with conservative/fixture-backed outputs; they validate the actual-run path, not exhaustive autonomous research quality.

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
gapforge eval --v4
```

## Limitations and Safety Notes

- GapForge does not perform exhaustive literature review.
- Offline fallback outputs are smoke tests.
- Semantic retrieval is a ranking aid, not proof of novelty.
- LLM outputs are untrusted until schema-valid and evidence-located.
- Fake-agent outputs validate plumbing only and never count as real Codex/GPT-5.4 research.
- Prompt-pack handoff counts as real only after Codex/GPT-5.4 outputs are validated, attested, and human-reviewed.
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
- v0.4: actual Codex/GPT-5.4 agentic campaign execution path, campaign recovery, multi-step canaries, v4 evals, and strict human-reviewed real-run acceptance gates
- Future: stronger real-world evaluations, richer layout/OCR extraction, external reference-manager integration, experiment execution adapters, and collaborative review workflows
