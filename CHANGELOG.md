# Changelog

All notable project changes should be recorded here.

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
