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

### v0.4 Campaign Fixtures

Located in `tests/fixtures/campaign_v4/`:

- `fake_agent_campaign`
- `novelty_research_loop`
- `undercovered_refusal`
- `invalid_agent_output`
- `experiment_ready_direction`
- `reviewer_fatal_flaw`

These fixtures test campaign behavior, actual-run gate logic, invalid output rejection, novelty re-search, stop reasons, direction maturity gates, review queues, code task quality, and rollback safety. They are synthetic offline fixtures and do not prove Codex/GPT-5.4 actual-run quality.

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

v0.4 metrics:

- `campaign_decision_quality`
- `stop_reason_correctness`
- `agent_output_validation_strictness`
- `actual_run_gate_correctness`
- `novelty_research_loop_quality`
- `direction_maturity_gate_accuracy`
- `campaign_report_honesty`
- `review_queue_quality`
- `experiment_code_task_quality`
- `rollback_safety`

### v0.5 Real-Literature Campaign Fixtures

Located in `tests/fixtures/real_literature_v5/`:

- `live_like_low_fpr_collusion`
- `live_like_monitor_evasion`
- `live_like_prior_work_duplicate`
- `live_like_undercovered_refusal`
- `live_like_cross_domain_specificity`

These are offline live-like fixtures. They test quality-gate behavior without live network calls and must not be presented as real literature conclusions.

v0.5 metrics:

- `live_source_coverage_score`
- `search_strategy_completeness`
- `prior_work_recall_gate_score`
- `canonicalization_quality`
- `real_literature_refusal_quality`
- `research_direction_quality_proxy`
- `quality_review_gate_correctness`
- `v5_release_gate_correctness`

## Commands

```bash
gapforge eval
gapforge eval --v2
gapforge eval --v3
gapforge eval --v4
gapforge eval --v5
gapforge eval --fixture low_fpr_collusion --v3
gapforge eval --fixture fake_agent_campaign --v4
gapforge eval --fixture live_like_low_fpr_collusion --v5
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
- fake-agent campaigns counted as actual-run acceptance
- invalid campaign output mutating state
- campaign reports recommending directions under poor coverage
- experiment-ready directions missing protocols, novelty dossiers, or related-work matrices
- rollback snapshots missing before import
- live-literature quality accepted without source health, search strategy, canonicalization, prior-work recall, or human quality review
- workflow-accepted campaigns counted as research-quality accepted
- undercovered campaigns recommending directions instead of refusing

## Fixture Policy

- Keep fixtures deterministic and small.
- Prefer synthetic excerpts unless licensing permits real short excerpts.
- Label synthetic content clearly.
- Include negative controls: duplicate ideas, unsupported claims, poor coverage, missing baselines, and not-ready reasons.
- Do not use live network or model calls.

## Interpreting Scores

Eval scores are regression signals. A passing eval means GapForge preserved safety and behavior on curated cases. It does not mean a generated research direction is novel, publishable, or exhaustive. Human expert review and additional source coverage remain required.

For v0.4, passing `gapforge eval --v4` means the offline campaign behavior fixtures passed. It does not mean actual Codex/GPT-5.4 campaign acceptance passed. Actual-run acceptance requires recorded real campaigns, validated imports, attestation, and human review.

For v0.5, passing `gapforge eval --v5` means offline real-literature quality gate fixtures passed. It does not mean live-literature campaign quality passed. That requires live source diagnostics, real campaign records, human quality review, and `gapforge v5-release-gate`.
