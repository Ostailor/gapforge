---
name: deep-reading
description: Use when producing source-grounded structured notes that distinguish paper claims, demonstrated evidence, assumptions, limitations, and topic connections.
---

# Deep Reading

## Purpose
Produce structured paper notes that separate what a paper claims from what it demonstrates. This skill protects GapForge from hallucinated results and unsupported literature claims.

## When To Use
- Use after paper triage for Tier 1 and Tier 2 papers.
- Use when a specific paper needs grounded extraction.
- CLI: `gapforge read --run-id RUN_ID --tier 1` or `gapforge read --paper-id PAPER_ID`.

## Inputs
- selected `Paper` records
- optional full text
- `PaperTriageDecision` records
- research topic

## Outputs
- `PaperNote` records
- `paper_notes.json`
- `paper_notes.md`
- evidence-backed claim ledger entries

## Required Artifacts
- `paper_notes.json`
- `paper_notes.md`
- source-linked evidence snippets for supported claims

## Procedure
1. Identify whether the note is based on full text or metadata/abstract only.
2. Extract only what is present in the available source text.
3. Separate:
   - core claims
   - method
   - datasets
   - metrics
   - main results
   - assumptions
   - stated limitations
   - unstated limitations
   - what the paper cannot answer
   - useful technical tools
   - possible connections to the topic
4. Add quotes or evidence snippets with source IDs and locators.
5. Add claim ledger entries only for source-grounded claims.
6. Mark abstract-only notes as low or medium confidence, not high.
7. Store concise public reasoning summaries only; do not store hidden chain-of-thought.

## Quality Bar
- Do not fabricate main results when no result statement exists.
- Do not infer datasets, metrics, or equations from title alone.
- Abstract-only notes must clearly say `metadata/abstract only`.
- Every supported claim must have evidence and paper ID.
- Speculation belongs in limitations or possible connections, not main results.

## Failure Modes
- Turning an abstract claim into a demonstrated result.
- Treating future-work language as an achieved contribution.
- Dropping locators, making later audit impossible.
- Mixing unstated limitations with author-stated limitations.

## Validation Checklist
- [ ] Each note has `paper_id`.
- [ ] Source basis is explicit: full text or metadata/abstract only.
- [ ] Main results appear only when supported by source text.
- [ ] Evidence snippets have source IDs and locators.
- [ ] Confidence is not high for abstract-only notes.
- [ ] Claim ledger entries are source-linked.

## Examples
Read all Tier 1 papers:

```bash
gapforge read --run-id 20260505T002206Z-low-false-positive-collusion-detection --tier 1
```

Read one paper:

```bash
gapforge read --paper-id arxiv-low-false-positive-collusion-detection-1
```
