---
name: idea-mutation
description: Use when a GapForge v2 idea is weak, rejected, too broad, or blocked by reviewer/prior-work objections.
---

# Idea Mutation

## Purpose

Transform weak or rejected ideas into new seeds without erasing why the source failed. Mutation is recovery by reframing, not proof of novelty.

## Strategies

- `metric_shift`
- `observable_shift`
- `threat_model_shift`
- `benchmark_shift`
- `dataset_shift`
- `baseline_shift`
- `guarantee_shift`
- `domain_transfer`
- `contribution_type_shift`
- `positive_to_negative_result`
- `method_to_measurement`
- `method_to_benchmark`
- `empirical_to_theory`
- `broad_to_minimum_publishable_unit`
- `reviewer_objection_to_new_idea`

## Workflow

1. Load the source idea and rejection or risk reason.
2. Choose a strategy that changes a decisive dimension.
3. Create a new `seed`, not an accepted candidate.
4. Preserve inherited novelty/evidence/reviewer risks.
5. Record what changed, why it may help, and required new searches.
6. If fatal prior work blocked the source, ensure the mutation changes the overlapping contribution, setting, metric, dataset, or claim.

## Commands

```bash
gapforge mutate-idea --idea-id <idea-id>
gapforge mutate-idea --idea-id <idea-id> --strategy metric_shift
gapforge mutate-rejected-ideas --project-id <project-id>
gapforge mutation-report --project-id <project-id>
```

Python:

```python
from gapforge import api

mutation = api.mutate_idea(idea_id, strategy="method_to_benchmark")
```

## Never Do

- Claim the mutation is novel.
- Drop inherited risks.
- Hide the parent idea or rejection reason.
- Use mutation to force a generic idea through the gates.
