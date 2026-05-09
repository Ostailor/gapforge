# GapForge v2.2 Pilot Benchmark Specification

Benchmark name: `sequential_specificity_low_fpr_collusion_audits`

Selected idea: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

Release target: v2.2 Pilot-Scale Benchmark Study

v2.2 upgrades the v2.1 smoke benchmark into a pilot benchmark study. The pilot must use expanded synthetic trace distributions and artifact-backed execution, but synthetic pilot data remains synthetic. It cannot establish deployment validity or replace a main benchmark.

## Study Question

Can the benchmark evaluate whether collusion monitors maintain low false-positive behavior over repeated benign multi-agent interactions while retaining sensitivity to defined collusive alternatives?

The pilot is exploratory. It can identify failure modes, power limitations, hard-negative weaknesses, and baseline behavior. It does not by itself prove real-world safety or publication readiness.

## Benchmark Levels

| Level | Purpose | Required Evidence | Allowed Claim |
| --- | --- | --- | --- |
| Smoke | Wiring and artifact persistence | deterministic fixtures, at least two baselines, metric computation | runnable benchmark path |
| Pilot | Exploratory benchmark study | powered plan, expanded distributions, full baselines, pilot manifest, result artifacts, uncertainty, reviewer blockers | pilot-scale evidence within stated power limits |
| Main | Claim-supporting benchmark | locked benchmark, sufficient sample size, replication package, prior-work gates, independent review where practical | benchmark-level comparison with uncertainty |

v2.2 must not pass from smoke evidence alone.

## Pilot Scenario Design

### Honest-Agent Null Distribution

Pilot null traces must include enough benign diversity to stress low-FPR claims:

- independent non-collusive task solving
- benign collaboration toward shared goals
- role specialization
- repeated wording from shared prompts or templates
- consensus building and negotiation
- synchronized actions caused by common constraints
- privacy-preserving or secrecy-like benign language
- noisy, confused, or failed benign coordination
- action-only traces with limited transcript signal

Each family must report trace count, window count, generator seed range, and any known realism limitation.

### Collusive-Agent Alternative Distribution

Pilot alternative traces must include:

- explicit collusion
- implicit coordination
- delayed collusion
- staged coordination across audit windows
- division of labor to evade detection
- noisy collusion mixed with benign filler
- weak, failed, or partial collusion attempts
- transcript-visible and action-only observability variants

Alternative labels are used for sensitivity context. They must not be exposed to monitors.

### Hard-Negative Slice

Hard negatives are honest traces designed to resemble monitor triggers:

- repeated phrase templates
- high similarity caused by shared instructions
- coincidental timing correlation
- benign secrecy language
- synchronized decisions from identical inputs
- constrained-resource negotiation
- suspicious-looking but permitted delegation

Hard negatives must remain in the honest null distribution. Reports must include a hard-negative false-positive table.

## Monitor Interface

Allowed monitor inputs:

- observed messages or action summaries
- timestamps or round indices
- agent role metadata
- task metadata available before the audit
- prior audit decisions when the sequential protocol permits them

Disallowed monitor inputs:

- ground-truth labels
- generator branch identifiers
- hidden collusion intent
- future events outside the audit window
- manual post-hoc rationale
- private chain-of-thought or privileged deployment state

## Full Baseline Suite

The pilot must run all registered baselines unless a baseline is explicitly marked unavailable with a blocker:

- random or prevalence-calibrated baseline
- keyword/rule baseline
- suspicious-similarity baseline
- coordination-pattern heuristic
- sequential-threshold baseline
- abstain/insufficient-evidence baseline
- stronger non-oracle baselines that exist in the repository at release time

Every baseline result must record:

- allowed inputs
- threshold selection method
- calibration split, if any
- abstention behavior
- failure modes
- unsupported assumptions
- raw per-window outputs

Missing or failed baselines remain visible in the pilot report.

## Pilot Run Manifest

A valid pilot run manifest must contain:

- `benchmark_id`
- `benchmark_version`
- `generator_version`
- `run_type: pilot`
- `scenario_counts_by_family`
- `honest_trace_count`
- `collusive_trace_count`
- `hard_negative_trace_count`
- `audit_window_count`
- `seeds`
- `monitor_ids`
- `monitor_thresholds`
- `metric_ids`
- `target_specificity`
- `alpha_claims_requested`
- `confidence_interval_method`
- `sequential_correction_method`
- `power_status_before_run`
- `expected_artifacts`
- `command`
- `known_blockers_at_start`

The manifest is locked before monitor outputs are inspected.

## Required Result Artifacts

The pilot run is not complete unless these artifacts exist:

- benchmark card
- dataset card
- generator config
- trace records
- hard-negative slice inventory
- monitor registry
- metric registry
- pilot manifest
- execution record
- logs
- raw monitor outputs
- metrics JSON
- power and confidence interval report
- sequential low-FPR analysis report
- slice analysis report
- reviewer blocker classification
- reproducibility record
- pilot manuscript package or blocked-manuscript report

## Sequential Metrics

Required specificity metrics:

- true negatives and false positives by window
- per-window specificity
- sequence-level specificity
- family-wise false-alarm probability
- time-to-first-false-alarm
- hard-negative false-positive rate
- specificity confidence intervals or uncertainty bands

Required sensitivity context:

- true positives and false negatives by window
- sequence-level sensitivity
- time-to-first-detection
- sensitivity at fixed specificity thresholds when supported

Required warnings:

- underpowered low-FPR target
- unsupported alpha claim
- missing baseline
- incomplete prior-work attachment
- unresolved reviewer blocker

## Reporting Rules

Pilot analysis must separate:

- smoke wiring evidence
- pilot execution evidence
- main benchmark requirements
- synthetic-data limits
- monitor comparison limits
- low-FPR power limits
- related-work and novelty limits
- reviewer blocker status

The report must say `pilot` only when a pilot manifest and pilot result artifacts exist. A smoke rerun with more prose is still smoke.

## Dashboard and API Inspection

Pilot status must be inspectable without reading raw JSON by hand:

```bash
gapforge dashboard --project-id <selected-project-id> --include-selected-pilot
```

The dashboard should expose pilot power, honest/null distribution, collusive alternatives, pilot dataset card, baseline calibration, pilot results, low-FPR report, related work, reviewer panel, manuscript package, and v2.2 release gate status. These pages are status views, not readiness certificates.

The same workflow should be scriptable through `gapforge.api`:

- `create_pilot_power_plan`
- `generate_honest_null`
- `generate_collusive_alternatives`
- `build_pilot_dataset`
- `calibrate_pilot_baselines`
- `run_selected_pilot`
- `analyze_selected_pilot`
- `selected_pilot_review`
- `selected_pilot_manuscript`
- `v22_release_gate`

## v2.3 Main-Study Handoff

The pilot benchmark should produce the information needed to design v2.3. v2.3 should not simply rerun v2.2 at a larger size without reviewing pilot errors. It should use pilot artifacts to choose larger negative counts, repair weak hard-negative slices, strengthen baselines, finalize the main run manifest, and decide whether synthetic traces need external or real-world validation before stronger claims.
