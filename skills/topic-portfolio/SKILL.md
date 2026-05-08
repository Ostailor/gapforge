---
name: topic-portfolio
description: Use when a GapForge v2 task needs topic variants, adjacent topics, or portfolio inputs before idea generation.
---

# Topic Portfolio

## Purpose

Create diverse, auditable topic variants before generating ideas. v1 evaluates or refuses a given direction; v2 first explores around the root topic so refusal is not based on the first obvious framing.

## Required Inputs

- root topic or `project_id`
- prior refusals, rejected ideas, and human preferences when available
- source/search constraints and known exclusions

## Workflow

1. Generate narrower, broader, adjacent, cross-domain, metric-shift, threat-model-shift, benchmark-shift, theory-shift, evaluation-shift, and data-shift variants.
2. For each variant, record why it may produce a paper and why it may fail.
3. Add executable search queries that existing GapForge search/campaign code can run.
4. Do not claim novelty. A variant is only a search input.
5. Persist and report the portfolio.

## Commands

```bash
gapforge topic-portfolio "low false-positive collusion detection in LLM multi-agent systems"
gapforge topic-portfolio --project-id <project-id>
gapforge topic-portfolio-report --portfolio-id <portfolio-id>
```

Python:

```python
from gapforge import api

portfolio = api.generate_topic_portfolio(project_id=project_id)
```

## Checks

- Variants are not shallow synonyms.
- Prior refusals influence variants without forcing acceptance.
- Cross-domain topics name a plausible technical bridge.
- Output remains auditable and does not say any variant is novel or paper-ready.
