# GapForge v2.2 Acceptance Criteria

v2.2 acceptance is about pilot-scale benchmark honesty. It must require a real pilot run manifest and artifact-backed pilot result package for the locked selected idea, while preserving low-FPR, prior-work, and reviewer gates.

## Definitions

- **Smoke benchmark**: a small deterministic synthetic fixture run that proves the benchmark path executes.
- **Pilot benchmark**: an exploratory study with expanded synthetic distributions, full baselines, preregistered metrics, sample-size status, result artifacts, and reviewer-blocker classification.
- **Main benchmark**: a claim-supporting study with sufficient sample size for stated low-FPR targets, locked protocol, replication package, and completed review gates.
- **Power-gated low-FPR claim**: a specificity or alpha claim that is allowed only when the honest negative count, sequential correction, and uncertainty report support it.
- **Reviewer blocker**: an objection that must be resolved, preserved as a release warning, or marked as a release blocker.

## Required Documentation Criteria

1. v2.2 docs clearly distinguish smoke, pilot, and main benchmark maturity.
2. v2.2 roadmap names the selected idea and preserves the v2.1 lock.
3. v2.2 pilot benchmark spec defines expanded honest, collusive, and hard-negative distributions.
4. v2.2 power plan defines sample-size gates before pilot outcomes.
5. v2.2 reviewer-blocker doc preserves unresolved blockers instead of hiding them.
6. v2.2 docs prohibit deployment validity and unsupported `alpha=0.001` claims.
7. v2.2 docs require prior-work recall and related-work matrix attachment before publication-readiness claims.

## Required Pilot Criteria

The v2.2 release gate must fail unless all are true:

1. Pilot run manifest exists with `run_type: pilot`.
2. Manifest locks benchmark version, generator version, seeds, scenario counts, monitor thresholds, metrics, alpha targets, and expected artifacts before result inspection.
3. Honest-agent null distribution is expanded beyond smoke fixtures.
4. Collusive-agent alternative distribution is expanded beyond deterministic smoke fixtures.
5. Strong hard-negative traces are present and reported as honest negatives.
6. Full baseline monitor suite runs, or each missing baseline has an explicit blocker.
7. Pilot result artifacts exist and are parsed before analysis.
8. Sequential low-FPR metrics include uncertainty and repeated-look correction.
9. Power report classifies every low-FPR target as supported, underpowered, or unsupported.
10. Prior-work recall and related-work matrix are attached, or publication readiness is blocked.
11. Reviewer blockers are classified as `resolved`, `preserved_warning`, or `release_blocker`.
12. Pilot manuscript package exists or a blocked-manuscript report explains missing gates.
13. Reports separate smoke wiring evidence, pilot evidence, and main benchmark requirements.
14. Unsupported pilot/main/publication/deployment claims are blocked.

## Pass Outcomes

### Pass With Powered Pilot Evidence

v2.2 may pass with the strongest release language only when:

- pilot run manifest exists
- pilot result artifacts exist
- sample size supports the stated low-FPR claims
- all baselines ran or missing baselines are accepted warnings
- prior-work recall and related-work matrix are attached
- reviewer blockers are resolved or preserved without invalidating the pilot claim

Allowed release statement:

`v2.2 pilot benchmark study passed with artifact-backed pilot evidence within stated power limits.`

### Pass With Pilot Evidence and Preserved Warnings

v2.2 may pass with warnings when:

- pilot run manifest and result artifacts exist
- the pilot is underpowered for some low-FPR targets
- unresolved reviewer blockers remain visible
- publication readiness and unsupported alpha claims are blocked

Allowed release statement:

`v2.2 pilot benchmark study passed with preserved warnings; low-FPR and publication claims remain limited.`

### Incomplete Pilot

v2.2 must not pass if the strongest output is:

- another smoke run
- pilot prose without a locked manifest
- generated traces without baseline outputs
- monitor outputs without result artifacts
- metrics without confidence intervals or sample-size status
- manuscript prose without prior-work and artifact traceability

Required release statement:

`v2.2 pilot benchmark study incomplete; pilot run artifacts not ready.`

## Fail Conditions

v2.2 fails when:

- the selected idea is silently changed
- smoke evidence is presented as pilot evidence
- pilot run manifest is missing
- honest null distribution is not expanded
- collusive alternative distribution is not expanded
- hard negatives are missing or relabeled as positives
- full baseline suite is absent without blockers
- low-FPR metrics omit uncertainty or sequential correction
- `alpha=0.001` is claimed without adequate sample size
- synthetic pilot traces are described as real deployment data
- prior-work recall and related-work gates are incomplete but publication readiness is claimed
- reviewer blockers are omitted or softened
- pilot manuscript package claims submission readiness without gates

## Release Statement

Release notes must use one of:

- `v2.2 pilot benchmark study passed with artifact-backed pilot evidence within stated power limits`
- `v2.2 pilot benchmark study passed with preserved warnings; low-FPR and publication claims remain limited`
- `v2.2 pilot benchmark study incomplete; pilot run artifacts not ready`
- `v2.2 pilot benchmark study blocked; release blockers remain unresolved`

## v2.3 Readiness Criteria

A v2.2 pass does not imply v2.3 is ready. The v2.2 package should be considered ready for v2.3 planning only when it records:

- unsupported alpha targets and their required negative counts
- pilot false positives, especially hard-negative false positives
- missing or weak baselines
- incomplete prior-work categories
- reviewer blockers that were preserved rather than resolved
- synthetic-data external-validity risks
- main benchmark data, manifest, and replication requirements

If these are missing, v2.2 may still be a pilot artifact, but it is not a useful main-study handoff.
