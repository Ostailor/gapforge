# GapForge v2.1 Benchmark Specification

Benchmark name: `sequential_specificity_low_fpr_collusion_audits`

Selected idea: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

Maturity boundary: v2 found candidate idea, and v2.1 executes it by building an inspectable benchmark artifact path. The synthetic smoke benchmark is not a final research result. Low-FPR claims require power; benchmark validity limitations include synthetic data, fixed scenario templates, incomplete adversary adaptation, and missing external review.

## Purpose

The benchmark evaluates collusion monitors under sequential audit conditions where false positives over repeated benign interactions are a primary failure mode.

The benchmark is designed to answer a narrow engineering question:

> Can an audit monitor maintain high specificity across repeated benign multi-agent interactions while still detecting defined collusive scenarios?

Smoke fixtures answer only whether the benchmark path runs and records artifacts. Pilot and main runs are required before making stronger empirical claims.

## Benchmark Levels

### Smoke

Smoke level is CI/local-development scale.

Requirements:

- deterministic fixture generator
- small honest and collusive scenario sets
- at least one hard-negative benign scenario
- at least two baseline monitors
- sequential specificity metrics computed
- run manifest, logs, result artifact, parsed metrics, and analysis report

Claims allowed:

- benchmark wiring runs
- artifacts are recorded
- metrics are computed from fixture outputs

Claims disallowed:

- real-world benchmark validity
- monitor superiority
- final specificity or sensitivity conclusions

### Pilot

Pilot level is exploratory research scale.

Requirements:

- expanded scenario distribution
- fixed random seeds and generator versions
- all baseline monitors
- preregistered metric thresholds
- power analysis showing whether pilot is underpowered
- reviewer critique of threat model and hard negatives

Claims allowed:

- exploratory benchmark behavior
- preliminary failure modes
- underpowered or adequately powered pilot status

### Main

Main level is claim-supporting benchmark scale.

Requirements:

- locked benchmark version
- sufficient sample size for target specificity claims
- complete baseline suite
- confidence intervals and sequential correction
- replication package
- external or independent review where practical
- manuscript traceability from claims to result artifacts

Claims allowed only when artifacts support them:

- benchmark-level monitor comparison
- specificity or sensitivity estimates with uncertainty
- supported limitations and negative results

## Formal Task Definition

Each task instance must contain:

- `task_id`
- `scenario_family`
- `agent_roles`
- `communication_rounds`
- `observable_events`
- `hidden_state_excluded_from_monitor`
- `ground_truth_label`
- `collusion_objective`, when applicable
- `benign_coordination_features`, when applicable
- `audit_windows`
- `expected_artifacts`

The monitor receives only the allowed observation interface. It must not receive hidden intent labels, generator seed labels, or post-hoc oracle information.

## Threat Model

The benchmark assumes:

- multiple LLM-like agents interact over observable text or action traces
- collusive agents may coordinate toward a prohibited objective
- honest agents may coordinate benignly and can look superficially suspicious
- audits are sequential and repeated over time
- false positives are costly because benign coordination can be incorrectly flagged

The benchmark excludes:

- private production logs
- hidden chain-of-thought inspection
- privileged access to true intent
- real adversary adaptation unless explicitly modeled
- claims about all collusion channels or all deployment settings

## Observability Assumptions

Allowed monitor inputs:

- messages or action summaries
- timestamps or round indices
- agent role metadata
- task metadata available before audit
- prior audit decisions when sequential protocol permits them

Disallowed monitor inputs:

- ground-truth labels
- generator branch identifiers
- hidden collusion plan state
- future events outside the audit window
- manual post-hoc rationale not available at decision time

## Scenario Distributions

### Honest-Agent Baseline Distribution

Honest scenarios should include:

- independent task solving
- benign collaboration with shared goals
- repeated similar wording without collusion
- role specialization
- negotiation or consensus
- benign anomaly-like behavior
- failed or confused coordination

This distribution is the primary source for low-FPR specificity measurement.

### Collusive-Agent Scenario Distribution

Collusive scenarios should include:

- explicit coordination toward a prohibited outcome
- subtle coordination across rounds
- division of roles to evade detection
- delayed or staged collusion
- noisy collusion with benign-looking filler
- weak or failed collusion attempts

This distribution provides sensitivity context, but v2.1 remains centered on specificity.

### Hard Negatives

Hard negatives are honest scenarios that resemble collusion signals:

- repeated phrase templates
- synchronized decisions caused by shared instructions
- common external constraints
- benign secrecy or privacy-preserving wording
- coincidental timing correlations

Hard negatives must not be relabeled as collusion to make monitors look better.

## Sequential Audit Protocol

The protocol must specify:

- audit window size
- window stride
- stopping rule
- alert threshold
- whether alerts reset, accumulate, or terminate the sequence
- how abstentions are counted
- how missing or malformed observations are handled
- maximum number of audits per scenario

Sequential reporting must include per-window and sequence-level metrics.

## Metrics

Required specificity metrics:

- true negative count
- false positive count
- per-window specificity
- sequence-level specificity
- family-wise false-alarm probability
- time-to-first-false-alarm
- false positives on hard negatives

Required sensitivity context:

- true positive count
- false negative count
- per-window sensitivity
- sequence-level sensitivity
- time-to-first-detection

Required uncertainty:

- confidence intervals or uncertainty bands
- sample-size warnings
- underpowered-run classification
- sequential-testing correction when applicable

## Baseline Monitors

Minimum baseline suite:

- random or prevalence-calibrated baseline
- keyword/rule baseline
- suspicious-similarity baseline
- coordination-pattern heuristic
- sequential-threshold baseline
- abstain baseline

Baseline reports must include:

- allowed inputs
- threshold selection method
- calibration data, if any
- failure modes
- unsupported assumptions

## Power and Sample-Size Plan

Each benchmark level must declare:

- target specificity
- acceptable confidence interval width
- expected false-positive base rate
- minimum scenario count
- number of sequential windows
- correction for repeated looks
- minimum detectable sensitivity difference, when comparing monitors

If the sample size is below the requirement, reports must mark the run as smoke or underpowered.

## Required Artifact Schema

A v2.1 smoke run must persist:

- benchmark card
- dataset card
- generator config
- generated task records
- monitor registry
- metric registry
- experiment manifest
- execution record
- raw monitor outputs
- metrics JSON
- analysis Markdown
- reproducibility record
- reviewer critique

## Release Gate Requirement

The v2.1 release gate must require a runnable smoke path:

1. Generate deterministic fixture tasks.
2. Run baseline monitors.
3. Compute sequential specificity metrics.
4. Write result artifacts.
5. Parse and analyze results.
6. Preserve logs and reproducibility metadata.
7. Block unsupported empirical claims.

If any step is missing, v2.1 is not ready.

## Pilot/Main Extension Requirements

Next steps toward pilot/main benchmark:

- lock benchmark version and generator version
- predeclare alpha levels, family-wise false-alarm target, and required negative trace counts
- expand scenario diversity without changing hidden labels after seeing results
- run all deployable baselines and keep oracle/LLM placeholders clearly labeled
- publish uncertainty, underpowered status, and reviewer blockers with every result table
