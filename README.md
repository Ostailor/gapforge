# GapForge

GapForge is a Codex-powered Research Ideation OS for turning a broad research topic into evidence-linked, experiment-ready research directions.

It is currently a deterministic v0.1 Python project. The default skills use source metadata, abstracts, local fixtures, and conservative heuristics. They are designed to be auditable and replaceable by stronger source readers later.

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

Run the offline-safe toy path:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --max-papers 12
gapforge report
```

The run writes artifacts under `runs/<timestamp-topic>/`, including:

- `state.json`
- `papers.json`
- `field_map.md`
- `paper_triage.md`
- `paper_notes.md`
- `gaps.md`
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
gapforge novelty-check --run-id <run-id>
gapforge design-experiments --run-id <run-id>
gapforge review --run-id <run-id>
gapforge report --run-id <run-id>
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
make format
make lint
make test
make eval
```

Tooling is configured in `pyproject.toml` for `pytest`, `ruff`, and `mypy`.

## Limitations

- v0.1 uses deterministic heuristics, not a full paper-understanding model.
- Most notes are abstract/metadata-only unless full text is supplied by future readers.
- Source connectors do not require API keys, so metadata coverage varies by source and network state.
- Novelty checks are conservative but not exhaustive. A `pursue` verdict means "worth investigating," not "definitely novel."
- Fixture and offline fallback outputs are smoke-test artifacts, not real research conclusions.

## Roadmap

- Add full-text PDF ingestion and section-level evidence locators.
- Add stronger semantic deduplication and citation-neighborhood search.
- Add configurable source policies and per-field venue authority lists.
- Add richer evaluator fixtures with human-reviewed gap labels.
- Add CI workflow and pre-commit hooks once the repo is under version control.
- Add LLM-backed skill implementations behind the same typed interfaces.
- Add export formats for paper briefs, experiment cards, and reviewer rebuttal plans.
