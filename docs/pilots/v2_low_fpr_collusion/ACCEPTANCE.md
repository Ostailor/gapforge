# v2 Low-FPR Collusion Pilot Acceptance

The pilot passes only if v2 actually attempts idea discovery before accepting an outcome.

## Required Artifacts

- `topic_portfolio`
- `idea_bank`
- `mutation_report`
- `constructive_gap_report`
- `cross_domain_transfer_report`
- `codex_idea_synthesis_tasks`
- `novelty_report`
- `idea_tournament_report`
- human review acceptance

## Candidate-Idea Pass

A selected idea passes only when all are true:

- active search artifacts exist
- tournament ran and selected the idea
- idea title is specific, not generic
- idea has no fake or unresolved citation IDs
- idea does not claim results before experiments
- idea has visible evidence and novelty gate state
- human feedback accepts it as a candidate, not as paper-ready

## Agenda Fallback Pass

A research agenda passes only when all are true:

- active search artifacts exist
- mutation ran
- tournament ran and selected no viable idea
- agenda exists and explains blockers
- human review accepts the agenda as an honest blocker

An accepted agenda does not mean v2 achieved idea discovery. It means the release must document blockers and plan v2.0.1 or v2.1 unless another run produces an accepted candidate.

## Required Failures

The pilot must fail for:

- early refusal without active idea search
- generic selected idea
- fake citation or unresolved paper IDs
- fake result claims
- missing human review
