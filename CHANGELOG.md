# Changelog

All notable project changes should be recorded here.

## 0.7.0

GapForge v0.7 is the real benchmark execution and replication upgrade. It keeps the v5 literature gates and v6 empirical-claim gates intact while adding first-class benchmark artifacts, explicit dataset consent and cache handling, compute/job abstractions, benchmark canaries, replication packages, and a v7 release gate that separates fixture validation from opt-in real/local public benchmark validation.

### Benchmarks, Data, and Compute

- Added a benchmark registry with benchmark records, tasks, suites, cards, readiness checks, and fixture labeling.
- Added external dataset download planning, cache management, explicit consent records, license/terms warnings, manual-download handling, download hashes, and cache reporting.
- Added compute environment abstraction for local, Docker, GPU-local, Slurm, and custom environments with resource requests and availability checks that remain CI-safe.
- Added job runner and scheduler abstractions with local execution, queue persistence, cancellation, Docker/Slurm unavailable reporting, and execution-record integration.
- Added experiment sweeps, ablation plans, and seed plans so parameter changes and stochastic runs are explicit and controlled.

### Results, Analysis, and Comparison

- Added a result database and aggregation layer that normalizes parsed metric results, preserves run-type labels, aggregates across seeds/splits, exports CSV, and excludes failed runs from aggregates while listing them.
- Added error analysis and slice analysis from prediction artifacts, with false-positive emphasis for low-FPR contexts and no fabricated examples.
- Added benchmark comparison and leaderboard reports that separate baseline/proposed rows, smoke/pilot/main run types, internal/external sources, missing baselines, limitations, and anti-SOTA guardrails.
- Added low-FPR power planner v2 with negative-sample sizing, zero-false-positive upper bounds, alpha target guidance, exact/binomial helpers, and underpowered-claim warnings.

### Replication and Release Gates

- Added safe-by-default replication package export, replication manifests, package verification, reproduction runner, and multi-environment reproducibility matrix.
- Added benchmark canary profiles for fixture success, fixture failure, opt-in local public small benchmark, low-FPR underpowered warning, and replication package validation.
- Added a v7 release gate requiring fixture benchmark success and failure paths, benchmark comparison, aggregation, error analysis, replication export/verification, low-FPR underpowered warning coverage, no fake results, and preserved smoke/pilot/main labels.
- Added opt-in real/local public benchmark claim checks requiring an accepted real benchmark canary, dataset consent, artifact-backed results, and a replication package for the real benchmark workspace.
- Added v7 eval fixtures/metrics, dashboard pages, Python API functions, documentation, and Codex-readable benchmark/replication skills.

### Validation

- Fixture benchmark gate passed locally with successful and failed benchmark canaries, result aggregation, error analysis, replication package export/verification, and low-FPR underpowered warning coverage.
- Real benchmark validation was attempted and passed for the opt-in `local_public_small_benchmark` canary using the public UCI Iris dataset with explicit dataset consent, cached download, artifact-backed metrics and predictions, benchmark comparison, error analysis, and replication package verification.
- `gapforge v7-release-gate --write-report --json --claim-real` passed with fixture gate true, real benchmark gate true, and no blockers.
- No fake benchmark results or SOTA claims are accepted. The real/local public benchmark canary validates the benchmark-and-replication path; it is not a broad performance claim across large external benchmarks, GPU/cluster runs, or independent replication by another researcher.

## 0.6.0

GapForge v0.6 is the experiment execution and empirical validation release. It keeps the v4 Codex workflow and v5 real-literature quality gates intact while adding durable experiment workspaces, artifact-backed result parsing, statistical analysis, reproducibility checks, empirical reviewer simulation, and honest paper-package exports.

### Experiment Workspaces and Registries

- Added first-class experiment workspaces with workspace state, run manifests, execution records, result artifacts, logs, reports, code, data, and config directories.
- Added dataset registry, dataset cards, loaders, and validation so fixture, synthetic, benchmark, generated, and real datasets are labeled with license, leakage, privacy, bias, and intended-use warnings.
- Added baseline registry, baseline cards, and related-work-driven baseline selection so required baselines become explicit experiment blockers instead of prose-only assumptions.
- Added metric registry and statistical test planning with built-in false positive rate, true positive rate, precision, recall, AUROC, AUPRC, calibration error, abstention, cost-weighted error, and runtime templates.
- Added low-FPR statistical planning warnings for rare false-positive claims, including sample-size and exact/binomial confidence-interval guidance.

