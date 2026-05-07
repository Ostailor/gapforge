---
name: bibliography-manager
description: Use when building, exporting, or auditing GapForge v0.8 manuscript bibliographies and citation keys.
---

# Bibliography Manager

## Purpose
Keep manuscript citations reproducible, tied to known `Paper` records, and free of invented references.

## Inputs
- Manuscript state, section source paper IDs, claim citation keys, project runs, project corpus paper records.

## Outputs
- `bibliography/bibliography.json`
- `bibliography/references.bib`
- citation audit output from `citation-check`.

## Procedure
1. Build with `gapforge bibliography-build --manuscript-id MANUSCRIPT`.
2. Export BibTeX with `gapforge bibliography-export --manuscript-id MANUSCRIPT --format bibtex`.
3. Check citations with `gapforge citation-check --manuscript-id MANUSCRIPT`.
4. Resolve missing metadata by adding real known paper metadata, not placeholder DOI/arXiv/venue values.
5. Treat unresolved or fake-looking keys as blockers for submission readiness.

## Citation Rules
- Citations must point to known `Paper` records.
- Stable citation keys are generated from known metadata.
- Deduplicate by DOI, arXiv ID, or normalized title.
- Missing DOI, venue, or authors is a warning, not permission to invent.

## Validation Checklist
- [ ] Every citation key resolves.
- [ ] Fake citation strings are rejected.
- [ ] Missing metadata is visible.
- [ ] BibTeX is auditable and reproducible.

## Never Do
Do not fabricate citations, BibTeX, DOI, arXiv ID, venue, authors, or publication year.
