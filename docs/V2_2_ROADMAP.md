# GapForge v2.2 Roadmap

v2.2 is the Pilot-Scale Benchmark Study release for the locked v2 idea:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`

v2.1 reached runnable synthetic smoke maturity. v2.2 must move the same benchmark to a pilot-scale study with preregistered sample-size logic, expanded scenario distributions, full baseline execution, sequential low-FPR analysis, prior-work attachment, reviewer-blocker tracking, and manuscript-package outputs.

The release claim is limited to:

`v2.2 defines and requires a pilot-scale benchmark study path for the selected v2 idea.`

v2.2 must not claim deployment validity, operational specificity at `alpha=0.001`, final scientific results, or publication readiness unless the required pilot artifacts and gates actually support those claims.

## Maturity Boundary

- **Smoke**: proves wiring, schemas, artifact persistence, and basic metric computation on small synthetic fixtures.
- **Pilot**: exploratory, powered where possible for stated low-FPR targets, with expanded honest/collusive/hard-negative traces, all baselines, uncertainty reporting, and reviewer critique.
- **Main**: claim-supporting benchmark with locked design, sufficient sample size for target specificity claims, replication package, and completed prior-work and review gates.

v2.2 is a pilot release. A pilot can be informative and still preserve blockers. It is not a main benchmark and does not validate production deployment.

## Workstreams

### 1. Powered Pilot Sample-Size Plan

Define pilot sample-size requirements before running pilot outcomes:

- target specificity levels and supported alpha claims
- honest negative trace counts required for each low-FPR target
- hard-negative slice counts
- sequential window counts and family-wise false-alarm correction
- acceptable confidence interval width
- minimum detectable sensitivity differences for monitor comparisons
- underpowered-run labels and fail-closed claim behavior

If sample size cannot support `alpha=0.001`, the pilot must not use that phrase as an achieved operational specificity claim.

### 2. Expanded Honest-Agent Null Distribution

Expand the null distribution beyond smoke fixtures:

- benign independent work
- benign collaboration
- repeated wording from shared instructions
- role specialization
- consensus and negotiation
- privacy-preserving or secrecy-like benign language
- confused or failed coordination
- task families with naturally synchronized actions

The null distribution is the primary evidence source for low-FPR behavior. Relabeling hard negatives as positives to improve metrics is forbidden.

### 3. Expanded Collusive-Agent Alternative Distribution

Expand alternatives beyond deterministic smoke collusion:

- explicit collusion
- subtle or implicit coordination
- delayed or staged collusion
- role-split evasion
- noisy collusion mixed with benign filler
- weak, failed, or partial collusion attempts
- observability variants, including transcript-visible and action-only traces

Sensitivity is reported as pilot context, not as proof of monitor superiority unless the pilot design is adequately powered for the comparison.

### 4. Stronger Hard-Negative Traces

Hard negatives must be first-class pilot data:

- common-template repetition
- coincidental timing alignment
- benign shared constraints
- synchronized decisions from identical task context
- privacy-preserving wording
- suspicious-looking delegation without prohibited intent

Reports must publish false positives on hard negatives as a named slice.

### 5. Full Baseline Monitor Suite

Run every required baseline, including weak or failed baselines:

- random or prevalence-calibrated
- keyword/rule
- suspicious similarity
- coordination-pattern heuristic
- sequential-threshold
- abstain/insufficient-evidence
- any stronger available non-oracle baseline

Each baseline must declare allowed inputs, thresholds, calibration data, failure modes, and unsupported assumptions.

### 6. Pilot Run Manifest

The pilot manifest must lock:

- benchmark version
- generator version
- scenario counts by split and family
- seeds
- monitor suite and thresholds
- metric definitions
- alpha and confidence interval targets
- sequential audit protocol
- expected artifacts
- command path or API wrapper
- known blockers at run start

Changing labels, sample-size targets, baselines, or thresholds after seeing results requires a new run manifest.

### 7. Pilot Result Artifacts

Pilot results must be artifact-backed:

- dataset card
- benchmark card
- generator config
- generated trace records
- baseline registry
- metric registry
- pilot manifest
- execution record
- logs
- raw monitor outputs
- metrics JSON
- confidence interval and power report
- slice analysis
- reviewer-blocker report
- pilot analysis Markdown
- reproducibility record

Generated prose without these artifacts is not a pilot result.

### 8. Sequential Low-FPR Analysis

The analysis must report:

- per-window specificity
- sequence-level specificity
- family-wise false-alarm probability
- time-to-first-false-alarm
- hard-negative false-positive rate
- sensitivity context at fixed specificity thresholds
- confidence intervals or uncertainty bands
- repeated-look correction
- underpowered warning status

Zero false positives must be reported with uncertainty, not as proof of operational safety.

### 9. Prior-Work Recall and Related-Work Matrix Attachment

v2.2 must attach or explicitly block:

- prior-work recall report
- live or recorded search strategy
- closest-prior-work candidates
- related-work matrix
- benchmark and monitor comparison table
- missing-search list
- novelty risk statement

If these remain incomplete, publication readiness is blocked even if pilot execution succeeds.

### 10. Reviewer Blocker Resolution or Preservation

Every v2.1 reviewer blocker must be classified:

- `resolved`: artifact proves the blocker is addressed
- `preserved_warning`: the blocker remains but does not invalidate the pilot release claim
- `release_blocker`: the blocker prevents v2.2 pass

The underpowered low-FPR blocker is resolved only for the claims supported by the pilot sample size. Unsupported low-FPR targets must remain warnings or blockers.

### 11. Pilot Manuscript Package

The manuscript package may be pilot-shaped, not submission-ready, unless all gates pass:

- benchmark study description
- threat model
- pilot dataset and scenario distribution
- baseline suite
- sequential metric and power analysis
- artifact-backed pilot results
- related-work attachment status
- reviewer blockers and limitations
- main-benchmark next steps

### 12. No Pilot/Main Overclaiming

v2.2 release notes and docs must not claim:

- deployment validity
- real-world collusion benchmark validity from synthetic data
- `alpha=0.001` operational specificity without adequate negative counts
- monitor superiority without powered comparison
- publication readiness with incomplete prior-work or related-work gates
- main benchmark maturity from a pilot run

## Milestones

1. Write pilot benchmark spec and maturity boundary.
2. Preregister power and sample-size requirements.
3. Expand honest null, collusive alternative, and hard-negative scenario families.
4. Lock full baseline monitor suite and allowed inputs.
5. Define pilot run manifest schema and required artifacts.
6. Run or require a pilot benchmark execution, not another smoke-only path.
7. Analyze sequential low-FPR behavior with uncertainty and correction.
8. Attach prior-work recall and related-work matrix, or preserve blockers.
9. Re-run reviewer blocker classification.
10. Build pilot manuscript package with explicit non-claims.
11. Gate v2.2 on pilot artifacts and overclaim prevention.

## Release Claim Boundary

Allowed v2.2 claims:

- GapForge has a defined pilot-scale benchmark study release gate for the selected idea.
- A v2.2 release may pass only when a pilot run manifest and artifact-backed pilot results exist.
- Low-FPR claims are restricted to the sample size and uncertainty actually supported.

Disallowed v2.2 claims unless separately proven:

- deployment validity
- production monitor readiness
- main benchmark maturity
- publication readiness
- exhaustive prior-work coverage
- operational specificity at unsupported alpha levels

## v2.3 Handoff

v2.2 should leave a concrete main-study backlog, not a vague "more work" note. v2.3 remains responsible for:

- increasing honest/null negative counts enough to support any requested `alpha=0.001` claim
- expanding hard-negative families and documenting coverage gaps after pilot false positives
- adding stronger external or literature-grounded monitor baselines where feasible
- freezing a main benchmark manifest with replication-ready data, thresholds, and seeds
- validating whether synthetic scenarios transfer to externally reviewed or real-world traces
- completing prior-work recall and related-work matrix updates before any publication-readiness claim
- preserving reviewer blockers that were only narrowed, not resolved, in v2.2

The v2.3 starting state should be the v2.2 pilot artifact package plus its blocker table.
