---
name: real-benchmark-search
description: Use when searching public benchmark candidates, assessing v2.6 adapter fit, running real benchmark attempts, or writing no-fit evidence.
---

# Real Benchmark Search

## Purpose

Attempt public benchmark grounding for the selected benchmark while preserving no-fit as an honest outcome.

## Command Path

```bash
gapforge selected-real-benchmark-search --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-candidates --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-adapter-assess --benchmark-id <benchmark-id> --candidate-id <candidate-id>
gapforge selected-real-benchmark-experiment-run --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-experiment-report --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

search = api.search_real_benchmark_candidates(benchmark_id)
assessment = api.assess_real_benchmark_adapter(benchmark_id, candidate_id)
attempts = api.run_real_benchmark_experiment(benchmark_id)
```

## Discipline Rules

- Do not download large datasets automatically.
- Preserve source URL, license, access, and terms.
- A candidate is not fit until mapping assessment passes.
- Label auxiliary and sanity-check evidence exactly; do not promote it to primary support.
- If no public benchmark fits, write a no-fit report and narrow manuscript claims.
- Do not invent evidence, fake benchmark results, or real-collusion validity claims.