### Code, Execution, and Results

- Added experiment code scaffold v2 with runnable workspace code, smoke configs, tests, and scripts while keeping generated outputs separate from result artifacts.
- Added constrained Codex/GPT-5.4 experiment code tasks for dataset loaders, baselines, metrics, runners, ablations, tests, smoke debugging, and result analysis.
- Added the experiment runner to execute manifests, capture redacted stdout/stderr logs, record return codes, detect expected outputs, hash result artifacts, and preserve failed runs.
- Added result parsing for metrics JSON artifacts, metric results, result summaries, and empirical claims.
- Added empirical claim ledger integration so no empirical claim is supported unless a run record and result artifact exist.
- Added statistical analysis helpers for binomial confidence intervals, paired summaries, bootstrap placeholders, multiple-testing warnings, low-FPR sample warnings, and exact count summaries.

### Reproducibility, Review, and Export

- Added reproducibility checks for dataset cards, baseline cards, metric definitions, random seeds, environments, manifests, commands, logs, hashes, confidence intervals, code scaffold version, and fake/fixture data labels.
- Added empirical reviewer simulation for empirical rigor, statistics, reproducibility, novelty with result context, and area-chair-style review.
- Upgraded paper package export to v2 so planned experiments, smoke runs, pilot/main results, failed results, negative results, and hypothetical expected results are labeled separately.
- Added v6 release gate requirements for executed fixture experiments, failed experiment paths, parsed result artifacts, artifact-backed empirical claims, reproducibility checks, empirical review, and paper package v2 export.
- Added v6 eval fixtures and metrics for experiment execution integrity, result-artifact grounding, empirical-claim validity, statistical caution, reproducibility, empirical review, fake-result rejection, paper-package honesty, and v6 release-gate correctness.
- Added experiment dashboard pages for workspaces, runs, datasets, baselines, metrics, results, reproducibility, empirical reviews, and paper-package status.
- Added v6 Python API helpers for experiment workspaces, registries, scaffolding, execution, result parsing, analysis, reproducibility, empirical review, paper-package v2 export, and release-gate checks.
- Added v6 documentation and Codex-readable skills for experiment workspaces, dataset cards, baseline selection, metric planning, experiment-code implementation, result analysis, reproducibility checks, empirical review, and paper-package v2.

### Validation

- Fixture experiment execution passed locally on May 6, 2026 with a successful smoke execution, a recorded failed execution path, a parsed metrics artifact, an artifact-backed empirical claim, reproducibility checks, empirical review, and paper package v2 export.
- A real Codex/GPT-5.4 experiment-code task ran locally through the configured direct Codex wrapper, produced a valid implementation patch, imported under the workspace code boundary, and passed workspace smoke validation. This validates the Codex experiment-code workflow, not a real empirical study.
- No real-world main experiment was run for this release; real empirical results remain not tested.
- `make ci`, `make eval`, v2/v3/v4/v5/v6 eval reports, v2/v3/v4/v6 smoke targets, and `gapforge v6-release-gate --write-report --json` pass for the release candidate.

## 0.5.0

GapForge v0.5 is the real literature campaign quality release. It keeps the deterministic/offline and v4 Codex workflow paths intact while adding live-source diagnostics, planned search rounds, closest-prior-work recall, and human research-quality acceptance gates.

### Live Literature Campaign Quality

- Added live source diagnostics and `live-source-diagnostic` reports that distinguish healthy, degraded, disabled, fallback-heavy, and unavailable source behavior.
- Added real literature campaign profiles for low-FPR collusion, LLM monitor evasion, multi-agent covert channels, cross-domain specificity, and undercovered-refusal validation.
- Added the real campaign dry-run planner so users can inspect source checks, search rounds, expected artifacts, budget, blockers, and acceptance criteria before running live campaigns.
- Added the real-literature campaign controller path so campaigns gather source health, execute planned search rounds, canonicalize papers, build retrieval, mine gap evidence, run prior-work recall, and stop with an explicit conservative reason.

