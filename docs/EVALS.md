# Evaluations

GapForge evals are offline and fixture-driven. They test behavior: evidence linkage, duplicate rejection, novelty caution, source transparency, retrieval relevance, direction maturity, and export honesty. They do not prove real scientific quality.

## Fixture Families

### v0.1 Synthetic Research Topics

Located in `tests/fixtures/research_topics/`:

- `low_fpr_collusion`
- `lexical_substitution_monitoring`
- `quantum_portfolio_optimization`
- `wildfire_prediction_ml`

These check deterministic run behavior, generic gap quality, duplicate ideas, and reviewer objections.

### v0.2 Full-Text Fixtures

Located in `tests/fixtures/research_topics/*_v2/`:

- paper sections
- evidence spans
- expected novelty dossiers
- gap evidence matrices
- expected source coverage

These test section grounding, evidence spans, unsupported full-text claims, and dossier-aware novelty.

### v0.3 Curated Real-World-Style Fixtures

Located in `tests/fixtures/curated_v3/`:

- `low_fpr_collusion`
- `llm_monitor_evasion`
- `medical_screening_specificity`
- `cartel_detection_economics`
- `physics_phase_transition_analogy`

These are synthetic or metadata/short-excerpt fixtures designed to resemble real research workflows. They must not include copyrighted PDFs or present fixture conclusions as real literature findings.

## Metrics

Core metrics:

- `gap_specificity_score`
- `evidence_linkage_score`
- `novelty_gate_accuracy`
- `duplicate_detection_rate`
- `unsupported_claim_rate`
- `experiment_completeness_score`
- `reviewer_objection_quality_score`

v0.2 metrics:

- `full_text_coverage_score`
- `evidence_span_precision_proxy`
- `section_grounding_score`
- `gap_evidence_matrix_score`
- `novelty_dossier_completeness_score`
- `source_coverage_transparency_score`
- `human_review_respect_score`
- `report_uncertainty_score`

v0.3 metrics:

- `retrieval_relevance_at_k`
- `prior_work_recall_proxy`
- `related_work_matrix_quality`
- `direction_maturity_accuracy`
- `protocol_completeness`
- `manuscript_package_honesty`
- `contradiction_detection_score`
- `source_policy_compliance`
- `llm_output_grounding_score`

## Commands

```bash
gapforge eval
gapforge eval --v2
gapforge eval --v3
gapforge eval --fixture low_fpr_collusion --v3
gapforge eval --write-report
make eval
```

`make eval` runs offline and writes `eval_report.md`.

## What Evals Should Catch

- unsupported high-confidence claims
- duplicate ideas not rejected by novelty gate
- generic gaps without paper/evidence links
- missing baselines in experiments
- poor source coverage hidden in reports
- full-text claims without locators
- query-only analogies presented as conclusions
- LLM outputs accepted without grounding
- manuscript packages that imply fake results

## Fixture Policy

- Keep fixtures deterministic and small.
- Prefer synthetic excerpts unless licensing permits real short excerpts.
- Label synthetic content clearly.
- Include negative controls: duplicate ideas, unsupported claims, poor coverage, missing baselines, and not-ready reasons.
- Do not use live network or model calls.

## Interpreting Scores

Eval scores are regression signals. A passing eval means GapForge preserved safety and behavior on curated cases. It does not mean a generated research direction is novel, publishable, or exhaustive. Human expert review and additional source coverage remain required.
