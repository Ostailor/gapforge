---
name: benchmark-adapter
description: Use when creating or running v2.5 adapters from vetted benchmarks into selected benchmark trace-like units.
---

# Benchmark Adapter

## Purpose

Create transparent adapters that let existing vetted benchmarks serve as bounded substrates, auxiliary checks, or sanity checks for the selected v2.5 protocol.

## Command Path

```bash
gapforge benchmark-adapter-create --selected-benchmark-id <benchmark-id> --vetted-benchmark-id <vetted-id>
gapforge benchmark-adapter-run --adapter-id <adapter-id>
gapforge benchmark-adapter-report --adapter-id <adapter-id>
gapforge selected-vetted-experiment-plan --benchmark-id <benchmark-id>
gapforge selected-vetted-experiment-run --plan-id <plan-id>
```

## API Path

```python
from gapforge import api

adapter = api.create_benchmark_adapter(selected_benchmark_id, vetted_benchmark_id)
run = api.run_benchmark_adapter(adapter.id)
plan_or_result = api.run_vetted_experiment(benchmark_id=selected_benchmark_id)
```

## Discipline Rules

- Preserve original labels, splits, and source metadata whenever possible.
- Record every transformation and every warning.
- Do not call adapted data real collusion traces unless the source truly contains collusion traces.
- Keep vetted-adapter results separated from synthetic benchmark results.
- Warn when conversion destroys task meaning or only supports auxiliary/sanity-check evidence.
- Evidence discipline applies: no fake citation, fake result, fake review, fake label, hidden adapter failure, or claim strengthening beyond the mapping report.