### Search, Canonicalization, and Novelty Safety

- Added the search strategy planner with initial, survey, benchmark/dataset, novelty, counterevidence, and adjacent-field rounds.
- Added paper canonicalization v2 for DOI, arXiv, OpenReview, normalized-title, and high-confidence title/author/year merge decisions with auditable reports.
- Added the prior-work recall gate to block strong novelty until exact, method/metric, benchmark/dataset, survey, citation-neighborhood, and adjacent-field searches are complete as required by the source profile.
- Tightened novelty/prior-work candidate selection so deterministic fallback records remain visible in coverage but do not dominate closest-prior-work decisions when live paper records are available.

### Codex, Review, Reporting, and APIs

- Added the Codex research synthesis task for evidence-gated direction synthesis after live search, retrieval, and prior-work recall gates pass.
- Added human real-literature quality review with separate workflow acceptance and research-quality acceptance.
- Added live campaign dashboard/report sections for source health, search strategy, search rounds, canonicalized papers, full-text/abstract coverage, prior-work recall, Codex synthesis artifacts, and quality review.
- Added the v5 release gate to require deterministic evidence, a passing v4 workflow gate, live-literature campaign records, research-quality accepted campaigns, a conservative refusal campaign, and an experiment-ready campaign.
- Added v5 eval fixtures and metrics for live-source coverage, search strategy completeness, prior-work recall gates, canonicalization quality, refusal quality, research-direction quality proxy, quality-review gate correctness, and v5 release-gate correctness.
- Added v5 API functions for source health, search planning, real-literature campaigns, canonicalization, prior-work recall, quality review, and release-gate checks.
- Added v5 documentation and Codex-readable skills for live literature scouting, search planning, prior-work recall, real-literature review, and research synthesis.

### Validation

- Recorded a local May 6, 2026 v5 release-gate pass with two quality-accepted live-literature campaigns: one experiment-ready campaign and one conservative refusal campaign.
- `make ci`, `make eval`, v2/v3/v4/v5 eval reports, v2/v3/v4 smokes, and `gapforge v5-release-gate --write-report --json` pass for the release candidate.

## 0.4.1

GapForge v0.4.1 is a focused Codex workflow usability patch. It does not add new research claims or count fake-agent canaries as real acceptance.

### Codex Workflow Usability

- Added `gapforge setup-codex` as a setup wizard that reports direct, task-pack, manual-handoff, and fake mode availability.
- Added `gapforge codex-doctor` to diagnose task-pack paths, outputs, validation/import status, attestation, review, and actual-run blockers.
- Added copy-paste handoff v2 files: `README_FIRST.md`, `CODEX_PROMPT.md`, `OUTPUT_CONTRACT.md`, `VALIDATE_AND_IMPORT.sh`, minimal output skeletons, and examples.
- Added direct command preview and dry-run support for Codex command templates.
- Added a local direct Codex runner wrapper for `codex exec` when real runs are enabled and the Codex CLI is available.
- Improved command-template validation, placeholder warnings, redaction, output directory handling, and direct-run failure messages.

### Validation, Import, and Attestation

- Added flexible output contract levels so partial but useful Codex output can validate without weakening evidence/citation rules.
- Added `validate-import-all`, task output discovery, latest task lookup, and easier validate/import command flows.
- Added valid and invalid Codex output examples for deep reading, gap mining, novelty, reviewer, manuscript, fake-citation rejection, and unsupported-claim rejection.
- Improved actual-run attestation status so users can see validation/import, attestation, human review, and remaining blockers.
- Improved repair UX with latest-invalid lookup, repair handoff prompts, exact validation errors, known valid IDs, and repair validate/import commands.
- Improved release-gate messaging with blocker categories, next commands, accepted-real-campaign counters, and fake-vs-real explanations.

### Canary Workflows

- Added `single_task_codex_handoff` and `single_task_fake_handoff_regression` to debug the smallest Codex task-pack workflow.
- Added `manual_pdf_codex_reading_handoff` and a fake companion to validate local-PDF/full-text Codex reading workflow mechanics.
- Validated three real Codex/GPT-5.4 workflow canaries locally on May 6, 2026: one conservative refusal workflow, one manual-PDF/full-text reading workflow, and one fixture-backed experiment-ready workflow.
- `gapforge v4-release-gate --write-report --json` passed locally with 3 accepted real campaigns and no blockers.

