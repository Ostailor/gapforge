---
name: honest-null-distribution
description: Use when generating or reviewing v2.2 selected benchmark honest/null traces, benign coordination, or hard negatives.
---

# Honest Null Distribution

## Purpose

Stress pilot specificity against realistic-looking honest behavior without relabeling hard negatives as collusion.

## Required Coverage

- independent honest behavior
- benign parallel strategy
- shared context
- role specialization
- repeated conventions
- tool-induced similarity
- accidental correlation
- action-only and transcript-visible hard negatives

## Command Path

```bash
gapforge honest-null-scenarios --benchmark-id <benchmark-id>
gapforge generate-honest-null --benchmark-id <benchmark-id> --count 300
gapforge honest-null-report --benchmark-id <benchmark-id>
```

## Result Discipline

- Label synthetic provenance.
- Keep hard negatives in the negative class.
- Warn when hard-negative count or scenario coverage is thin.
- Do not claim the null distribution covers all benign multi-agent behavior.
