# GapForge Architecture

GapForge is a skills-based research ideation OS. It is not a rigid one-pass summarizer; it is a durable research state machine with evidence, uncertainty, and review gates.

## Versioned Architecture

- **v0.1 foundation**: run-local state, source connectors, deterministic skills, claim ledger, novelty gate, evaluator harness, CLI, and reports.
- **v0.2 evidence layer**: PDF artifacts, parsed sections, EvidenceSpan locators, source coverage, citation graph, related-work expansion, novelty dossiers, gap evidence matrices, human review, and strict reports.
- **v0.3 project and retrieval layer**: project memory across runs, hybrid retrieval, source policy profiles, active loop decisions, optional LLM-backed skills, related-work matrices, direction maturation, experiment protocols, review queues, dashboards, and manuscript packages.
- **v0.4 campaign and actual-run layer**: campaign state, campaign controller decisions, Codex/GPT-5.4 task packs, direct/handoff runner paths, strict output import validation, repair/rollback, novelty re-search loops, campaign reviewer loops, experiment code tasks, campaign canaries, human acceptance gates, and release-gate enforcement.

## Core Layers

1. **Models**: `src/gapforge/models.py`
   - Dataclass models for runs, projects, papers, artifacts, sections, evidence spans, claims, gaps, novelty dossiers, retrieval documents, directions, protocols, review panels, dashboards, and export packages.

2. **Run state**: `src/gapforge/state.py`
   - Writes `runs/<timestamp-topic>/`.
   - Persists JSON and Markdown artifacts after each skill/stage.
   - Validates evidence links, supported claims, novelty claims, experiments, human review locks, and source policy gates.

3. **Project memory**: `src/gapforge/project_memory.py`
   - Writes `projects/<project-id>/`.
   - Deduplicates corpus papers across runs.
   - Preserves rejected ideas, human decisions, claims, gaps, and research directions.
   - Project memory is context, not proof. Reports must distinguish current-run evidence from prior-run memory.

4. **Sources and coverage**: `src/gapforge/sources/`
   - Source connectors normalize external metadata into `Paper`.
   - `CachedHttpClient` provides timeouts, retries, user-agent, and cache.
   - Query ledger and source coverage make every search auditable.
   - Source policy profiles evaluate whether coverage is enough for mapping, gap mining, novelty, or experiment design.

5. **Skills**: `src/gapforge/skills/`
   - Skills transform `ResearchRunState`.
   - Deterministic skills remain default.
   - Optional LLM-backed variants use prompt packs, fake clients, or provider clients only when configured.
   - All skills must cite paper IDs/evidence locators for source-backed claims and store public reasoning summaries only.

6. **Retrieval**: `src/gapforge/retrieval/`
   - Builds local hybrid indexes over papers, sections, evidence spans, notes, claims, gaps, novelty dossiers, and project memory.
   - Combines deterministic lexical scoring with local hash embeddings by default.
   - Retrieval improves candidate finding; it does not prove novelty.

7. **Orchestration**: `src/gapforge/orchestrator.py`
   - Supports v0.1, v0.2, and v0.3 paths.
   - `gapforge run "topic"` keeps the original deterministic path.
   - `gapforge run "topic" --v2` adds full-text/prior-work stages.
   - `gapforge run "topic" --v3` adds source policy, project memory, retrieval, direction/review/export hooks.
   - `gapforge run "topic" --v3 --active` uses the active decision loop.

8. **Active loop**: `src/gapforge/orchestration/`
   - Decides among search more, parse more, read more, expand citations, check novelty, design experiment, request human review, and stop.
   - Every decision records reason, evidence, expected value, and cost estimate.
   - Budget limits and stopping criteria prevent unbounded expansion.

9. **Campaigns and Agent Execution**: `src/gapforge/campaigns/`, `src/gapforge/agents/`, `src/gapforge/canaries/`
   - Campaigns are first-class project objects with steps, decisions, milestones, imports, stop conditions, search requests, human reviews, and acceptance summaries.
   - Codex/GPT-5.4 task packs live under `projects/<project>/campaigns/<campaign>/agent_tasks/<task>/`.
   - Execution modes are deterministic, fake-agent, Codex task-pack, Codex direct, and manual handoff.
   - Fake-agent mode validates schemas and lifecycle only. It never counts as actual-run acceptance.
   - Direct and task-pack/handoff modes can count only after validated import, attestation, and human review.

10. **Validated import, repair, rollback, and release gates**
   - `src/gapforge/campaigns/importer.py` validates campaign output before mutation.
   - `src/gapforge/campaigns/rollback.py` creates snapshots for reversible imports.
   - `src/gapforge/agents/repair.py` creates repair prompts for invalid output.
   - `src/gapforge/release_gate/` enforces v0.4 actual-run acceptance requirements.

11. **Reports and exports**
   - `src/gapforge/reporting.py` renders conservative Markdown/JSON reports.
   - `src/gapforge/export/` writes manuscript starter packages.
   - `src/gapforge/campaigns/reporting.py` renders campaign reports with explicit stop reasons.
   - Reports must show source coverage, evidence locators, unsupported claims, rejected ideas, fake-vs-real agent mode, validation state, and uncertainty.

## v0.3 Staged Loop

`gapforge run "topic" --v3` may run:

```text
search
-> source coverage
-> source policy assessment
-> map
-> triage
-> download PDFs
-> parse full text
-> deep read
-> build retrieval index
-> mine gaps
-> analogies
-> analogy search
-> citation graph
-> related-work expansion
-> refresh retrieval index
-> novelty dossiers
-> optional LLM novelty
-> experiments when coverage permits
-> reviewer simulation
-> project memory sync
-> related-work matrices
-> optional direction maturation/protocols/package/dashboard
-> review queue
-> final report
```

Network-dependent steps skip cleanly when `GAPFORGE_DISABLE_NETWORK=1`.

## v0.4 Campaign Loop

`gapforge campaign-run --campaign-id ID` runs a campaign controller rather than a single run pipeline:

```text
load campaign/project/runs
-> assess coverage, retrieval, reading, gaps, novelty, direction maturity, review queue, budget
-> choose next decision
-> run deterministic step or create Codex campaign task pack
-> validate/import outputs when present
-> repair/rollback on invalid output
-> request human review when needed
-> stop with explicit reason
```

Common stop reasons include `ready_experiment_protocol`, `not_ready_poor_coverage`, `not_ready_novelty_unknown`, `rejected_duplicate_prior_work`, `human_review_required`, `budget_exhausted`, `agent_output_invalid`, and `manual_handoff_pending`.

Actual Codex/GPT-5.4 campaign work must enter state only through validated import. A task-pack handoff is not actual-run evidence until real Codex output is imported, attested, and accepted by human review.

## v0.3 Active Loop

`gapforge run "topic" --v3 --active --budget small` creates an active-loop run. The active loop evaluates current state, source policy, evidence coverage, novelty dossiers, review queue, and budget before selecting the next action. It can stop because coverage is sufficient, budget is exhausted, no new papers are found, or human review is needed.

## Safety Invariants

- No fabricated citations, quotes, datasets, metrics, results, or venues.
- No hidden chain-of-thought in persisted artifacts.
- Supported claims require evidence.
- Strong novelty requires closest prior work and adequate source coverage.
- Full-text claims should use EvidenceSpan locators.
- Rejected or locked human decisions must be respected.
- Offline/fallback data must be labeled as such.
- Fake-agent and prompt-pack-only outputs must not be represented as real Codex/GPT-5.4 research.
- Campaign acceptance requires explicit stop reason, validated imports when agent-backed, and human review.