### Documentation

- Added `docs/CODEX_QUICKSTART.md`.
- Added v0.4.1 fix plan, acceptance, troubleshooting, release notes, and Codex usage status docs.
- Rewrote Codex usage documentation around setup, task-pack handoff, direct command dry run, validation/import, attestation, review, repair, and release-gate acceptance.

### Validation

- `make format-check` passes.
- `make lint` passes.
- `make typecheck` passes.
- `make test` passes with 465 tests.
- `make eval` passes offline.
- `gapforge eval --v4 --write-report` passes offline.
- `gapforge v4-release-gate --write-report --json` passes with 3 accepted real Codex/GPT-5.4 workflow canaries.

## 0.4.0

GapForge v0.4 prepares the system for actual Codex/GPT-5.4 agentic research campaigns. It does not claim exhaustive autonomous literature review, and it does not count fake-agent success as real-run acceptance.

### Agentic Campaigns

- Added first-class campaign state, campaign steps, campaign decisions, campaign milestones, campaign budgets, stop conditions, and campaign reports.
- Added campaign controller logic for deterministic, fake-agent, Codex task-pack, Codex direct, and manual-handoff modes.
- Added explicit stop reasons so campaigns can end as ready, not ready, blocked, pending handoff, invalid-output, or budget-exhausted.
- Added campaign canary profiles for low-FPR collusion, monitor evasion, cross-domain specificity, undercovered refusal, manual PDF, and fake-agent regression.

### Codex/GPT-5.4 Actual-Run Path

- Added real-run diagnostics for environment status, agent runtime status, task-pack status, import validator status, canary status, blockers, and recommended next commands.
- Upgraded the AgentClient runtime contract with direct, task-pack, manual-handoff, and fake capabilities plus actual-run attestation rules.
- Added runtime capability reporting for direct, task-pack, manual-handoff, and fake execution methods.
- Added Codex runner and handoff support with configured command execution, task-pack handoff files, validation/import commands, and redacted command logs.
- Added campaign-level Codex task packs for planning, literature scouting, batch reading, gap synthesis, novelty review, experiment architecture, reviewer panel, and stop decisions.
- Added actual-run attestation records so task-pack/manual-handoff outputs can count only when real Codex/GPT-5.4 execution is attested, validated, imported, and human-reviewed.
- Added diagnostics for real-run blockers and setup guidance for direct versus task-pack/handoff execution.

### Validation, Import, and Recovery

- Added robust campaign output validation, partial import, rollback snapshots, import records, and rollback commands.
- Added agent output repair task generation so invalid Codex JSON can be corrected without weakening validation.
- Added retrieval-backed task context selection with explicit budgets and context-limited flags.
- Added agentic search requests and novelty re-search loops so Codex can propose searches while GapForge validates and executes them.

### Research Workflows

- Added campaign-level reviewer and rebuttal loops.
- Added experiment code task generation and experiment repository scaffolding for experiment-ready directions.
- Added campaign-level human review and acceptance summaries.
- Added dashboard pages for campaigns, actual runs, canaries, agent tasks, imports, human reviews, rejected outputs, fake-vs-real labels, and release-gate status.
- Added campaign reports with explicit stop reasons and acceptance blockers.

### Evaluation, API, and Release Gates

- Added v4 campaign eval fixtures and metrics for campaign decisions, stop reasons, output validation strictness, actual-run gates, novelty loops, direction maturity, report honesty, review queues, code tasks, and rollback safety.
- Exposed v0.4 campaign and actual-run workflows through the Python API.
- Added a machine-checkable v0.4 release gate requiring deterministic evidence, fake-agent campaign canary success, at least three accepted real Codex/GPT-5.4 campaigns, a strict-refusal campaign, an experiment-ready campaign, and a manual-PDF/full-text campaign.
- Added `make v4-smoke` for CI-safe fake-agent campaign smoke validation. The target writes a release-gate report but expects the actual-run gate to fail unless real campaigns have been accepted.
- Updated v0.4 docs and Codex-readable skills for campaign control, Codex campaign tasks, output validation, novelty loops, experiment code tasks, reviewer panels, and real-run acceptance.

