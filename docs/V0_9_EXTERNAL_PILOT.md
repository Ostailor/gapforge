# GapForge v0.9 External Pilot

This runbook defines the first real GapForge pilot. It is intentionally narrow: one topic, full workflow coverage, strict refusal behavior, and enough external feedback to decide whether v1 is credible.

## Pilot Topic

Recommended topic:

`low false-positive collusion detection in LLM multi-agent systems`

Canonical pilot-specific docs:

- `docs/pilots/low_fpr_collusion/PILOT_SPEC.md`
- `docs/pilots/low_fpr_collusion/ACCEPTANCE_CRITERIA.md`
- `docs/pilots/low_fpr_collusion/REVIEW_CHECKLIST.md`

CLI helpers:

```bash
gapforge pilot-spec --name low_fpr_collusion
gapforge pilot-spec --name low_fpr_collusion --document acceptance
gapforge pilot-status --name low_fpr_collusion
```

Pilot framing should record:

- target domain: LLM multi-agent safety, monitoring, and evaluation
- core problem: detecting collusive behavior while minimizing false positives
- likely evidence types: AI safety papers, multi-agent evaluation papers, benchmark papers, monitoring or anomaly-detection methods, deployment-risk discussions
- likely metrics: false positive rate, recall/sensitivity, precision, calibration, confidence intervals, and cost of false alarms
- non-goal: proving a deployable detector without adequate real or benchmark-like evaluation

## Pilot Phases

### 1. Project Setup

Create a durable project and record the pilot scope.

Expected records:

- project ID
- topic statement
- source profile
- external reviewer target
- artifact hygiene plan
- acceptance outcome options: defensible direction or evidence-backed refusal

### 2. Live Literature Campaign

Run a live literature campaign unless live sources are unavailable. If sources are unavailable, record the outage and decide whether manual search can substitute.

Minimum evidence:

- source health report
- planned search strategy
- executed search rounds
- canonicalized paper set
- missing source or failed query list
- source coverage assessment

Search should include at least:

- direct query for low false-positive collusion detection in LLM agents
- query for LLM multi-agent collusion monitoring
- query for agent communication or coordination detection
- query for false-positive evaluation in AI safety monitoring
- query for closest prior benchmarks or surveys

### 3. Novelty and Direction Decision

Review closest prior work before recommending any direction.

Decision options:

- `defensible`: proceed to protocol and manuscript draft with conservative claims
- `needs_more_search`: no direction yet; search gaps are material
- `needs_more_experiment`: novelty may be plausible but empirical feasibility is unproven
- `refused`: closest prior work, weak novelty, poor coverage, or feasibility blockers prevent recommendation
- `blocked`: source/tooling failure prevents a research-quality decision

The decision must include:

- strongest closest-prior-work conflicts
- what appears new, if anything
- what remains unknown
- human reviewer judgment
- citations or paper IDs for every cited prior-work claim

### 4. Experiment Protocol

If the direction is defensible or needs empirical triage, write a protocol.

Required protocol fields:

- research question
- falsifiable hypothesis or explicit exploratory question
- dataset or scenario source
- baseline detector or comparison method
- metric definitions, especially false positive rate
- minimum sample-size or power caveat for low-FPR claims
- run classes: fixture smoke, small real run, full benchmark
- artifact and logging requirements
- refusal condition if no valid dataset or baseline exists

### 5. Benchmark/Fixture or Small Real Run

At minimum, the pilot should run a fixture or benchmark-like canary to validate workflow mechanics. A small real run may count as empirical pilot evidence only if it has real/non-fixture inputs, logs, artifacts, analysis, and review.

Required labels:

- `fixture_smoke`: workflow only, no empirical success claim
- `small_real_run`: limited empirical evidence, not publication proof
- `blocked`: dataset, baseline, compute, or policy issue prevents execution
- `failed` or `negative`: preserved as useful evidence

### 6. Artifact Package

Generate an artifact package from actual recorded state. If the package is incomplete, it must say why.

The package should include:

- manifest
- reproduce instructions
- data and license notes
- expected outputs
- result artifact list and hashes where practical
- known failures
- reviewer checklist
- safe-to-commit review

### 7. Manuscript Draft

Generate a manuscript draft or blocked-draft package.

Required draft behavior:

- unsupported claims are labeled or removed
- novelty claims cite closest prior work and coverage context
- result claims link to run records and artifacts
- fixture-only results are labeled as workflow checks
- limitations, failed runs, and missing baselines remain visible
- submission-ready is not claimed unless the v0.8 submission gate passes

### 8. Reviewer and Rebuttal Plan

Create reviewer objections from the manuscript, evidence, artifact package, and protocol.

The rebuttal plan should answer each objection with:

- evidence-backed manuscript edit
- additional search
- additional experiment
- artifact packaging fix
- concession or refusal

Unsupported rebuttal answers are blockers.

### 9. External Feedback

Capture feedback from at least one external reviewer, pilot user, or domain reviewer who did not author the run.

Feedback record should include:

- reviewer role and relationship to the pilot
- reviewed artifacts
- blocker findings
- required fixes
- optional suggestions
- disagreements
- whether the reviewer accepts the direction, refusal, or release readiness

### 10. v1 Readiness Assessment

Run the v1 readiness assessment after the pilot artifacts and feedback exist.

Allowed outcomes:

- `ready`: v1 can be prepared within documented scope
- `ready_with_explicit_scope`: v1 can be prepared only with clearly narrowed claims
- `not_ready`: v1 is blocked

## Suggested Command Path

The exact CLI may evolve during v0.9. The documented golden path should converge on a short sequence like:

```bash
gapforge init-project "v0.9 low-FPR collusion pilot"
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge live-source-diagnostic --topic "low false-positive collusion detection in LLM multi-agent systems" --source-profile ai_safety --write-report
gapforge real-literature-run --profile live_low_fpr_collusion
gapforge campaign-report --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --reviewer "<expert>"
gapforge real-literature-acceptance --campaign-id <campaign-id>
gapforge experiment-protocol --project-id <project-id> --direction-id <direction-id>
gapforge benchmark-canary-run --profile <pilot-profile>
gapforge artifact-eval-package --manuscript-id <manuscript-id>
gapforge manuscript-review --manuscript-id <manuscript-id>
gapforge rebuttal-plan --manuscript-id <manuscript-id>
gapforge v9-release-gate --project-id <project-id> --write-report --json
gapforge v1-readiness --project-id <project-id> --write-report --json
```

If a listed command does not exist yet, the v0.9 CLI cleanup workstream must either implement it, replace it with the existing command, or document the gap as a blocker.

## Pilot Evidence Rules

- Live source failure is evidence only when recorded; it is not a pass by itself.
- Fixture runs validate mechanics only.
- A small real run must have run records and artifacts before supporting any empirical claim.
- Reviewer simulation is diagnostic; external feedback is still required.
- A refusal can be a successful pilot outcome when it prevents overclaiming.
