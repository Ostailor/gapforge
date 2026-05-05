---
name: manuscript-export
description: Use when exporting an honest manuscript starter kit, bibliography, evidence index, limitations, or rebuttal plan from a mature GapForge direction.
---

# Manuscript Export

## Purpose
Export a paper starter package from a mature direction without inventing results or hiding uncertainty.

## When To Use
- After direction reaches experiment-ready or manuscript-ready.
- When a researcher wants outlines, related work, protocol, evidence, and rebuttal planning.
- CLI: `gapforge export-paper-package --project-id PROJECT --direction-id DIRECTION`.

## Inputs
- research direction
- related-work matrix
- experiment protocol
- novelty dossier
- review panel and rebuttal plan
- claim ledger
- evidence spans
- paper metadata

## Outputs
- `PaperPackage`
- `paper_packages/<direction-id>/README.md`
- `abstract.md`
- `intro_outline.md`
- `related_work_matrix.md`
- `method_outline.md`
- `experiment_protocol.md`
- `expected_results.md`
- `limitations.md`
- `reviewer_objections.md`
- `review_panel.md`
- `rebuttal_plan.md`
- `bibliography.bib`
- `claim_ledger.md`
- `evidence_index.md`

## Required Artifacts
- mature direction
- related-work matrix
- experiment protocol
- novelty dossier
- claim ledger/evidence index

## Procedure
1. Check direction maturity and rejected status.
2. Refuse rejected directions unless explicitly allowed.
3. Gather related work, protocol, novelty, claims, evidence, reviewer objections, and bibliography metadata.
4. Write outlines and package files.
5. Label expected results as hypothetical.
6. Include limitations, missing searches, unsupported claims, and reviewer risks.
7. Produce best-effort BibTeX from known metadata only.

## Citation and Evidence Rules
- Related work must cite known paper IDs and available DOI/arXiv/URLs.
- Do not invent bibliography entries.
- Do not write fake results as real.
- Evidence index should expose locators and claim IDs.

## Uncertainty Rules
- Missing requirements must remain visible.
- Candidate directions should produce more warnings than manuscript-ready directions.
- Reviewer objections should not be softened without evidence.

## Validation Checklist
- [ ] All expected package files exist.
- [ ] Results are hypothetical unless actual experiment results are present.
- [ ] Bibliography uses known metadata only.
- [ ] Rejected direction is blocked unless allowed.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Polished prose that hides missing evidence.
- Fake results or fake citations.
- Exporting a weak direction as paper-ready.
- Omitting limitations or rebuttal risks.

## Examples
```bash
gapforge export-paper-package --project-id PROJECT --direction-id DIRECTION
gapforge export-bib --project-id PROJECT --direction-id DIRECTION
gapforge export-safe-bundle --project-id PROJECT
```