### Validation

- Deterministic checks passed locally on May 5, 2026: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `gapforge eval --v4 --write-report`, `make coverage`, `make v2-smoke`, `make v3-smoke`, and `make v4-smoke`.
- Fake campaign canary `fake_agent_campaign_regression` passed.
- Actual Codex/GPT-5.4 campaign acceptance was **not completed** in this environment. `GAPFORGE_ENABLE_REAL_RUNS`, `GAPFORGE_AGENT_NAME`, and `GAPFORGE_CODEX_MODEL` were not configured, so real campaign canaries were refused or recorded as non-actual.
- `gapforge v4-release-gate --write-report` correctly fails because there are zero accepted real Codex/GPT-5.4 campaigns.

## 0.3.0

GapForge v0.3 extends the v0.2 full-text evidence system with project memory, hybrid retrieval, optional Codex/GPT-5.4 task-pack workflows, research direction maturation, and manuscript package exports. It is still not an exhaustive autonomous literature reviewer.

### Project Memory and Retrieval

- Added project-level memory for topics, corpus papers, rejected ideas, human decisions, memory records, and research directions.
- Added a Python API layer for notebooks, scripts, and future UI surfaces without shelling out to the CLI.
- Added project claim graphs with deterministic duplicate/contradiction detection and human resolution records.
- Added hybrid lexical/local-semantic retrieval over papers, sections, evidence spans, notes, claims, gaps, dossiers, and project memory.
- Added source policy profiles and coverage stopping assessments.
- Added active-loop decision records and budget-aware stop conditions.

### Codex/GPT-5.4 Agent Support

- Added an optional provider LLM adapter with JSON guards, budget tracking, transcript redaction, and graceful provider-unavailable failures.
- Added optional LLM-backed deep-reading, gap-mining, novelty-dossier, and reviewer workflows behind deterministic/fake/prompt-pack/provider modes.
- Added `AgentClient` separately from `LLMClient`.
- Added Codex-compatible task packs, strict schema validation, validated output import, fake-agent CI mode, and canary run profiles.
- Added `gapforge run --v3 --mode deterministic|prompt-pack|fake-agent|llm-assisted`.
- Added human review harness and release-gate status for actual Codex/GPT-5.4 canary acceptance.

### Research Direction Workflow

- Added related-work matrices, must-read lists, baseline candidates, experiment protocols, reproducibility checklists, review panels, rebuttal plans, and manuscript/paper package exports.
- Added review queue and static dashboard for project/run inspection.
- Added artifact safety auditing, redaction, safe-bundle export, and generated-artifact hygiene.

### Full-Text and Evaluation

- Added v0.3 PDF structure extraction hooks for references, tables, equations, captions, and OCR-status records.
- Added v0.3 curated fixture layout and metrics for retrieval relevance, prior-work recall proxy, direction maturity, protocol completeness, manuscript honesty, contradiction detection, source-policy compliance, and LLM grounding.

### Validation

- Deterministic checks passed locally: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `make coverage`, `make v2-smoke`, and `make v3-smoke`.
- Fake-agent canary `fake_agent_regression` passed.
- Actual Codex/GPT-5.4 real-run acceptance was **not completed** because the real-run environment was unavailable. The release must not claim actual-run validation passed.

## 0.2.0

GapForge v0.2 upgrades the project from an abstract/metadata-heavy smoke-test system into a full-text-aware, evidence-located research ideation system with conservative novelty checking. It is still not an exhaustive autonomous literature reviewer.

### Full-Text and Evidence

- Added full-text artifact models for PDFs, HTML/text/metadata artifacts, parsed paper sections, evidence spans, search query records, source coverage, and citation graphs.
- Added PDF artifact storage under run directories with safe filenames, SHA256 hashing, duplicate detection, and durable `PaperArtifact` records.
- Added PDF download support with cache-aware HTTP, max-size guards, PDF validation, network-disable handling, and non-fatal failure recording.
- Added PDF parsing and sectionization with page-preserving extraction, common section classification, fallback sections, and section text artifacts.
- Upgraded deep reading to use parsed full-text sections when available, produce evidence spans, distinguish abstract-only notes, and avoid extracting results without evidence.
- Added evidence-span-aware validation and report language so abstract/metadata-only claims are not presented as full-text evidence.

