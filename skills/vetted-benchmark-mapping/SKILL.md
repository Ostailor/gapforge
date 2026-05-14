---
name: vetted-benchmark-mapping
description: Use when mapping v2.5 selected benchmarks to existing vetted benchmarks or recording a no-fit decision.
---

# Vetted Benchmark Mapping

## Purpose

Map the selected v2.5 benchmark idea to existing benchmark artifacts without pretending an unrelated dataset validates the new protocol.

## Command Path

```bash
gapforge vetted-benchmark-list
gapforge vetted-benchmark-register --name "<benchmark>" --license "<license>" --terms-of-use "<terms>"
gapforge vetted-benchmark-eligibility --benchmark-id <vetted-id> --idea-id <idea-id>
gapforge selected-vetted-benchmark-map --benchmark-id <benchmark-id>
gapforge selected-vetted-benchmark-report --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

record = api.register_vetted_benchmark("Benchmark Name", license="...", terms_of_use="...")
fit = api.assess_benchmark_fit(record.id, selected_idea_id)
mapping = api.map_selected_benchmark_to_vetted(benchmark_id, vetted_benchmark_id=record.id)
```

## Discipline Rules

- Vetted status is not fit; assess fit before making claims.
- License, terms, download requirements, and authentication requirements must be visible.
- Mapping type must be direct, substrate, auxiliary, analogy, sanity-check, or rejected.
- Unsupported claims must be listed and fed into manuscript limitations.
- If no benchmark fits, preserve the synthetic benchmark as the protocol contribution and record a no-fit justification.
- Evidence discipline applies: no fake citation, fake result, fake review, hidden no-fit decision, or deployment-validity claim is allowed.
