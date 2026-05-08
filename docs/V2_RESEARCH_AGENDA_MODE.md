# GapForge v2 Research Agenda Mode

Research agenda mode is the honest fallback when v2 tries hard to find a defensible idea and no candidate passes.

It is not a consolation prize, a hidden success state, or a way to bypass the accepted-candidate gate. It is a structured refusal plus next-search plan.

## When To Enter Agenda Mode

Enter research agenda mode when:

- no candidate passes the accepted-candidate standard
- the search budget is exhausted
- source coverage is too weak for acceptance
- closest prior work invalidates the strongest candidates
- human review rejects the candidate set
- feasibility or artifact requirements cannot be met
- the active controller determines that more mutation would be low-value without new evidence

## Agenda Contents

An agenda should include:

- portfolio scope and search budget
- best rejected candidates
- rejection reasons and counterevidence
- promising mutations that still need evidence
- cross-domain transfer routes worth revisiting
- missing sources, datasets, baselines, metrics, or expertise
- human feedback summary
- evidence that would reopen the search
- recommended next release lane

Persisted `ResearchAgenda` objects contain `blocker_summary`, concrete `agenda_steps`, expected artifacts, decision points, stop conditions, estimated effort, and provenance. Each `AgendaStep` must name a step type, required artifact, success criteria, and next decision.

## Agenda Item Statuses

Use:

- `needs_more_search`
- `needs_expert_review`
- `needs_dataset_access`
- `needs_benchmark_design`
- `needs_metric_definition`
- `needs_transfer_validation`
- `parked`
- `do_not_pursue`

Do not label agenda items as accepted, manuscript-ready, or paper-ready.

## Release Impact

Agenda mode means no idea candidate was accepted. For v2 release gating:

- if agenda mode was triggered by an implementation defect, plan v2.0.1
- if agenda mode was triggered by broader discovery strategy limits, plan v2.1
- if agenda mode was triggered by the domain genuinely lacking a defensible candidate under current evidence, record the refusal and plan a new portfolio or later v2.1 scope

The release notes must not say v2 idea discovery passed when agenda mode is the final output.

For v2.0, agenda-only release is a warning path, not the preferred success path. `gapforge v2-release-gate --allow-agenda-only` may pass only when the release notes explicitly say `idea_discovery_incomplete` and route follow-up work to v2.0.1 or v2.1.

## Agenda Template

```text
Agenda ID:
Portfolio ID:
Reason no candidate was accepted:
Search budget used:
Candidate summary:
Top rejected candidates:
Counterevidence:
Human feedback:
Missing evidence:
Recommended next searches:
Recommended mutations:
Recommended transfer domains:
Next release lane:
Reviewer:
```

## Human Review

A human reviewer should confirm that agenda mode is appropriate and that GapForge is not abandoning a defensible candidate too early. Human review may request more search, but it cannot force acceptance without evidence.

## Commands and API

```bash
gapforge research-agenda --project-id <project-id>
gapforge agenda-report --agenda-id <agenda-id>
gapforge agenda-to-campaigns --agenda-id <agenda-id>
```

```python
from gapforge import api

agenda = api.generate_research_agenda(project_id, blocker_summary="No candidate survived active search.")
```

Agenda mode is still a form of refusal. It becomes useful because it preserves blockers and creates future campaign inputs; it does not create a paper idea by itself.
