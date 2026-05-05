# Example: Low False-Positive Collusion Detection

This example is a topic seed for exercising the GapForge v0.1 research loop.

## Topic

```text
low false positive collusion detection
```

## Offline Smoke Run

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --max-papers 12
gapforge report
```

## What To Inspect

- `field_map.md`: whether papers cluster around detection, calibration, graph methods, and evaluation.
- `gaps.md`: whether gaps link to paper IDs or clearly state indirect evidence.
- `novelty_gate.md`: whether duplicate benchmark ideas are rejected or marked weak.
- `experiments.md`: whether plans include baselines, metrics, and falsification conditions.
- `final_report.md`: the single recommended direction and its uncertainty.

## Caution

With `GAPFORGE_DISABLE_NETWORK=1`, source connectors may use deterministic fallback metadata. Do not treat the output as a real literature review until live searches and full-text notes are added.
