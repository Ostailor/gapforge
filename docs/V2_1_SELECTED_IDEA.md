# GapForge v2.1 Selected Idea

v2.1 freezes the v2.0 accepted idea and uses it as the execution target.

In plain terms: v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`; v2.1 executes that selected idea. The synthetic smoke benchmark is not a final research result, low-FPR claims require power, and benchmark validity limitations must stay visible.

## Frozen Idea

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`
- Origin: v2.0 low-FPR collusion idea pilot
- v2.0 project: `v2-low-fpr-collusion-idea-pilot-3`
- v2.0 pilot: `pilot-v2_low_fpr_collusion-20260508T094317Z`
- Release status: human-accepted candidate idea, not empirical result

## Why This Idea

The accepted idea targets a concrete gap in low false-positive collusion auditing: monitors can look plausible when evaluated on isolated examples, but deployment-like audit settings need sequential specificity guarantees under repeated benign interactions.

The execution hypothesis is:

> A benchmark that stresses benign coordination and repeated audits can make false-positive risk visible before collusion monitors are treated as operationally useful.

This is a candidate-level hypothesis. v2.1 must turn it into a benchmark artifact before stronger claims are allowed.

## Scope Freeze

v2.1 should execute this exact scope:

- benchmark sequential audit behavior, not one-shot classification only
- prioritize low false-positive specificity under honest-agent traffic
- include collusive-agent scenarios for sensitivity context
- include benign-but-suspicious hard negatives
- evaluate baseline monitors honestly before advanced methods
- report uncertainty and power limits
- produce a manuscript package update that labels smoke results as smoke results

Out of scope for v2.1:

- broad real-world multi-agent deployment validation
- human-subject or private production data
- claims of monitor superiority from synthetic fixtures
- venue submission or camera-ready readiness
- replacement of prior-work and novelty checks

## Required v2.1 Artifacts

The selected idea is not executed until these artifacts exist:

1. Benchmark specification.
2. Threat model and observability assumptions.
3. Benchmark task definitions.
4. Synthetic/fixture data generator.
5. Honest-agent baseline distribution.
6. Collusive-agent scenario distribution.
7. Sequential audit protocol.
8. Low-FPR specificity metrics.
9. Baseline monitor suite.
10. Statistical power/sample-size plan.
11. Experiment workspace.
12. Benchmark smoke manifest and run record.
13. Result artifacts and parsed metrics.
14. Analysis report with limitations.
15. Reviewer critique.
16. Manuscript package update.

## Evidence Gates Preserved

v2.1 must preserve:

- v1 literature and closest-prior-work gates
- v2 accepted-candidate provenance
- fake citation and fake result rejection
- artifact-backed empirical claims only
- benchmark smoke versus pilot versus main run separation
- human review before stronger readiness claims

## Pivot Policy

A v2.1 pivot is allowed only when the frozen idea cannot be executed without changing its core contribution. If that happens, the release candidate must record:

- what execution blocker was found
- which part of the frozen idea failed
- whether the blocker requires v2.1 redesign, v2.2 planning, or a new v2 idea-discovery run
- why no replacement idea was silently substituted

## Non-Claims

v2.1 selected-idea execution does not mean:

- the benchmark is scientifically final
- synthetic fixtures represent real collusion deployments
- baseline results are empirical proof
- the manuscript package is submission-ready
- novelty is guaranteed beyond the recorded v2.0 scope

## Next Evidence Step

The next steps toward pilot/main benchmark are to preserve this frozen scope, run a smoke benchmark only as artifact-backed wiring evidence, then expand the honest null distribution, collusive alternatives, baseline suite, and sample size before making any stronger low-FPR or benchmark-validity claim.