### Search, Coverage, and Prior Work

- Added first-class search query ledger records for initial, analogy, novelty, citation-expansion, and manual searches.
- Added source coverage and full-text coverage reports that show searched sources, failures, fallback/offline papers, PDF/full-text coverage, and warnings.
- Added citation graph construction from explicit metadata and conservative related-work expansion.
- Upgraded novelty checking with closest-prior-work dossiers, query planning, deterministic structured comparison, missing-search tracking, and conservative verdict rules.
- Added source ranking v2 with paper roles, source/role diversity, full-text availability, novelty importance, and adjacent-field transfer signals.

### Research Skills

- Upgraded gap mining with evidence matrices, counterevidence, confidence rules, and full-text/coverage-sensitive behavior.
- Added gap evidence matrix artifacts in JSON and Markdown.
- Upgraded cross-domain analogy into status-tagged transfer candidates with query-only, evidence-found, promoted, and rejected states.
- Added cross-domain transfer candidate artifacts and report integration.
- Upgraded experiment design and reviewer simulation to respect stronger novelty, baseline, falsification, and reviewer blocking-issue rules.

### Human Review and LLM Extension Points

- Added human-in-the-loop review/edit commands for approving/rejecting gaps, annotating and marking claims, adding evidence, locking objects, and viewing audit logs.
- Added durable human review records and audit artifacts.
- Added optional LLM adapter interfaces, deterministic fake client, and prompt-pack generation without requiring live model calls.

### Evaluation and Reporting

- Added v0.2 synthetic fixtures with paper sections, evidence spans, novelty dossiers, gap evidence matrices, source coverage, duplicate ideas, and expected reviewer objections.
- Added v0.2 metrics for full-text coverage, evidence-span grounding, gap evidence matrices, novelty dossier completeness, source coverage transparency, human review respect, and report uncertainty.
- Upgraded the final report into a v0.2 evidence-located dossier with source coverage, full-text coverage, evidence locators, gap matrices, cross-domain transfer candidates, novelty dossiers, human review summary, rejected ideas, uncertainty, and strict report mode.
- Strict report mode refuses to recommend a top direction when coverage, evidence, novelty, or reviewer gates are weak.

### CLI, Docs, and Release Hygiene

- Added v0.2 orchestration flags for `gapforge run --v2`, PDF download/parse controls, deep novelty, strict reports, and bounded related-work expansion.
- Added manual ingestion commands for papers, arXiv IDs, DOIs, local PDFs, and URLs.
- Added coverage, citation graph, related-work expansion, prompt-pack, and human review CLI commands.
- Added v0.2 roadmap, acceptance criteria, known limitations, release process, contributing guide, testing guide, and v0.2 workflow documentation.
- Added GitHub Actions CI and pre-commit configuration.
- Added Makefile targets for `format-check`, `typecheck`, `ci`, `coverage`, `v2-smoke`, `clean-runs`, and `clean-cache`.

### Validation

- `make ci` passes.
- `make eval` passes offline.
- `make v2-smoke` passes offline.
- `gapforge eval --v2 --write-report` passes offline.

### Known Limitations

- v0.2 remains deterministic and heuristic.
- Offline/fallback runs are smoke tests, not literature conclusions.
- Full-text quality depends on available PDFs and extractable text.
- Novelty dossiers are conservative prior-work aids, not proof of novelty.

## 0.1.0

- Created the initial GapForge Python package and CLI.
- Added persistent research run state under `runs/`.
- Added source connector interfaces and keyless first-pass connectors with caching and graceful fallback.
- Added modular skills for literature mapping, paper triage, deep reading, gap mining, cross-domain analogy, novelty gating, experiment design, and reviewer simulation.
- Added claim ledger, provenance tracking, validation rules, evaluator fixtures, and final report generation.
- Added Codex-readable skill folders under `skills/`.
- Added README, examples, docs, Makefile, Ruff, mypy, and pytest tooling.

Note: v0.1 outputs are deterministic heuristic artifacts. Offline and fixture outputs are smoke-test signals, not real literature conclusions.
