# GapForge v0.3 Roadmap

v0.3 moves GapForge beyond the v0.2 full-text/evidence foundation toward a project-level, retrieval-aware research ideation system. It does not make GapForge an exhaustive autonomous literature reviewer.

## Why v0.3 Exists Beyond v0.2

v0.2 made runs evidence-located with PDFs, sections, EvidenceSpan locators, source coverage, citation graphs, novelty dossiers, gap evidence matrices, human review, and strict reports.

v0.3 addresses the next risks:

- related runs need shared memory
- closest-prior-work search needs retrieval and project context
- gaps need counterevidence search, not just generation
- source coverage needs field-specific policy
- ideas need maturity gates before manuscript export
- optional LLM skills need schema validation and citation discipline
- researchers need review queues and dashboards

## Must-Have

### Project Memory Across Runs

- Project store under `projects/<project-id>/`.
- Attach runs to projects.
- Deduplicate corpus papers.
- Sync claims, gaps, rejected ideas, human decisions, and directions.
- Preserve provenance and avoid treating prior memory as newly verified evidence.

### Hybrid Retrieval

- Index papers, sections, evidence spans, notes, claims, gaps, novelty dossiers, and project memory.
- Combine lexical scoring with deterministic local embeddings.
- Persist index manifests and retrieval coverage.
- Keep live embedding providers optional and out of tests.

### Source Policy and Stopping Criteria

- Provide field profiles for generic, ML, AI safety, multi-agent systems, medicine, economics, cybersecurity, physics, and biology.
- Assess whether coverage is enough for mapping, gap mining, novelty, and experiment design.
- Recommend next searches.
- Prevent strict reports and novelty gates from overclaiming when coverage is weak.

### Active Research Loop

- Support `gapforge run "topic" --v3 --active`.
- Decide whether to search more, parse more, read more, expand citations, check novelty, design experiments, request human review, or stop.
- Record active-loop decisions with reasons, evidence, expected value, and cost estimates.
- Respect budgets.

### Optional LLM-Backed Skills

- Keep deterministic default.
- Support prompt-pack, fake, and provider modes.
- Validate JSON before state updates.
- Require paper IDs and EvidenceSpan locators for source-backed outputs.
- Never request or store hidden chain-of-thought.
- Treat Codex/GPT-5.4 as the intended real-run research agent for v0.3 canaries, while keeping CI independent of Codex/GPT-5.4.

### Direction Maturation

- Track directions through `seed`, `candidate`, `validated_gap`, `experiment_ready`, `manuscript_ready`, and `rejected`.
- Gate maturity on evidence matrices, novelty dossiers, source coverage, protocols, reviewer status, claim contradictions, and human review.

### Related-Work Matrix and Protocols

- Classify prior work by relationship to a direction.
- Surface must-cite and baseline papers.
- Generate executable experiment protocols with baselines, metrics, statistics, reproducibility checks, and falsification conditions.

### Manuscript Package Export

- Export a paper starter kit only when maturity permits or explicit override is used.
- Include related work, protocol, expected results labeled hypothetical, limitations, reviewer objections, rebuttal plan, BibTeX, claim ledger, and evidence index.
- Do not invent results.

### Review Queue and Dashboard

- Create review queue items for unsupported claims, unknown novelty, contradictions, source-policy waivers, and near-ready directions.
- Generate static HTML dashboards without requiring a server.

### Curated v0.3 Evals

- Add curated real-world-style fixtures with synthetic or permissible short excerpts.
- Measure retrieval relevance, prior-work recall proxy, related-work matrix quality, direction maturity, protocol completeness, manuscript honesty, contradiction detection, source policy compliance, and LLM grounding.

### Real-Run Acceptance

- Define validation levels from deterministic CI through human-reviewed Codex/GPT-5.4 canary runs.
- Require at least one Codex/GPT-5.4 LLM-assisted literature run before claiming actual-run validation.
- Require at least one local-PDF full-text canary workflow.
- Keep actual-run validation manual/private and outside CI.
- Never fake a canary pass with fake LLM or prompt-pack mode.

## Should-Have

- Better table/reference extraction from difficult PDFs.
- More field-specific venue authority profiles.
- More human-review commands for claim graph and direction state.
- Safer collaborator bundles with redacted evidence snippets.
- Better dashboard filtering.
- Stronger source connector metadata for references/citations.

## Future v0.4

- OCR and layout reconstruction for scanned PDFs.
- External reference-manager integrations.
- Experiment execution adapters.
- Collaborative multi-user project review.
- Active-learning ranking from human feedback.
- Long-running paper monitoring.
- Browser-assisted access workflows.

## Explicit Non-Goals

- Do not claim exhaustive autonomous literature review.
- Do not require live LLM, embedding, or source API calls for tests.
- Do not remove deterministic/offline paths.
- Do not silently trust model-generated citations.
- Do not present fallback or fixture data as real literature conclusions.
- Do not treat semantic similarity as proof of novelty.
- Do not export fake results or imply publication readiness without human validation.
- Do not claim actual-run validation if Codex/GPT-5.4 was unavailable.

## Current v0.3 CLI Entry Points

```bash
gapforge run "topic" --v3
gapforge run "topic" --v3 --active --budget small
gapforge build-index --run-id <run-id>
gapforge init-project "project name"
gapforge sync-project-memory --project-id <project-id>
gapforge related-work-matrix --project-id <project-id> --direction-id <direction-id>
gapforge mature-direction --project-id <project-id> --direction-id <direction-id>
gapforge export-paper-package --project-id <project-id> --direction-id <direction-id>
gapforge dashboard --project-id <project-id>
```

## Real-Run Release Gate

v0.3 release readiness has two tracks:

- Automated validation: Levels 0-3 in `docs/V0_3_REAL_RUN_ACCEPTANCE.md`.
- Actual-run validation: Level 4 Codex/GPT-5.4 canary runs plus Level 5 human review.

CI must not require Codex/GPT-5.4. Release notes must say whether actual-run validation passed, failed, or was not run.
