# GapForge

GapForge v0.2 is a Codex-powered Research Ideation OS for turning a broad research topic into evidence-linked, experiment-ready research directions.

GapForge v0.2 is still not an exhaustive autonomous literature reviewer. It is now a full-text-aware, evidence-located research ideation system with conservative novelty checking. The default skills remain deterministic and heuristic, using source metadata, abstracts, parsed local/PDF text when available, local fixtures, claim ledger evidence, and explicit uncertainty.

## Why Not Just Summarization?

A summarizer compresses papers. GapForge tracks a research state.

GapForge keeps:

- a persistent run directory with machine-readable artifacts
- normalized papers and abstract/full-text-aware paper notes
- a claim ledger with supporting evidence, counterevidence, confidence, and verification status
- provenance for skill-created objects
- field maps, gaps, novelty assessments, experiments, reviewer objections, and rejected ideas
- a final report that separates evidence-backed claims from hypotheses

The system is intentionally skeptical. It should attack an idea before recommending it, and it should not claim novelty until closest prior work has been checked.

## Installation

Requires Python 3.11+.

```bash
git clone <repo-url> GapForge
cd GapForge
python -m venv .venv
source .venv/bin/activate
make install
```

Equivalent direct install:

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

Run the v0.2 offline-safe smoke path:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --v2 --max-papers 8
gapforge report --strict
gapforge coverage
```

Strict mode should be conservative in this smoke path: because the run uses fallback metadata and has no parsed full text, the final report should say that no direction is ready rather than claiming novelty.

The run writes artifacts under `runs/<timestamp-topic>/`, including:

- `state.json`
- `papers.json`
- `source_coverage.md`
- `full_text_coverage.md`
- `field_map.md`
- `paper_triage.md`
- `paper_notes.md`
- `gaps.md`
- `gap_evidence_matrix.md`
- `novelty_dossiers.md`
- `novelty_gate.md`
- `experiments.md`
- `reviewer_simulation.md`
- `run_report.md`
- `final_report.md`

Open the final report:

```bash
latest_run=$(ls -td runs/* | head -1)
sed -n '1,160p' "$latest_run/final_report.md"
```

## v0.2 Workflows

### Offline Smoke Quickstart

Use this to verify the orchestration loop without live APIs:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --v2 --max-papers 8
gapforge report --strict
gapforge coverage
```

Expected behavior:

- PDF download, analogy search, and related-work expansion are skipped with coverage warnings.
- `source_coverage.md` labels fallback/offline records.
- `full_text_coverage.md` reports zero parsed full text.
- `final_report.md` does not recommend a top direction as novel.

### Manual Local PDF Ingestion

Use this when you already have a paper PDF:

```bash
gapforge init-topic "my research topic"
run_id=$(ls -td runs/* | head -1 | xargs basename)
gapforge add-pdf --run-id "$run_id" /path/to/paper.pdf --title "Paper Title" --authors "A. Author;B. Author" --year 2024 --parse
gapforge read --run-id "$run_id" --fulltext-only
gapforge mine-gaps --run-id "$run_id"
gapforge novelty-check --run-id "$run_id" --deep
gapforge report --run-id "$run_id" --strict
```

Local PDFs are copied into the run artifact store, hashed, parsed into sections when possible, and used by deep reading to create locator-backed evidence spans.

### Full-Text Parsing Workflow

For searched papers with reliable `pdf_url` or arXiv IDs:

```bash
gapforge run "topic" --v2 --download-pdfs --parse-fulltext --max-papers 20
```

Or run the stages manually:

```bash
gapforge search "topic" --max-results 20 --sources arxiv,crossref
run_id=$(ls -td runs/* | head -1 | xargs basename)
gapforge triage --run-id "$run_id"
gapforge download-pdfs --run-id "$run_id" --max-papers 10 --skip-existing
gapforge parse-fulltext --run-id "$run_id"
gapforge read --run-id "$run_id" --tier 1
```

If downloads or parsing fail, GapForge records the failure and continues. A missing PDF must not become a fabricated full-text claim.

### Novelty Dossier Workflow

Generate closest-prior-work dossiers before treating an idea as research-ready:

```bash
gapforge mine-gaps --run-id "$run_id"
gapforge build-citation-graph --run-id "$run_id"
gapforge expand-related-work --run-id "$run_id" --max-new-papers 30
gapforge novelty-check --run-id "$run_id" --deep
gapforge novelty-dossier --run-id "$run_id" --gap-id <gap-id>
```

The dossier records query plans, candidates considered, closest prior work, missing searches, reviewer objections, and the decisive difference needed. A strong novelty claim should not appear unless closest prior work has been checked.

### Strict Report Mode

```bash
gapforge report --run-id "$run_id" --strict
```

Strict mode refuses to recommend a top direction when source coverage is poor, no full-text evidence spans exist, novelty dossiers are missing or unresolved, or reviewer blocking issues remain.

## Example Run

```bash
make example
```

`make example` disables live network access, runs the default low-FPR collusion topic, and writes a final report. In offline mode, source connectors use deterministic fallback metadata where needed. Treat the output as a smoke test of the research OS, not as a real literature review.

More topic seeds are in `examples/`:

- `examples/low_fpr_collusion.md`
- `examples/lexical_substitution_monitoring.md`
- `examples/quantum_portfolio_optimization.md`

## Common CLI Commands

```bash
gapforge --help
gapforge init-topic "low false positive collusion detection"
gapforge search "low false positive collusion detection" --max-results 50 --sources arxiv,crossref
gapforge map --run-id <run-id>
gapforge triage --run-id <run-id>
gapforge read --run-id <run-id> --tier 1
gapforge mine-gaps --run-id <run-id>
gapforge analogies --run-id <run-id>
gapforge coverage --run-id <run-id>
gapforge download-pdfs --run-id <run-id> --max-papers 10
gapforge parse-fulltext --run-id <run-id>
gapforge build-citation-graph --run-id <run-id>
gapforge expand-related-work --run-id <run-id> --max-new-papers 30
gapforge novelty-check --run-id <run-id> --deep
gapforge design-experiments --run-id <run-id>
gapforge review --run-id <run-id>
gapforge report --run-id <run-id> --strict
gapforge validate-state
gapforge cache-info
gapforge eval --write-report
```

Use `gapforge report` without `--run-id` to report on the latest run.

## Architecture

GapForge has four main layers:

1. **Sources**: arXiv, CrossRef, DBLP, OpenReview, Semantic Scholar, and generic web placeholders normalize metadata into the shared `Paper` model. Networked connectors cache responses under `.gapforge_cache/` and degrade gracefully without API keys.
2. **Skills**: modular research abilities transform `ResearchRunState`. Skills can run individually or through the orchestrator.
3. **State and provenance**: every run persists JSON and Markdown artifacts under `runs/`. Claims, evidence, gaps, experiments, and reviewer objections keep IDs and provenance links.
4. **Evaluator harness**: offline fixtures test whether GapForge produces specific, evidence-linked, novelty-aware gaps rather than generic ideas.

See:

- `docs/ARCHITECTURE.md`
- `docs/RESEARCH_STATE.md`
- `docs/CLAIM_LEDGER.md`
- `docs/SOURCES.md`
- `docs/SKILLS.md`
- `docs/EVALS.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/V0_2_ROADMAP.md`

## Skill List

- Literature Cartographer: clusters papers and maps methods, datasets, metrics, saturation, and underexplored areas.
- Paper Triage: ranks papers into reading tiers.
- Deep Reading: creates structured notes while marking abstract-only limitations.
- Gap Mining: identifies evidence-linked research gaps from field maps and notes.
- Cross-Domain Analogy: proposes skeptical adjacent-field search directions.
- Novelty Gate: checks candidate ideas against closest prior work and rejects duplicates.
- Experiment Designer: converts non-rejected gaps into falsifiable experiment plans.
- Reviewer Simulation: attacks experiments from technical, novelty, empirical-rigor, and area-chair perspectives.

Each skill also has a Codex-readable package under `skills/*/SKILL.md`.

## Evaluation Philosophy

GapForge evals are offline and fixture-driven. They include known good gaps, known bad gaps, duplicate ideas, unsupported claims, and expected reviewer objections.

The current metrics include:

- gap specificity
- evidence linkage
- novelty gate accuracy
- duplicate detection
- unsupported claim rate
- experiment completeness
- reviewer objection quality

Run:

```bash
make eval
```

This writes `eval_report.md`.

## Configuration and Caching

Environment variables:

- `GAPFORGE_ROOT`: override the workspace root for CLI runs.
- `GAPFORGE_CACHE_DIR`: override the source response cache directory.
- `GAPFORGE_DISABLE_NETWORK=1`: force offline-safe behavior.

Cache diagnostics:

```bash
gapforge cache-info
```

## Development

```bash
make install
make format-check
make format
make lint
make typecheck
make test
make eval
make coverage
make v2-smoke
```

Run the full local CI gate with:

```bash
make ci
```

Tooling is configured in `pyproject.toml` for `pytest`, `pytest-cov`, `ruff`, and `mypy`. See `docs/CONTRIBUTING.md` and `docs/TESTING.md` for contributor and verification details.

## Limitations

- v0.2 still uses deterministic heuristics, not a full paper-understanding model.
- Most notes are abstract/metadata-only unless PDFs are manually ingested or successfully downloaded and parsed.
- Source connectors do not require API keys, so metadata coverage varies by source and network state.
- Novelty checks are conservative but not exhaustive. A `pursue` verdict means "worth investigating," not "definitely novel."
- Fixture and offline fallback outputs are smoke-test artifacts, not real research conclusions.

See `docs/KNOWN_LIMITATIONS.md` for the current limitation contract.

## Roadmap

v0.2 is planned as the full-text and stronger-novelty release. The goal is to reduce v0.1's abstract/metadata-heavy risk, not to claim exhaustive literature review capability.

v0.2 targets:

- full-text PDF and manual paper ingestion
- section-level paper parsing
- evidence spans with page and section locators
- full-text-aware deep reading
- citation graph and related-work expansion
- closest-prior-work dossiers for the novelty gate
- source coverage reports that distinguish live source coverage from offline fallback mode
- human-in-the-loop review/edit commands
- stronger eval fixtures, including full-text fixture papers or excerpts
- report sections that make full-text coverage, fallback mode, and unresolved novelty searches visible

Future v0.3 work may include LLM-backed full-text synthesis, OCR, multi-run project memory, collaborative review workflows, and export formats for manuscript or rebuttal planning.

See:

- `docs/V0_2_ROADMAP.md`
- `docs/V0_2_ACCEPTANCE_CRITERIA.md`
- `docs/RELEASE_PROCESS.md`
