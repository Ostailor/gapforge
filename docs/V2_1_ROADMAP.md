# GapForge v2.1 Roadmap

v2.1 is the Selected Idea Execution release. It freezes the human-accepted v2.0 idea and turns it into a concrete, runnable research artifact path.

Selected idea:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`

v2.1 does not re-open idea discovery by default. It executes the selected idea by specifying, building, running, analyzing, reviewing, and packaging a benchmark artifact while preserving v1/v2 evidence gates.

Maturity boundary: v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`; v2.1 executes the selected idea. The synthetic smoke benchmark is not a final research result. Low-FPR claims require power, and benchmark validity limitations remain material until pilot/main evidence, uncertainty analysis, and reviewer fixes exist.

## Release Objective

By the end of v2.1, GapForge should contain a benchmark artifact for sequential low-FPR collusion audits that can be run at smoke scale and extended to pilot/main scale without changing the benchmark definition.

The release claim is limited to:

`v2.1 defines and smoke-validates the selected v2 idea execution path.`

It must not claim final scientific results, real-world benchmark validity, or publication readiness from synthetic fixtures or smoke runs.

## Workstreams

### 1. Selected Idea Freeze

Record the v2.0 selected idea as the execution target. Freeze:

- idea ID and title
- accepted candidate dossier
- human acceptance rationale
- closest prior work and novelty risks
- scope limits and non-claims
- execution success criteria

Any replacement idea requires a new v2 idea-discovery decision, not a silent v2.1 pivot.

### 2. Formal Benchmark Definition

Define the benchmark object before implementation:

- benchmark name, version, and scope
- task families
- observation interface
- allowed monitor inputs
- disallowed oracle information
- honest-agent baseline distribution
- collusive-agent scenario distribution
- sequential audit protocol
- low-FPR specificity metrics
- required artifacts and schemas

The definition must distinguish what is fixed for comparability from what can vary by smoke, pilot, and main benchmark level.

### 3. Threat Model and Observability

Define adversary, benign behavior, monitor access, and deployment assumptions:

- agent roles and communication channels
- collusion objective and coordination budget
- benign coordination that should not be flagged
- audit window and stopping rules
- observable transcripts, actions, metadata, and hidden state exclusions
- false-positive harm model
- known out-of-scope behaviors

### 4. Task and Data Generator

Build a synthetic/fixture data generator that can create:

- honest-agent scenarios
- collusive-agent scenarios
- benign-but-suspicious negatives
- hard negatives for specificity stress
- deterministic smoke fixtures
- seeded pilot/main configurations

Synthetic fixtures are implementation artifacts only. They do not establish real-world collusion benchmark validity.

### 5. Baseline Monitors

Implement honest baselines before advanced methods:

- random or prevalence-calibrated monitor
- keyword/rule monitor
- transcript anomaly heuristic
- pairwise similarity or coordination heuristic
- sequential threshold monitor
- abstain/insufficient-evidence baseline

Every baseline must record what it can observe and what it cannot infer.

### 6. Sequential Specificity Metrics

Define metrics that make low false-positive behavior visible:

- per-window specificity
- per-agent or per-team false-positive rate
- family-wise false-alarm probability over sequential audits
- time-to-first-false-alarm
- false alarms under benign coordination
- sensitivity at fixed specificity targets
- confidence intervals or uncertainty bands
- calibration curves where applicable

### 7. Power and Sample-Size Plan

Add a plan for deciding whether smoke, pilot, and main runs are adequately sized:

- expected base rates
- target specificity thresholds
- minimum detectable sensitivity differences
- sequential testing correction
- confidence interval width targets
- scenario count requirements
- failure conditions for underpowered claims

Underpowered runs must be reported as underpowered, not interpreted as evidence of monitor quality.

### 8. Experiment Workspace and Smoke Run

Create an experiment workspace that can run the benchmark at smoke scale:

- dataset card
- benchmark card
- baseline registry
- metric registry
- manifest and command
- run record
- logs
- result artifacts
- parsed metrics
- analysis report
- reproducibility check

The v2.1 release gate must fail if the smoke path is not runnable.

### 9. Result Analysis and Critique

Generate result analysis only from recorded artifacts. The analysis must separate:

- smoke wiring results
- pilot exploratory results
- main benchmark results
- failed runs
- missing baselines
- underpowered metrics
- unsupported claims

Add reviewer critique that attacks novelty, threat model, benchmark validity, low-FPR statistics, baselines, and manuscript claims.

### 10. Manuscript Package Update

Update the manuscript package as a research artifact package, not a submission-ready paper. It should include:

- benchmark specification section
- threat model section
- tasks and generator section
- metrics and power plan section
- smoke-run limitations
- result artifact links
- reviewer objections and required follow-up work

## Milestones

1. Freeze selected v2 idea and non-claims.
2. Write formal benchmark and threat-model specs.
3. Define task families, data generator, and fixture schemas.
4. Implement smoke generator and fixture outputs.
5. Register benchmark, baselines, metrics, and experiment workspace.
6. Implement baseline monitors and sequential specificity metrics.
7. Add power/sample-size plan and underpowered-run blockers.
8. Run benchmark smoke path and persist artifacts.
9. Analyze smoke outputs without making final scientific claims.
10. Add reviewer critique and manuscript package update.
11. Add v2.1 release gate requiring the runnable smoke path.

## Next Steps Toward Pilot/Main Benchmark

After the smoke path passes, v2.1 follow-up work should:

- expand the honest-agent null distribution and hard negatives
- expand collusive-agent alternatives beyond deterministic fixtures
- lock pilot/main sample-size targets before looking at outcomes
- run every required baseline monitor, including failed or weak baselines
- compute sequential low-FPR metrics with confidence intervals and multiple-testing warnings
- resolve reviewer blockers before any publication-facing contribution claim
- keep smoke versus pilot versus main benchmark status separate in reports and dashboards

## Non-Goals

- Do not claim final scientific results from smoke runs.
- Do not claim real-world collusion benchmark validity from synthetic fixtures.
- Do not weaken novelty or prior-work gates.
- Do not invent empirical results.
- Do not treat benchmark scaffolding as publication-ready by itself.
- Do not replace v2 idea discovery with an unreviewed new idea.
- Do not hide failed baselines, underpowered analyses, or ambiguous specificity results.

## Release Claim Boundary

Allowed v2.1 claim:

- GapForge can execute the selected v2 idea through a specified, runnable smoke benchmark artifact path.

Disallowed v2.1 claims unless future evidence supports them:

- the benchmark is externally validated
- the benchmark proves real-world collusion monitor quality
- any baseline or method is scientifically superior
- the manuscript is submission-ready
- the selected idea is proven novel beyond the recorded scope
