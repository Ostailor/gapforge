# GapForge v0.9 Roadmap

v0.9 is the external pilot and v1-readiness release.

v0.8 validated manuscript, artifact evaluation, reviewer-rebuttal, and submission-package mechanics with fixtures and local artifacts. v0.9 must use GapForge on one real end-to-end research pilot and decide honestly whether the result is a defensible research direction or an evidence-backed refusal.

The recommended pilot topic is:

> low false-positive collusion detection in LLM multi-agent systems

v0.9 is not a publication claim. It is the first release where GapForge must carry a real topic from broad framing through live literature, novelty review, experiment planning, artifact packaging, manuscript drafting, reviewer/rebuttal planning, and v1 readiness assessment.

## Goals

1. Run one real external pilot topic through the full GapForge workflow.
2. Start from a broad topic and record a live literature campaign with source diagnostics, search rounds, canonicalization, closest-prior-work review, and missed-search accounting.
3. Produce either a novelty-checked, defensible research direction or an explicit refusal when coverage, novelty, feasibility, or evidence is too weak.
4. Create an experiment protocol and run either a benchmark/fixture-backed canary or a small real run with clear limits.
5. Generate an artifact package from recorded workspace, benchmark, replication, and manuscript state.
6. Draft a manuscript package that preserves unsupported claims, missing evidence, failed runs, and limitations.
7. Produce a reviewer-objection ledger and rebuttal or refusal plan.
8. Capture external reviewer or pilot feedback from someone who did not author the run.
9. Audit migration and backward compatibility from v0.8 state and commands.
10. Decide whether GapForge is v1-ready using an explicit gate.

## Must-Have Workstreams

### External Pilot Topic

- use one named real topic, preferably `low false-positive collusion detection in LLM multi-agent systems`
- record topic framing, scope exclusions, venue-like audience, source profile, and reviewer expectations
- preserve a topic decision log from broad topic through accepted direction or refusal
- record all live source failures, unavailable data, rate limits, and manual search additions

### End-to-End Project Run

The pilot must exercise the full project chain:

1. broad topic intake
2. live literature campaign
3. closest-prior-work and novelty review
4. direction decision or refusal
5. experiment protocol
6. benchmark/fixture or small real run
7. artifact package
8. manuscript draft
9. reviewer/rebuttal plan
10. v1 readiness assessment

Skipping a stage is allowed only when the skip is recorded as a blocker or refusal reason.

### Research-Direction Quality Review

- require human quality review of source coverage, closest prior work, novelty, feasibility, metrics, baselines, and likely failure cases
- require a conservative direction classification: `defensible`, `needs_more_search`, `needs_more_experiment`, `refused`, or `blocked`
- reject strong novelty claims when closest-prior-work evidence is incomplete
- reject result claims when no run record and result artifact exist

### Honest Refusal Path

v0.9 can pass with refusal if the refusal is evidence-backed and useful.

A valid refusal must include:

- completed or explicitly blocked live search rounds
- closest-prior-work conflicts or coverage gaps
- why the direction is not ready
- what evidence would change the decision
- downstream artifacts marked blocked rather than fabricated

### v1 Readiness Gate

v0.9 must include a v1 readiness assessment. The assessment should say `ready`, `not_ready`, or `ready_with_explicit_scope`, with blockers and evidence.

v1 cannot be declared until the v1 readiness gate passes.

### Migration and Backward Compatibility Audit

- verify v0.8 manuscript, artifact evaluation, rebuttal, and submission-package state remains readable
- document command changes and deprecated paths
- provide migration notes for project, run, manuscript, artifact package, and release-gate state
- refuse silent schema migration that drops evidence, blockers, or human decisions

### CLI Workflow Cleanup

- reduce the pilot command path to a documented golden path
- identify confusing or duplicate commands
- distinguish fixture smoke, live pilot, small real run, submission package, and readiness gate commands
- add `--next-commands` or equivalent guidance where a gate fails, if implemented
- preserve strict gates even when improving CLI ergonomics

### Docs Usability Pass

- add a v0.9 quickstart/runbook for the external pilot
- explain every readiness term in one place
- label fixture-only examples as fixture-only
- add troubleshooting for common pilot blockers
- update README, release process, limitations, and Codex agent contract

### Artifact Hygiene

- record which pilot artifacts are safe to commit, private, cache-only, generated, or reviewer-facing
- prevent large downloads, private data, raw transcripts, credentials, and local environment files from entering source
- require manifests and checksums/version identifiers where practical
- keep failed, negative, underpowered, and incomplete artifacts visible

### External Feedback Capture

- capture at least one external reviewer or pilot-user feedback record
- classify feedback as blocker, required fix, optional improvement, disagreement, or accepted risk
- require a response plan for blocker feedback
- include feedback in the v1 readiness decision

## Non-Goals

- Do not force a research idea if novelty is weak.
- Do not claim real publication readiness unless the gates pass.
- Do not fabricate missing experiments.
- Do not count fixture-only results as real empirical success.
- Do not weaken any release gate to make the pilot pass.
- Do not call v1 until the v1 readiness gate passes.
- Do not claim venue submission, reviewer acceptance, camera-ready status, or artifact-evaluation acceptance unless external evidence exists.

## Milestones

1. v0.9 documentation and runbook.
2. External pilot project created with topic, source policy, and artifact hygiene plan.
3. Live literature campaign completed or explicitly refused.
4. Direction quality review completed.
5. Experiment protocol and benchmark/fixture or small real run completed, or refused with evidence.
6. Artifact package and manuscript draft generated with blockers visible.
7. Reviewer/rebuttal plan and external feedback captured.
8. Migration/backward compatibility audit completed.
9. CLI/docs usability pass completed.
10. v1 readiness assessment completed.

## Release Claim

The strongest allowed v0.9 release claim is:

`v0.9 completed the first real external pilot workflow and recorded whether GapForge is v1-ready.`

If the pilot refuses the research direction, the release can still pass if the refusal is evidence-backed and all refusal artifacts are complete.
