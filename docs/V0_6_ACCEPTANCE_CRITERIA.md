# GapForge v0.6 Acceptance Criteria

v0.6 acceptance is about empirical execution integrity. A direction can only move beyond experiment-ready when GapForge has durable evidence that an experiment was run or failed in a recorded way.

## Definitions

- **Experiment protocol**: a design document with objective, hypothesis, datasets, baselines, metrics, statistical plan, ablations, falsification conditions, and reproducibility checklist.
- **Experiment scaffold**: generated repository/workspace files that could run the experiment, but have not necessarily been executed.
- **Smoke run**: a small execution meant to validate wiring, commands, and artifact generation. A smoke run does not establish empirical success.
- **Pilot run**: an exploratory execution that can identify design flaws, variance, or missing baselines. It must be labeled pilot and cannot be written as a final result.
- **Main run**: the intended empirical execution for a protocol. It still supports claims only through parsed result artifacts and uncertainty analysis.
- **Executed experiment**: a run with a manifest, execution log, result artifact, environment/config record, and reproducibility status.
- **Failed experiment**: an attempted run with a run record, failure status, logs, and failure reason.
- **Negative experiment**: an executed experiment whose results do not support the intended hypothesis.

## Required Release Criteria

1. Versioned docs explain v0.6 experiment execution boundaries.
2. At least one fixture experiment executes through the v0.6 path.
3. At least one failed or negative experiment path is recorded and reported.
4. No result claim can be marked supported without a linked result artifact.
5. Smoke tests are clearly labeled and cannot be used as empirical success.
6. Paper package exports separate real results, placeholders, expected/hypothetical results, and missing results.
7. Experiment logs, run manifests, dataset cards, baseline cards, metric definitions, and reproducibility checks are persisted.
8. Empirical reviewer simulation uses the protocol, result artifacts, statistics, and reproducibility checks.
9. CI remains deterministic and does not require expensive experiments, live sources, or live LLM calls.
10. v0.5 literature/novelty gates remain intact for any direction that claims empirical relevance.

## Required Artifacts

For an executed experiment:

- `experiment_workspace/`
- `dataset_cards.json` or `dataset_cards.md`
- `baseline_registry.json`
- `metric_registry.json`
- `run_manifest.json`
- `execution_log.md`
- `result_artifacts.json`
- `statistical_analysis.md`
- `reproducibility_check.md`
- `result_claim_ledger.json`
- `empirical_review.md`
- `paper_package_v2/paper_package.json` if a package is exported

For a failed experiment:

- `run_manifest.json`
- `execution_log.md`
- `failure_record.json`
- `failure_report.md`
- visible report language that does not bury the failed status

## Acceptance Tests

The v0.6 test suite should cover:

- fixture experiment workspace creation
- dataset card validation
- baseline/metric registry validation
- run manifest persistence
- execution log persistence
- result artifact linkage
- statistical analysis rendering
- reproducibility check pass/fail behavior
- failed experiment reporting
- negative result claim handling
- paper package result separation
- v6 release gate failure when only protocols/scaffolds/smoke labels exist
- API workflows for workspace creation, fixture execution, result parsing, and package export

## Rejection Conditions

Reject v0.6 release acceptance if:

- any empirical claim is supported only by a protocol, scaffold, smoke test, or model-generated text
- a failed run is hidden from reports
- negative results are softened into success language
- generated placeholders are labeled as real results
- CI requires expensive execution
- literature/novelty gates are weakened to get to experiment execution faster

## Claim Boundary

Result claims are artifact-gated:

- a protocol can support a planned experiment claim
- a scaffold can support an implementation-readiness claim
- a smoke run can support a wiring/artifact-production claim
- pilot/main/ablation/reproduction runs can support empirical claims only when result artifacts parse into metric results
- failed or negative runs support failure/negative-result claims and must remain visible

No model summary, notebook prose, TODO, expected-results section, or Codex code task can substitute for a result artifact.
