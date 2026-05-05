---
name: cross-domain-analogy
description: Use when searching adjacent fields for skeptical analogies, transferable concepts, and new source-search queries for candidate research gaps.
---

# Cross-Domain Analogy

## Purpose
Generate skeptical cross-domain analogies that may suggest useful concepts, search queries, or hypothesis seeds. Analogies are not evidence; they are prompts for further search and testing.

## When To Use
- Use after gap mining.
- Use when a gap may benefit from adjacent fields such as medicine, cybersecurity, economics, control theory, statistics, information theory, or epidemiology.
- CLI: `gapforge analogies --run-id RUN_ID`.

## Inputs
- `ResearchTopic`
- `Gap` records
- `FieldMap`
- `PaperNote` records

## Outputs
- `CrossDomainAnalogy` records
- `cross_domain_analogies.json`
- `cross_domain_analogies.md`
- optional hypothesis seeds
- adjacent-field search queries for source connectors

## Required Artifacts
- `gaps.json`
- `field_map.json`
- `cross_domain_analogies.json`
- `cross_domain_analogies.md`

## Procedure
1. Read gap titles, descriptions, risks, and minimum experiments.
2. Match the core constraint to adjacent fields, not surface vocabulary alone.
3. For each analogy, record:
   - source field
   - source concept
   - target gap ID
   - why it maps
   - what breaks in the mapping
   - technical transfer candidate
   - papers or sources to search
   - possible experiment
   - risk of fake analogy
4. Generate search queries for adjacent-field papers.
5. Do not claim the analogy is valid until evidence is found.
6. Store concise public reasoning summaries only.

## Quality Bar
- Every analogy must include "what breaks in the mapping".
- Every analogy must include fake-analogy risk.
- No analogy may be used as proof of novelty or feasibility.
- Search queries must be concrete enough for source connectors.
- Prefer fewer skeptical analogies over many shallow analogies.

## Failure Modes
- Shallow metaphor matching.
- Assuming transfer works without evidence.
- Ignoring domain-specific constraints that break the analogy.
- Creating hypotheses without linked gap IDs.

## Validation Checklist
- [ ] `cross_domain_analogies.json` and `.md` exist.
- [ ] Each analogy links a target gap ID.
- [ ] Each analogy states why it maps and what breaks.
- [ ] Each analogy lists adjacent-field search queries.
- [ ] No citation or result is invented.
- [ ] Confidence is low or medium unless evidence supports more.

## Examples
Generate analogies for a run:

```bash
gapforge analogies --run-id 20260505T002206Z-low-false-positive-collusion-detection
```
