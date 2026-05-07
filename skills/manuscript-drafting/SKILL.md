---
name: manuscript-drafting
description: Use when drafting or rendering GapForge v0.8 manuscript sections while preserving claim, citation, and result traceability.
---

# Manuscript Drafting

## Purpose
Draft section-level manuscript text that remains linked to known claims, papers, results, artifacts, and limitations.

## Inputs
- Manuscript state, section records, claim uses, bibliography, traceability report, related-work matrix, result artifacts, and limitations.

## Outputs
- `sections/*.md`
- rendered manuscript Markdown through CLI/API or submission package.

## Procedure
1. Create or update section stubs before writing prose.
2. For every nontrivial claim, add or verify a `ManuscriptClaimUse`.
3. Use known citation keys only.
4. Keep result language aligned to run type: smoke, pilot, main, failed, negative, reproduction.
5. Put known blockers in limitations, not hidden comments.
6. Run traceability and citation checks after drafting.

## Section Rules
- Abstract and introduction may summarize only supported or explicitly tentative claims.
- Related work requires known paper records.
- Results require artifact-backed values.
- Limitations must mention known blockers, failed runs, missing baselines, and scope limits.

## Validation Checklist
- [ ] Sections have status and source IDs.
- [ ] Claims are linked or labeled hypothesis/speculation.
- [ ] No unresolved citation keys.
- [ ] Failed/negative experiments are visible.

## Never Do
Do not write polished prose that masks missing evidence. Do not fabricate results, citations, or novelty.
