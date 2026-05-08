# GapForge v2 Human Feedback

v2 uses human preference feedback to steer idea search. Feedback can guide which topics, constraints, and risk profiles matter, but it cannot override evidence gates.

## Feedback Types

Capture feedback as:

- `preference`: the human prefers a topic, method, audience, or risk profile
- `dispreference`: the human wants to avoid a topic, method, or framing
- `constraint`: a hard requirement such as data access, compute, venue, ethics, or timeline
- `critique`: a reason a candidate is weak, generic, infeasible, or already known
- `acceptance_review`: a decision that a candidate is worth continued research
- `refusal_review`: a decision that no candidate should be accepted
- `agenda_review`: feedback on the fallback agenda

## What Feedback May Do

Human feedback may:

- prioritize portfolios
- narrow or broaden scope
- reject uninteresting or infeasible candidates
- request more search
- choose among similarly defensible candidates
- define acceptable risk and cost
- approve accepted-candidate status after evidence review
- approve research agenda fallback

## What Feedback May Not Do

Human feedback may not:

- make an unsupported candidate accepted
- waive closest-prior-work review
- invent citations, results, datasets, baselines, or metrics
- hide counterevidence
- convert a speculative seed into a paper-ready claim
- remove correct refusal as an outcome
- bypass release-gate failure when no candidate is accepted

## Feedback Record

Each feedback record should include:

```text
Feedback ID:
Reviewer:
Role or expertise:
Portfolio ID:
Candidate IDs:
Feedback type:
Summary:
Evidence referenced:
Decision impact:
Follow-up required:
Timestamp:
```

## Preference-Aware Search

The active idea search controller should use preferences to choose next actions, for example:

- search more in a preferred subtopic
- mutate toward lower compute cost
- reject candidates outside the human's scope
- expand transfer search into a requested neighboring field
- stop when the candidate set is no longer useful

Preference-aware search must still record rejected alternatives and stop reasons.

## Review Points

Require human review at:

- portfolio definition
- tournament finalist selection
- accepted-candidate decision
- research agenda fallback
- v2 release gate

Human review should be preserved even when the decision is refusal.
