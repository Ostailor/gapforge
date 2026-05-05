---
name: related-work-matrix
description: Use when classifying prior work around a research direction as directly solving, partially solving, baseline, survey, foundation, or adjacent.
---

# Related-Work Matrix

## Purpose
Convert a list of prior papers into a structured matrix that shows what each paper contributes, what it does not solve, and whether it must be cited or used as a baseline.

## When To Use
- After novelty dossiers.
- Before experiment protocols, reviewer panels, or manuscript export.
- CLI: `gapforge related-work-matrix --project-id PROJECT --direction-id DIRECTION`.

## Inputs
- research direction or run gap
- papers and notes
- novelty dossiers
- citation graph
- retrieval results
- paper roles

## Outputs
- `RelatedWorkEntry`
- `RelatedWorkMatrix`
- `related_work_matrix.json`
- `related_work_matrix.md`
- must-read and baseline paper IDs

## Required Artifacts
- `research_directions.json` or `gaps.json`
- `novelty_dossiers.json`
- `related_work_matrix.json`
- `related_work_matrix.md`

## Procedure
1. Collect candidate papers from retrieval, citation graph, novelty dossiers, paper roles, and project corpus.
2. Classify relationship: directly solves, partially solves, adjacent method, benchmark/dataset provider, theoretical foundation, negative result, survey/background, cross-domain analogy, baseline to include.
3. Record what each paper contributes and what it does not solve.
4. Mark must-cite, baseline candidates, and reviewer risk if omitted.
5. Downgrade or block directions when prior work directly solves the target.
6. Write matrix artifacts.

## Citation and Evidence Rules
- Entries require paper IDs.
- Use evidence span IDs when relationship depends on full text.
- Do not invent relationships, citations, or benchmark results.

## Uncertainty Rules
- Abstract-only relationship classifications are provisional.
- Missing categories should trigger next-search recommendations.
- Directly-solving papers require careful verification before rejecting a direction.

## Validation Checklist
- [ ] Matrix has entries or explicit missing-coverage reason.
- [ ] Must-cite and baseline IDs are visible.
- [ ] Directly solving prior work downgrades/blocks direction.
- [ ] Reviewer omission risk is stated.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Related work as a flat list.
- Missing baseline papers.
- Treating surveys as evidence of direct solution.
- Omitting closest prior work.

## Examples
```bash
gapforge related-work-matrix --project-id PROJECT --direction-id DIRECTION
gapforge must-read --project-id PROJECT --direction-id DIRECTION
```
