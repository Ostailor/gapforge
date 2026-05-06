---
name: prior-work-recall-gate
description: Use when deciding whether a GapForge v0.5 gap or direction has enough closest-prior-work search to support novelty or must remain unknown/rejected.
---

# Prior Work Recall Gate

## Purpose
Block premature novelty claims by checking whether required prior-work search rounds ran and whether close candidates already solve the proposed gap.

## Inputs
- Gap or direction ID, attached runs, search rounds, source profile, papers, notes, sections, novelty dossiers, related-work matrix, citation graph.

## Outputs
- `PriorWorkRecallAssessment`
- `prior_work_recall.md`
- downgraded novelty dossiers or rejected/revised directions when needed

## Required Artifacts
- run `prior_work_recall_assessments`
- `prior_work_recall.md`
- `novelty_dossiers.md`
- `search_rounds.md`

## Procedure
1. Identify required rounds from the source profile.
2. Check exact phrase, method/metric, benchmark/dataset, survey, citation-neighborhood, adjacent-field, and counterevidence searches as applicable.
3. Compare candidate prior work against problem, method, evaluation, and minimum experiment.
4. If required rounds are missing, cap novelty at unknown/weak.
5. If prior work likely solves the gap, reject or revise the direction.
6. Write blocking issues into reports.

## Evidence/Citation Rules
- Top prior work must resolve to known paper IDs or recorded search outputs.
- Claims about prior work need paper IDs and EvidenceSpan locators when available.
- Do not invent citations, prior-work IDs, DOI/arXiv IDs, results, or comparison table entries.

## Source Coverage Rules
- Missing required searches block strong novelty.
- Adjacent-field claims require adjacent-field search.
- Citation-neighborhood search is required when citation graph data exists.

## Failure Modes
- Treating incomplete search as novelty.
- Ignoring a close paper because it uses different terminology.
- Softening duplicates into “related work” without rejection/revision.
- Allowing model-proposed citations into state.

## Validation Checklist
- [ ] Required and completed rounds are visible.
- [ ] Missing searches are listed.
- [ ] Top prior work IDs resolve.
- [ ] Likely duplicates reject or downgrade.
- [ ] Final report shows recall gate status.

## Examples
```bash
gapforge prior-work-recall --run-id <run-id> --gap-id <gap-id>
gapforge prior-work-recall --campaign-id <campaign-id>
gapforge prior-work-recall-report --campaign-id <campaign-id>
```

## Uncertainty Rules
Unknown prior-work recall means unknown novelty. Never upgrade to strong novelty under poor or incomplete coverage.

## Reasoning Storage
Store public comparison summaries and blockers only. Do not store hidden chain-of-thought.
