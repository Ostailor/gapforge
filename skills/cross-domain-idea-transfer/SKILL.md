---
name: cross-domain-idea-transfer
description: Use when a GapForge v2 task explores analogies or transfers from neighboring technical fields.
---

# Cross-Domain Idea Transfer

## Purpose

Generate idea diversity from other fields only when there is a plausible technical transfer mechanism. Shallow analogy is rejected or kept as a search request.

## Source Fields

- medicine screening and specificity
- industrial anomaly detection
- fraud detection
- cartel detection economics
- covert channels and steganography
- sequential hypothesis testing
- statistical process control
- safety-critical monitoring
- reliability engineering

## Workflow

1. State the source field, source concept, and target problem.
2. Explain the transfer mechanism, not just similarity.
3. State required adaptation and what breaks.
4. Attach supporting source papers when known.
5. Without supporting evidence, keep the transfer as a search request.
6. Promote to `IdeaCandidate` only after evidence exists.

## Commands

```bash
gapforge transfer-ideas --project-id <project-id>
gapforge transfer-ideas --topic "low false-positive collusion detection"
gapforge transfer-report --project-id <project-id>
```

Python:

```python
from gapforge import api

transfers = api.transfer_ideas(project_id=project_id)
```

## Never Do

- Claim novelty from analogy.
- Promote unsupported transfers.
- Hide what breaks during adaptation.
- Use cross-domain transfer to bypass closest-prior-work review.
