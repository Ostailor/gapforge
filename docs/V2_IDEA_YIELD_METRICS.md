# GapForge v2 Idea Yield Metrics

v2 must measure idea search productivity. Yield metrics prevent high-volume brainstorming from being mistaken for research progress and make failure diagnosable when no idea is accepted.

## Core Metrics

Persisted v2 yield metrics include:

- `topic_variant_count`
- `candidate_count`
- `mutation_count`
- `constructive_gap_count`
- `cross_domain_transfer_count`
- `rejected_duplicate_count`
- `rejected_generic_count`
- `novelty_unknown_count`
- `tournament_survivor_count`
- `human_accepted_idea_count`
- `agenda_generated`
- `idea_yield_rate`
- `time_to_selected_idea`
- `evidence_per_candidate`
- `prior_work_per_candidate`

## Candidate Funnel

The funnel should report:

```text
seeded:
searched:
mutated:
transfer_expanded:
counterevidence_checked:
tournament_entered:
human_reviewed:
accepted:
rejected:
fallback_items:
```

A high drop-off is not automatically bad. It may show that evidence gates are working.

## Rejection Reasons

Standard rejection reason categories:

- `covered_by_prior_work`
- `insufficient_source_coverage`
- `weak_novelty`
- `too_generic`
- `infeasible_protocol`
- `missing_dataset`
- `missing_baseline`
- `metric_not_defensible`
- `underpowered_or_unmeasurable`
- `artifact_path_unclear`
- `human_rejected`
- `out_of_scope`
- `blocked_by_source_failure`

Release reports should include counts and examples for serious rejections.

## Yield Quality Measures

Recommended derived measures:

- accepted candidates per portfolio
- accepted candidates per Codex/GPT-5.4 synthesis task
- accepted candidates per tournament
- median mutations per accepted candidate
- rejection rate by reason
- percentage of candidates with closest-prior-work checks
- percentage of serious candidates with human review
- percentage of accepted candidates with unresolved high-risk blockers
- cost or time per accepted candidate, when available

These are diagnostics, not targets to game.

## Failure Metrics

When no candidate is accepted, the metrics report must still be complete. It should identify:

- whether search breadth was too low
- whether prior work invalidated the portfolio
- whether source coverage blocked the decision
- whether candidate quality was too generic
- whether human preferences rejected the candidate set
- whether implementation failed to run the discovery loop

The release gate should use this to route to v2.0.1 or v2.1.

## Reporting Rules

- Do not count speculative seeds as accepted candidates.
- Do not count tournament winners as accepted unless they pass the accepted-candidate standard.
- Do not count Codex/GPT-5.4 suggestions unless outputs were validated and imported.
- Do not hide rejected candidates to improve acceptance rate.
- Do not optimize for candidate volume over accepted-candidate quality.
- Report zero accepted ideas explicitly; do not turn agenda fallback into idea yield.
- Human preference can change rankings, but it cannot remove fake-citation, fake-result, novelty, evidence, or review blockers.

## Commands and API

```bash
gapforge idea-yield --project-id <project-id>
gapforge idea-yield --project-id <project-id> --write-report
```

```python
from gapforge import api

metrics = api.idea_yield(project_id, write_report=True)
```

The v2 release gate consumes the same metrics. For v2.0, at least one human-accepted candidate is the preferred passing condition. Agenda-only fallback can pass only with an explicit `--allow-agenda-only` warning path and release notes that say idea discovery did not produce an accepted idea.

## Minimal Metrics Report

Every v2 release candidate should include:

```text
Portfolio summary:
Search budget:
Candidate funnel:
Mutation and transfer summary:
Counterevidence summary:
Tournament summary:
Human feedback summary:
Accepted candidates:
Rejected candidates by reason:
Agenda fallback status:
Release-gate outcome:
Next release lane:
```
