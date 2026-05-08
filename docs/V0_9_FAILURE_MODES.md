# GapForge v0.9 Failure Modes

v0.9 should make failure useful. A failed pilot is acceptable only when the failure is recorded honestly and does not become a false success claim.

## Failure Categories

### Research Direction Failure

The pilot cannot recommend a direction because:

- closest prior work already covers the idea
- source coverage is too weak
- novelty is unclear after required searches
- the protocol lacks a valid dataset, baseline, or metric
- low-FPR claims would be underpowered or misleading
- human review rejects the research direction

Expected outcome: evidence-backed refusal. This can still pass v0.9 if the refusal artifacts are complete.

### Source and Literature Failure

Live source work is blocked by:

- source outage or rate limit
- unavailable full text
- incomplete metadata
- failed canonicalization
- missing key venues or source families
- manual search discovering missed prior work that invalidates coverage

Expected outcome: `needs_more_search`, `blocked`, or refusal. Do not claim novelty.

### Experiment and Benchmark Failure

Execution is blocked or inconclusive because:

- no valid dataset or scenario source exists
- baseline implementation is missing
- metric definition is unsuitable for low false-positive claims
- run fails or produces invalid artifacts
- sample size is too small for the claim
- result artifacts cannot be reproduced

Expected outcome: failed, negative, underpowered, or blocked status remains visible. Do not fabricate results or convert fixture smoke into empirical success.

### Manuscript and Artifact Failure

The paper package is not ready because:

- unsupported manuscript claims remain
- citations or BibTeX keys are unresolved
- artifact package is incomplete
- blinding leaks remain
- figures/tables are not artifact-backed
- reviewer objections are open

Expected outcome: manuscript-ready with blockers or submission not ready. Do not claim submission-ready or camera-ready status.

### Product and Workflow Failure

External pilot use is blocked by:

- command path is confusing or broken
- gate failure output lacks next steps
- docs confuse fixture evidence with real evidence
- migration breaks v0.8 state
- artifact hygiene is unsafe
- external reviewer cannot inspect the package

Expected outcome: release blocker, v0.9.1 candidate, or v1 not ready.

## v0.9.1 Criteria

Create v0.9.1 when all of the following are true:

- the v0.9 scope remains correct
- the external pilot exposed a narrow fixable defect
- the defect blocks credible external pilot use or v1 readiness
- the fix does not weaken any evidence gate
- the fix can be verified with targeted tests, docs, or pilot rerun evidence

Typical v0.9.1 fixes:

- repair a broken pilot command or option
- clarify release-gate diagnostics
- add missing migration handling for v0.8 artifacts
- correct docs that imply fixture-only success is empirical success
- improve artifact hygiene filters
- add missing external feedback or refusal record templates

Not valid v0.9.1 fixes:

- lowering novelty, source coverage, empirical, citation, artifact, or human-review gates
- reclassifying a refusal as success without new evidence
- deleting failed runs or blockers from reports
- claiming v1 readiness while known blockers remain

## Failure Reporting Template

Each failure report should record:

```text
Failure ID:
Category:
Detected by:
Affected pilot phase:
Evidence:
Blocked claim:
Current status:
Required fix:
Can v0.9 still pass with refusal:
Requires v0.9.1:
Requires later release:
Reviewer decision:
```

## Refusal Is Not Failure

An evidence-backed refusal is a valid v0.9 outcome when it prevents overclaiming. It becomes a failure only when the refusal lacks evidence, skips required review, hides missing work, or leaves the user without actionable next steps.

## v1 Readiness Impact

Every v0.9 failure must be classified against v1 readiness:

- `no_impact`: recorded limitation, no release blocker
- `scope_limit`: v1 can proceed only with narrower claims
- `patch_required`: v0.9.1 needed before v1
- `major_blocker`: v1 requires a later release

The v1 readiness report must include all `scope_limit`, `patch_required`, and `major_blocker` items.
