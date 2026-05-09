# GapForge v2.2 Reviewer Blockers

v2.2 does not erase v2.1 reviewer blockers. It must resolve them with artifacts or preserve them as warnings or release blockers.

## Blocker Status Vocabulary

- `resolved`: concrete artifact addresses the blocker for the stated claim.
- `preserved_warning`: blocker remains visible, but the release claim is narrowed so the blocker does not invalidate v2.2.
- `release_blocker`: blocker prevents v2.2 from passing.

## v2.1 Blockers Carried Forward

| Blocker | v2.2 Required Treatment |
| --- | --- |
| Underpowered low-FPR evidence cannot support pilot/main or publication claims. | Resolve only for targets supported by the v2.2 power report; preserve unsupported targets as warnings or blockers. |
| Smoke dataset is synthetic and underpowered. | Replace smoke-only evidence with pilot manifest and pilot artifacts; preserve synthetic-data limitation. |
| Prior-work recall and related-work matrix need deeper attachment. | Attach reports before publication-readiness claims; otherwise preserve as publication blocker. |
| Baselines are starting points, not strong scientific comparison. | Run full baseline suite and classify missing or weak baselines. |
| Synthetic data limitations remain major if overclaimed. | Keep synthetic pilot status explicit and prohibit deployment-validity claims. |

## Required Reviewer Panels

The v2.2 reviewer critique must cover:

- novelty and closest prior work
- threat model and observability
- honest null distribution realism
- collusive alternative realism
- hard-negative quality
- baseline strength and missing baselines
- sequential low-FPR statistics
- sample-size and power
- synthetic-data external validity
- manuscript claim traceability
- publication readiness

Each objection must map to an artifact, a release warning, a release blocker, or future main-benchmark work.

## Release-Blocking Objections

These objections block v2.2:

- no pilot run manifest
- no artifact-backed pilot result
- no expanded honest null distribution
- no expanded collusive alternative distribution
- no hard-negative slice
- no full baseline suite or missing-baseline blockers
- no sequential low-FPR uncertainty analysis
- sample-size targets chosen after seeing results
- unsupported `alpha=0.001` or deployment-validity claim
- smoke evidence described as pilot evidence
- unresolved reviewer blockers hidden from release notes

## Preserved Warnings

These may remain as warnings if clearly stated:

- synthetic pilot traces are not real deployment traces
- pilot is underpowered for some low-FPR targets
- hard-negative families are incomplete
- baselines are not SOTA monitors
- prior-work attachment is incomplete and publication readiness is blocked
- external expert review has not happened
- main benchmark sample size is still pending

## Publication-Readiness Gate

v2.2 must not claim publication readiness unless:

- prior-work recall report is attached
- related-work matrix is attached
- pilot result claims link to artifacts
- low-FPR targets are power-supported
- baseline limitations are visible
- reviewer blockers are resolved or accepted by human review
- manuscript package distinguishes pilot from main benchmark claims

If any item is missing, the manuscript package may be `pilot_manuscript_with_blockers` only.

## Required Blocker Report

The release must include a blocker table with:

- blocker ID
- source, such as v2.1 reviewer, v2.2 reviewer, power gate, or related-work gate
- status
- evidence artifact
- affected claim
- required follow-up
- release-note wording

The absence of a blocker report is itself a v2.2 release blocker.

## v2.3 Reviewer Handoff

The v2.2 panel should explicitly name which objections become v2.3 work:

- main-scale negative counts for unsupported alpha levels
- external review of synthetic honest/null and collusive scenario realism
- stronger or literature-grounded baselines
- deeper prior-work categories or closest-prior-work comparisons
- main benchmark replication and artifact packaging
- publication-readiness review after main results, not before

Preserved warnings should not disappear in v2.3 planning. They should either be resolved with artifacts, converted into narrower claims, or remain blockers.
