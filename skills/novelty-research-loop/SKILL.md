---
name: novelty-research-loop
description: Use when a GapForge campaign has unknown, weak, contested, or duplicate-prone novelty and needs iterative prior-work search.
---

# Novelty Research Loop

## Purpose
Prevent premature novelty claims by iterating closest-prior-work searches until a direction is rejected, revised, remains unknown, or becomes plausibly experiment-ready.

## When To Use
- After novelty dossier verdict is `unknown`, `weak`, or `contested`.
- When reviewer or human review flags likely duplicate prior work.
- Before experiment-ready direction maturity.

## Inputs
- Gaps/directions, novelty dossiers, missing searches, related-work matrix, source policy, retrieval index, citation graph, project memory, and search budget.

## Outputs
- Search requests, `SearchQueryRecord`s, refreshed retrieval index, refreshed novelty dossiers, updated direction maturity, stop reason.

## Artifacts
- `novelty_dossiers.json`
- `related_work_matrix.md`
- `search_queries.json`
- `source_coverage.md`
- campaign decisions and stop conditions

## Procedure
1. Inspect promising gaps/directions and current dossier.
2. Generate exact title, method, benchmark, dataset, author, survey, adjacent-field, and citation-neighborhood searches.
3. Execute or create structured search requests.
4. Record every query and source failure.
5. Rebuild retrieval.
6. Refresh novelty comparison.
7. Reject duplicates, downgrade weak novelty, or stop as not ready when coverage remains poor.

## Validation Checklist
- [ ] Missing searches are explicit.
- [ ] Every search is recorded.
- [ ] Closest prior work resolves to known paper IDs.
- [ ] Duplicate prior work rejects or downgrades the direction.
- [ ] Strong novelty is blocked when source policy is incomplete.

## Failure Modes
- Treating no search results as novelty.
- Softening duplicates into minor related work.
- Ignoring source policy requirements.
- Letting Codex invent search results.

## Examples
```bash
gapforge novelty-loop --campaign-id CAMPAIGN
gapforge novelty-loop --campaign-id CAMPAIGN --gap-id GAP
gapforge campaign-task --campaign-id CAMPAIGN --type novelty_reviewer
```

## Evidence Rules
Novelty conclusions must cite known papers, dossiers, retrieval candidates, or explicit missing searches. Unknown citations become search requests.
Do not invent citations, results, prior-work papers, search results, or evidence locators.

## Uncertainty Rules
Unknown coverage means unknown novelty. If a closest prior work may solve the gap, mark contested or reject.

## Reasoning Storage
Store concise public reasoning summaries only. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake-agent novelty tasks test validation only. Real Codex/GPT-5.4 novelty assistance is accepted only after validated import, attestation, and human review.
