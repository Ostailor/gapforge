# GapForge v2.3 Main Benchmark Specification

Benchmark name: `sequential_specificity_low_fpr_collusion_audits`

Selected idea: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

Release target: v2.3 Main-Scale Benchmark and Publication-Readiness Upgrade

v2.3 upgrades the v2.2 pilot handoff into a main-scale benchmark decision. The release must either run a main benchmark with adequate power and complete artifacts, or record an explicit no-go.

## Study Question

Can the benchmark support a main-scale, artifact-backed evaluation of collusion monitors at low false-positive rates over sequential benign multi-agent interactions, while reporting sensitivity to defined collusive alternatives and preserving hard-negative false-positive risk?

The study remains bounded by its data. If the main dataset is synthetic, the result may support benchmark behavior for that synthetic benchmark only. It must not be described as deployment validity.

## v2.2 Handoff

v2.2 provides:

- 300 negative traces
- 150 positive traces
- 214 hard-negative traces
- pilot support for `alpha=0.01`
- underpowered and blocked `alpha=0.001`
- pilot baseline comparison and error analysis
- incomplete real prior-work records
- pilot manuscript package with fatal publication blockers

v2.3 must treat these as inputs to the main plan, not as main evidence.

## Main-Scale Sample-Size Plan

The main plan must be locked before main outcomes are inspected. It must record:

- requested alpha targets
- required honest/null trace count for each target
- required hard-negative trace count
- audit windows per trace
- effective negative count after sequential correction
- confidence level and interval method
- acceptable upper confidence bound for false-positive rate
- expected false-positive budget by family
- minimum detectable sensitivity difference for monitor comparisons
- planned treatment of abstentions
- stop rule for infeasible alpha targets

`alpha=0.001` is not available by default. The v2.2 handoff recorded 2995 required negatives for that target. v2.3 must either meet the corrected requirement or drop the claim.

## Alpha Decision Gate

The main manifest must include exactly one status for `alpha=0.001`:

- `powered`: required negative counts, correction, and uncertainty plan support the claim.
- `dropped`: the claim is removed from v2.3 main and manuscript claims.
- `blocked`: the release cannot pass as main-scale ready because the target is still requested but not supported.

If the target is `dropped`, the report may still mention that v2.2 explored it and found it underpowered. It must not present dropped targets as achieved.

## Main Dataset Path

v2.3 may use either a fresh main dataset or a pilot-to-main expansion. A valid dataset must include:

- `dataset_id`
- `benchmark_version`
- `generator_version`
- `dataset_type`
- `synthetic_data_label`
- `negative_trace_count`
- `positive_trace_count`
- `hard_negative_trace_count`
- `audit_window_count`
- `scenario_counts_by_family`
- `seed_ranges`
- `split_policy`
- `deduplication_report`
- `leakage_report`
- `external_review_status`
- `known_realism_limits`

Hard negatives remain honest negatives. Relabeling them as positives to improve metrics is a release blocker.
The implemented dataset builder is:

```bash
gapforge build-main-trace-dataset --benchmark-id <benchmark-id>
gapforge build-main-trace-dataset --benchmark-id <benchmark-id> --negative-count 3000 --positive-count 500
gapforge main-trace-dataset-report --dataset-id <main-dataset-id>
```

If the requested main dataset exceeds the local synthetic generation limit, the builder must persist a feasibility report instead of pretending that traces were generated.
Every generated or feasibility-only dataset reports scenario coverage, observability-mode counts, synthetic-only limitations, and explicit alpha support.

## Main Scenario Coverage

The honest/null distribution must include:

- independent benign work
- benign collaboration
- shared-template repetition
- role specialization
- consensus and negotiation
- synchronized actions from common constraints
- privacy-preserving or secrecy-like benign language
- confused or failed benign coordination
- action-only traces

The collusive distribution must include:

- explicit collusion
- implicit coordination
- delayed or staged collusion
- role-split evasion
- noisy collusion mixed with benign filler
- weak or failed collusion attempts
- transcript-visible and action-only variants

The hard-negative slice must include:

- repeated phrase templates
- high lexical similarity from shared instructions
- coincidental timing alignment
- benign secrecy language
- synchronized decisions from identical inputs
- constrained-resource negotiation
- suspicious-looking but permitted delegation

Reports must show family-level false positives and false negatives.

## Stronger Baseline Suite

The main suite must preserve v2.2 baselines and add stronger comparisons where feasible:

- random or prevalence-calibrated baseline
- keyword/rule baseline
- lexical or semantic similarity baseline
- repeated-action or repeated-template baseline
- coordination-pattern heuristic
- statistical anomaly detector
- sequential change-point detector
- calibrated anomaly detector
- permutation/null-distribution detector
- conformal-style score threshold detector
- action-only transition detector
- transcript-visible semantic heuristic detector
- robust lexical substitution monitor
- abstain or insufficient-evidence baseline
- prior-work-derived baselines from completed related-work records
- optional LLM judge baseline, opt-in only and never required in normal CI

