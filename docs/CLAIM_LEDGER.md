# Claim Ledger

GapForge treats claims as first-class research objects, not prose inside a summary.

The claim ledger exists to answer four questions:

- What does the system currently believe?
- Which paper or source caused that belief?
- What evidence supports or contradicts it?
- Which claims are still uncertain or need verification?

## Philosophy

Research ideation fails when unsupported assumptions quietly become conclusions. The ledger is intentionally conservative:

- New claims start as `unsupported`.
- A claim cannot be considered `supported` without supporting evidence.
- Counterevidence does not disappear; it is stored beside supporting evidence.
- Novelty claims remain high-risk unless closest prior work is recorded.
- Novelty gate verdicts are not proof of novelty; `unknown` means searches are missing, `revise` means the idea needs a decisive difference, and `reject` means closest prior work appears too similar.
- Uncertain claims are useful, but they must stay visibly uncertain.

The ledger stores concise public reasoning summaries only. It must not store hidden chain-of-thought. `reasoning_summary` should explain the auditable reason an object was created, such as "Grouped repeated calibration limitations into one measurable gap."

## Claim Fields

Each claim has:

- `id`
- `text`
- `type`: `background`, `method`, `novelty`, `gap`, `result`, `limitation`, or `analogy`
- `status`: `unsupported`, `supported`, `contested`, `uncertain`, or `falsified`
- `confidence`: `low`, `medium`, or `high`
- `supporting_evidence`
- `counter_evidence`
- `source_paper_ids`
- `created_by_skill`
- `needs_verification`
- `notes`
- `closest_prior_work` for novelty claims
- `provenance`

## Evidence

Evidence records include:

- `source_id`
- `source_paper_id`
- `quote`
- `locator`
- `confidence`
- `notes`

Evidence should be specific enough to audit later. For papers, `locator` should eventually become a section, page, paragraph, DOI, URL, or annotation anchor.

## Status Meaning

- `unsupported`: recorded but not yet backed by evidence
- `supported`: has supporting evidence and source papers
- `contested`: has meaningful counterevidence
- `uncertain`: plausible but still verification-sensitive
- `falsified`: evidence indicates the claim is false

## Markdown Export

`ClaimLedger.export_markdown()` emits a readable audit artifact with each claim, status, confidence, source papers, supporting evidence, counterevidence, and notes.
