---
name: cross-domain-analogy
description: Use when searching adjacent fields for skeptical transfer candidates, analogy queries, or mechanisms relevant to candidate gaps.
---

# Cross-Domain Analogy

## Purpose
Find adjacent-field concepts that might transfer into a target gap, while explicitly testing what breaks. Analogies are hypotheses for search, not conclusions.

## When To Use
- After gap mining.
- When a gap may benefit from medicine, cybersecurity, economics, game theory, control theory, statistics, information theory, physics, biology, or software provenance.
- CLI: `gapforge analogies --run-id RUN_ID --search --promote-evidence-only`.

## Inputs
- topic
- gaps
- field map
- paper notes/sections/evidence
- source coverage
- optional adjacent-field papers and retrieval index

## Outputs
- `CrossDomainAnalogy`
- `CrossDomainTransferCandidate`
- `cross_domain_analogies.json`
- `cross_domain_analogies.md`
- `cross_domain_transfers.json`
- `cross_domain_transfers.md`
- adjacent-field search queries

## Required Artifacts
- `gaps.json`
- `cross_domain_analogies.json`
- `cross_domain_analogies.md`
- `cross_domain_transfers.json` when candidates are promoted

## Procedure
1. Map the target gap constraint to adjacent-field patterns.
2. Generate query-only analogies with explicit "what breaks."
3. Search adjacent fields when allowed.
4. Triage/read adjacent-field papers when available.
5. Promote transfer candidates only when a source paper supports a technical mechanism.
6. Reject or leave query-only analogies when evidence is absent.
7. Never present query-only analogies as conclusions.

## Citation and Evidence Rules
- Promoted transfer candidates require source paper IDs.
- Use EvidenceSpan locators when available.
- Do not fabricate adjacent-field papers or mechanisms.
- Analogy evidence does not prove novelty.

## Uncertainty Rules
- Default confidence is low.
- Evidence-backed transfer can be medium.
- High confidence requires strong source evidence and target-domain validation.

## Validation Checklist
- [ ] Every analogy has target gap ID.
- [ ] Every analogy states why it maps and what breaks.
- [ ] Query-only, evidence-found, promoted, and rejected statuses are separated.
- [ ] Promoted candidates cite source papers/evidence.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Shallow metaphor matching.
- Treating analogy as proof.
- Ignoring domain constraints.
- Inventing adjacent-field citations.

## Examples
```bash
gapforge analogies --run-id RUN_ID
gapforge analogies --run-id RUN_ID --search --promote-evidence-only
```