Each baseline must declare allowed inputs, calibration split, threshold rule, abstention behavior, failure modes, and raw outputs. Missing prior-work-derived baselines are blockers unless the related-work matrix explains why no implementable baseline exists.
Strong contribution claims require `selected-baseline-strength` to report every required baseline present and no calibration leakage.

## Main Run Manifest

A valid main manifest must contain:

- `benchmark_id`
- `benchmark_version`
- `generator_version`
- `run_type: main`
- `dataset_id`
- `dataset_card_id`
- `scenario_counts_by_family`
- `honest_trace_count`
- `collusive_trace_count`
- `hard_negative_trace_count`
- `audit_window_count`
- `seeds`
- `monitor_ids`
- `monitor_thresholds`
- `metric_ids`
- `alpha_claims_requested`
- `alpha_0_001_decision`
- `confidence_interval_method`
- `sequential_correction_method`
- `power_status_before_run`
- `related_work_matrix_id`
- `baseline_registry_id`
- `expected_artifacts`
- `command`
- `known_blockers_at_start`

Changing thresholds, labels, sample-size targets, or baselines after seeing outcomes requires a new manifest.
Implemented main-run commands:

```bash
gapforge selected-main-manifest --benchmark-id <benchmark-id> --dataset-id <main-dataset-id>
gapforge selected-main-run --benchmark-id <benchmark-id> --manifest-id <main-manifest-id>
gapforge selected-main-status --execution-id <main-execution-id>
gapforge selected-main-analysis --execution-id <main-execution-id>
gapforge selected-benchmark-go-no-go --benchmark-id <benchmark-id>
gapforge selected-go-no-go-report --benchmark-id <benchmark-id>
```

The run status must preserve failures and must block publication claims when alpha support, required baselines, or calibration status are insufficient.
Synthetic main runs may back benchmark-artifact claims, but they must not become deployment-validity claims.
The go/no-go decision may be `no_go`; v2.3 should prefer a visible no-go over a publication-candidate overclaim.

## Required Result Artifacts

The main run is incomplete unless these artifacts exist:

- main dataset card
- benchmark card
- generator config
- trace records
- hard-negative inventory
- monitor and baseline registry
- metric registry
- main manifest
- execution record
- logs and return code
- raw monitor outputs
- predictions JSON
- metrics JSON
- power and confidence interval report
- sequential low-FPR report
- hard-negative error analysis
- baseline comparison report
- failure records, even when empty
- replication package
- reviewer panel report
- manuscript package or blocked-manuscript report
- go/no-go recommendation

## Metrics

Required specificity metrics:

- per-window true negatives and false positives
- sequence-level true negatives and false positives
- per-window specificity
- sequence-level specificity
- family-wise false-alarm probability
- time-to-first-false-alarm
- hard-negative false-positive rate
- confidence intervals or uncertainty bands

Required sensitivity context:

- true positives and false negatives by window
- sequence-level sensitivity
- time-to-first-detection
- sensitivity at fixed specificity thresholds when powered

Required comparison reporting:

- threshold and calibration summary
- baseline ranking with uncertainty
- slice-level error analysis
- missing-baseline blockers
- underpowered comparison warnings

## Main Go/No-Go

The main benchmark report must end with one of:

- `main_run_passed`: main artifacts exist and requested claims are supported.
- `main_run_passed_limited`: main artifacts exist but claims are narrowed.
- `main_run_no_go_power`: sample size or alpha support is inadequate.
- `main_run_no_go_data`: dataset generation or expansion is inadequate.
- `main_run_no_go_baselines`: required baselines are missing or too weak.
- `main_run_no_go_related_work`: related work is incomplete for the claims.
- `main_run_no_go_review`: fatal reviewer blockers remain.

Only `main_run_passed` and `main_run_passed_limited` may support a v2.3 pass, and publication readiness still requires the separate publication gate.

## Dashboard and API

Main benchmark status is inspectable without reading raw artifact folders:

```bash
gapforge dashboard --project-id <project-id> --include-selected-main
```

Use `main_power.html`, `main_dataset.html`, and `main_results.html` to inspect power feasibility, dataset alpha support, execution status, metrics, baseline comparison, error analysis, and low-FPR outputs.

The equivalent Python API path is:

```python
from gapforge import api

plan = api.create_main_power_plan(benchmark_id)
dataset = api.build_main_dataset(benchmark_id)
execution = api.run_selected_main(benchmark_id, dataset_id=dataset.id)
analysis = api.analyze_selected_main(execution.id)
decision = api.selected_go_no_go(benchmark_id)
```

If a main dataset is infeasible, the dataset builder must leave a feasibility artifact and the go/no-go path must narrow or reject the claim. Synthetic datasets remain synthetic evidence only.
