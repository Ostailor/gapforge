---
name: openreview-review-dataset
description: Use when building or labeling v2.5 OpenReview-style datasets for reviewer calibration.
---

# OpenReview Review Dataset

## Purpose

Build public, auditable review-calibration datasets and taxonomy labels for harsher reviewer simulation.

## Command Path

```bash
gapforge review-dataset-create --name openreview_like
gapforge review-dataset-ingest-fixture
gapforge review-dataset-report --dataset-id <dataset-id>
gapforge review-labels-generate --dataset-id <dataset-id>
gapforge review-taxonomy-report --dataset-id <dataset-id>
gapforge reviewer-train --dataset-id <dataset-id> --mode heuristic
gapforge reviewer-evaluate --dataset-id <dataset-id>
gapforge reviewer-calibration-report --dataset-id <dataset-id>
```

## API Path

```python
from gapforge import api

dataset = api.create_review_dataset(ingest_fixture=True)
run = api.train_reviewer(dataset.id, mode="heuristic")
evaluation = api.evaluate_reviewer(dataset.id, model_id=run.id)
```

## Discipline Rules

- Use public review data only when source terms, venue policy, and privacy constraints allow it.
- Hash reviewer identifiers and store no hidden/private review data.
- Taxonomy labels are calibration signals, not ground truth unless human-verified.
- Reviewer training must penalize no fake citation violations, fake result references, and unsupported external facts.
- Evidence discipline applies: do not fabricate OpenReview records, fake reviews, or claims of acceptance prediction.
