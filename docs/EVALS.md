# Evaluations

GapForge evaluations are offline and fixture-driven. They test whether the system identifies specific, evidence-backed, novelty-aware gaps instead of generic research ideas.

## Fixtures

Fixtures live under `tests/fixtures/research_topics/`:

- `low_fpr_collusion`
- `lexical_substitution_monitoring`
- `quantum_portfolio_optimization`
- `wildfire_prediction_ml`

Each fixture contains:

- `topic.md`
- `papers.json`
- `paper_notes.json`
- `known_good_gaps.json`
- `known_bad_gaps.json`
- `duplicate_ideas.json`
- `expected_reviewer_objections.json`

The fixtures intentionally include duplicate ideas, unsupported claims, and missing-baseline controls so the evaluator can check failure detection.

## Metrics

`src/gapforge/evals/metrics.py` implements:

- `gap_specificity_score`
- `evidence_linkage_score`
- `novelty_gate_accuracy`
- `duplicate_detection_rate`
- `unsupported_claim_rate`
- `experiment_completeness_score`
- `reviewer_objection_quality_score`

## Runner

Run all fixtures:

```bash
gapforge eval
```

Run one fixture:

```bash
gapforge eval --fixture low_fpr_collusion
```

Write the Markdown report:

```bash
gapforge eval --write-report
```

The runner writes `eval_report.md` with scores by fixture, unsupported claims, accepted gaps, rejected gaps, novelty gate failures, missing baselines, and recommended improvements.

The eval report is not a scientific benchmark result. It is a regression harness for GapForge behavior: duplicate ideas should be rejected, unsupported claims should stay visible, and experiments should not pass reviewer simulation without baselines and falsification conditions.

## Contract

- Evals must not call live APIs.
- Evals must not require API keys.
- Fixture duplicate ideas should be rejected by the novelty gate.
- Fixture unsupported claims should be visible in the report.
- Missing baselines should be caught by reviewer simulation.
