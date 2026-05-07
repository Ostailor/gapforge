# GapForge v0.8 Rebuttal Workflow

v0.8 rebuttal workflow turns reviewer objections into an evidence-backed response plan. It should help authors decide what to fix, what to concede, what to clarify, and what cannot be answered before submission or rebuttal deadlines.

It must not invent results, citations, reviewer sentiment, acceptance odds, or promises.

## Inputs

- manuscript project
- reviewer simulations
- human reviewer comments
- area-chair style summaries when available
- claim traceability report
- citation audit
- result artifacts and statistical analyses
- benchmark comparison and error-analysis reports
- artifact evaluation audit
- limitations and failed-run records
- venue rebuttal constraints such as length or anonymity

## Objection Ledger

Each objection should record:

- ID
- source: simulated reviewer, human reviewer, area chair, author audit, or venue checklist
- section or artifact link
- severity
- whether it blocks submission
- related claim IDs
- related citation keys
- related evidence or result artifact IDs
- suggested fix
- status: open, answered, needs experiment, needs search, conceded, rejected with rationale
- human owner

Major objections should stay visible until they are answered, conceded, or explicitly waived by a human decision.

## Rebuttal Plan

The rebuttal plan should map every objection to one of:

- manuscript edit backed by existing evidence
- new citation search or prior-work review
- additional experiment, ablation, replication, or artifact packaging task
- figure/table regeneration from existing artifacts
- limitation or concession
- refusal to answer because evidence is missing

Invented responses are blockers. If GapForge lacks evidence, the plan should say what evidence is needed or recommend a concession.

## Reviewer Simulation

Reviewer simulation should attack:

- novelty and closest prior work
- unsupported claims
- weak or missing citations
- missing baselines
- inappropriate metrics
- underpowered low-FPR claims
- failed or hidden experiments
- irreproducible results
- artifact evaluation gaps
- double-blind risks
- unclear writing and section organization

Simulated reviewers are diagnostic tools. They are not venue reviewers, acceptance predictors, or evidence that a submission will be accepted.

## Rebuttal Drafting Rules

Rebuttal text may:

- cite known paper IDs and validated BibTeX keys
- point to manuscript edits
- point to existing result artifacts
- summarize completed additional analyses
- concede limitations
- request more time or mark work out of scope when honest

Rebuttal text must not:

- invent citations
- invent new results
- claim an experiment was run without execution records
- hide negative or failed experiments
- promise camera-ready changes that are not planned or feasible
- claim reviewer agreement or venue acceptance

## Suggested Command Surface

```bash
gapforge manuscript-review --manuscript-id <manuscript-id>
gapforge manuscript-meta-review --manuscript-id <manuscript-id>
gapforge manuscript-fix-list --manuscript-id <manuscript-id>
gapforge rebuttal-plan --manuscript-id <manuscript-id>
gapforge revision-plan --manuscript-id <manuscript-id>
gapforge mark-rebuttal-item --item-id <item-id> --status addressed
gapforge revision-status --manuscript-id <manuscript-id>
```

## Rebuttal Gate

The rebuttal gate should fail if:

- a response cites unknown papers or unresolved BibTeX keys
- a response claims a result without artifact-backed evidence
- a response hides a failed or negative experiment
- a response answers a novelty objection without closest-prior-work evidence
- a response promises artifact availability when the package is incomplete
- major objections remain open without a visible concession or task

Passing the rebuttal gate means the response plan is evidence-backed. It does not mean reviewers will accept the paper.

## Implemented Reviewer Roles

The manuscript reviewer panel attacks:

- novelty and prior-work recall
- empirical result support and baseline comparison
- clarity and missing/unfinished sections
- related work and bibliography completeness
- reproducibility and artifact evaluation package state
- ethics/limitations and hidden blockers
- area-chair decision risk

`rebuttal-plan` converts reviewer objections into `RebuttalItem` and `RevisionPlan` records. Open or deferred items block camera-ready packages. A required new experiment becomes a task/request; a missing citation becomes a search/citation request; an overstrong claim becomes a softening item. If evidence is missing, the plan must ask for evidence or concede the limitation, not invent a response.
