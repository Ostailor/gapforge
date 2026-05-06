# GapForge Architecture

GapForge is a skills-based research ideation OS. It is not a rigid one-pass summarizer; it is a durable research state machine with evidence, uncertainty, and review gates.

## Versioned Architecture

- **v0.1 foundation**: run-local state, source connectors, deterministic skills, claim ledger, novelty gate, evaluator harness, CLI, and reports.
- **v0.2 evidence layer**: PDF artifacts, parsed sections, EvidenceSpan locators, source coverage, citation graph, related-work expansion, novelty dossiers, gap evidence matrices, human review, and strict reports.
- **v0.3 project and retrieval layer**: project memory across runs, hybrid retrieval, source policy profiles, active loop decisions, optional LLM-backed skills, related-work matrices, direction maturation, experiment protocols, review queues, dashboards, and manuscript packages.
- **v0.4 campaign and actual-run layer**: campaign state, campaign controller decisions, Codex/GPT-5.4 task packs, direct/handoff runner paths, strict output import validation, repair/rollback, novelty re-search loops, campaign reviewer loops, experiment code tasks, campaign canaries, human acceptance gates, and release-gate enforcement.
- **v0.5 real-literature quality layer**: live source health diagnostics, planned multi-round search strategies, paper canonicalization, prior-work recall gates, real-literature campaign records, human research-quality review, dashboards/reports for quality acceptance, and v5 release-gate enforcement.
- **v0.6 empirical execution layer**: experiment workspaces, dataset/baseline/metric registries, run manifests, execution records, result artifacts, statistical analysis, reproducibility checks, empirical reviewer panels, paper package v2 exports, experiment dashboards, and v6 release-gate enforcement.

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

12. **Real-literature campaign quality**
   - `src/gapforge/sources/health.py` and `src/gapforge/sources/live_diagnostics.py` check whether source connectors are reachable and returning live-looking results.
   - `src/gapforge/search_strategy/` plans initial, survey, benchmark, novelty, adjacent-field, and counterevidence rounds before synthesis.
   - `src/gapforge/sources/canonical.py` deduplicates paper records by DOI, arXiv/OpenReview/Semantic Scholar ID, exact normalized title, and conservative title/author/year similarity.
   - `src/gapforge/novelty/recall_gate.py` blocks strong novelty until required prior-work searches are complete.
   - `src/gapforge/real_literature/` defines profiles, dry-run planning, campaign records, and human quality review.
   - `src/gapforge/release_gate/v05.py` separates workflow acceptance from research-quality acceptance.

13. **Experiment execution and empirical validation**
   - `src/gapforge/experiments/` manages experiment workspaces, manifests, execution records, logs, result artifacts, and reproducibility checks.
   - `src/gapforge/datasets/`, `src/gapforge/baselines/`, and `src/gapforge/metrics/` make data, comparators, and measurements first-class.
   - `src/gapforge/experiment_code/` scaffolds runnable workspace code and creates bounded Codex implementation tasks under the workspace code root.
   - `src/gapforge/results/` parses metrics artifacts into `MetricResult` and `EmpiricalClaim` records, then analyzes uncertainty.
   - `src/gapforge/reviewers/empirical.py` reviews executed artifacts, statistics, reproducibility, missing baselines, and result overclaim.
   - `src/gapforge/export/paper_package.py` v2 exports separate planned protocols, smoke/pilot/main results, failed runs, hypothetical expected results, and limitations.
   - `src/gapforge/release_gate/v06.py` fails closed unless execution, failure/negative path, result parsing, reproducibility, empirical review, and package artifacts exist.

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

## v0.5 Real-Literature Campaign Flow

The v0.5 flow adds research-quality gates before Codex synthesis:

```text
dry-run broad campaign
-> live source health diagnostic
-> source-policy-aware search strategy
-> execute search rounds and record failures
-> canonicalize duplicate papers
-> triage/read priority papers
-> build retrieval index
-> mine gaps and counterevidence
-> run prior-work recall gate
-> ask Codex for bounded research synthesis only after evidence/search gates
-> validate/import Codex patches
-> build related-work matrix and experiment protocol or refusal
-> human research-quality review
-> v5 release gate
```

The controller should refuse recommendations when live coverage is disabled, fallback records dominate, required prior-work rounds are missing, or closest prior work likely solves the gap.

## v0.6 Experiment Execution Flow

The v0.6 flow starts only after an experiment-ready direction exists:

```text
experiment-ready direction
-> create experiment workspace
-> register datasets, baselines, and metrics
-> scaffold runnable code and Codex implementation tasks
-> create run manifest
-> execute smoke, pilot, main, ablation, negative-control, or reproduction run
-> capture stdout/stderr, return code, expected outputs, and result artifact hashes
-> parse metrics_json artifacts into MetricResult records
-> create empirical claims only from parsed result artifacts
-> analyze uncertainty and low-FPR sample-size risk
-> run reproducibility checker
-> run empirical reviewer panel
-> export paper package v2 with result labels and failed/negative paths
-> v6 release gate
```

Run type matters. `smoke` proves wiring and artifact production only. `pilot` can inform design but should be labeled exploratory. `main`, `ablation`, `negative_control`, and `reproduction` runs may support empirical claims only when execution records and result artifacts exist.

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
- v0.5 research-quality acceptance additionally requires live source diagnostics, search strategy/rounds, canonicalized papers, prior-work recall, closest-prior-work evidence, and human quality review.
- v0.6 empirical claims additionally require run manifests, execution records, result artifacts, parsed metrics, uncertainty analysis, and reproducibility status.
- Smoke results, placeholder data, and fixture outputs must be labeled and must not be presented as real empirical success.
- Failed and negative runs must remain visible in reports, dashboards, reviewer panels, and paper packages.
