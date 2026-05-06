# v0.5 Quality Gates

v0.5 quality gates evaluate whether live-literature campaigns are useful and honest research artifacts.

## Gate 1: Source Coverage

Pass criteria:

- Source policy profile selected and justified.
- Required/recommended sources attempted or unavailable with reason.
- Search queries recorded with purpose and result IDs.
- Source failures and rate limits visible.
- Full-text coverage reported separately from abstract-only coverage.

Fail criteria:

- Missing source families are hidden.
- Fallback/fixture papers are presented as live literature.
- Coverage confidence is high without enough source diversity.

## Gate 2: Closest Prior Work

Pass criteria:

- Novelty dossier lists closest prior work or marks novelty unknown.
- Candidate prior work includes retrieval, citation-neighborhood, exact method/benchmark, and survey/systematic-review searches where relevant.
- Top prior work resolves to known paper IDs or recorded search results.

Fail criteria:

- Strong novelty is claimed without prior work.
- Obvious prior work identified by human review is missing and unaddressed.
- Model-proposed citations are accepted without corpus resolution.

## Gate 3: Evidence Grounding

Pass criteria:

- Full-text-backed claims cite EvidenceSpan locators.
- Abstract-only evidence is labeled.
- Tables/references/captions are used cautiously and provenance is recorded.
- No result claim is high-confidence without evidence.

Fail criteria:

- Unsupported high-confidence claims.
- Fake quotes, fake paper IDs, fake DOI/arXiv IDs, or invented metrics.
- Model summaries treated as evidence.

## Gate 4: Gap Quality

Pass criteria:

- Gap has evidence matrix or explicit reason for absence.
- Supporting and countering papers are visible.
- Confidence reflects source coverage and evidence strength.
- Repeated limitations or benchmark/metric absences are grounded in real papers.

Fail criteria:

- Generic heuristic gap promoted as high confidence.
- Counterevidence ignored.
- Cross-domain analogy promoted without transferable mechanism evidence.

## Gate 5: Experiment Protocol

Pass criteria:

- Baselines, datasets, metrics, statistical notes, ablations, falsification criteria, and reproducibility checklist are present.
- Missing baselines or unavailable datasets are blockers.
- Expected results are labeled hypothetical.

Fail criteria:

- Experiment-ready status without protocol.
- Fake results or implied completed experiments.
- No baseline or metric definition.

## Gate 6: Human Expert Review

Pass criteria:

- Human review record exists.
- Reviewer scores source coverage, prior-work recall, evidence grounding, novelty honesty, gap quality, protocol quality, and uncertainty visibility.
- Required fixes are tracked.

Fail criteria:

- Review accepts campaign despite fake citations, unsupported high-confidence claims, or strict-report overclaim.
- Reviewer objections are ignored.

## Gate 7: Release Summary

Pass criteria:

- Release note lists accepted and rejected live campaigns.
- Workflow canaries are separated from live-literature campaigns.
- Known misses and remaining risks are documented.

Fail criteria:

- Fixture-only canaries counted as research quality.
- Release claims exhaustive review or proven novelty.

## Gate 8: Workflow vs Research Quality

Pass criteria:

- Campaign record distinguishes `accepted_for_workflow` from `accepted_for_research_quality`.
- Workflow canaries, fake-agent runs, dry runs, and fixture evals are listed separately from live-literature campaigns.
- Human quality review explicitly scores source quality, paper relevance, prior-work recall, evidence grounding, novelty honesty, gap importance, experiment feasibility, reviewer objection quality, and report honesty.

Fail criteria:

- A workflow-accepted campaign is described as research-quality accepted without quality review.
- A task-pack or dry-run artifact is counted as live source evidence.
- A campaign passes despite fake citations, missed obvious prior work, unsupported high-confidence claims, or overclaimed novelty.

## Gate 9: v5 Release Gate

Run:

```bash
gapforge v5-release-gate --project-id <project-id> --write-report --json
```

The gate must fail closed unless accepted campaigns include live source diagnostics, search strategy/rounds, source coverage, canonicalized papers, retrieval index, prior-work recall assessment, novelty dossier or refusal reason, related-work matrix, human research-quality review, and explicit stop reason.
