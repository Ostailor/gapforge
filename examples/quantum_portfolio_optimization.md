# Example: Quantum Portfolio Optimization

This example is a topic seed for testing GapForge on a domain where novelty claims are especially risky because closely related prior work is common.

## Topic

```text
quantum portfolio optimization
```

## Suggested Run

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "quantum portfolio optimization" --max-papers 12
gapforge report
```

## What To Inspect

- `novelty_gate.md`: closest-prior-work comparisons should dominate the recommendation.
- `rejected_ideas.json`: intentionally duplicate or weakly differentiated ideas should be rejected.
- `experiments.md`: experiments should name classical baselines, metrics, and falsification conditions.
- `reviewer_simulation.md`: missing baselines or unsupported novelty should be blocking issues.

## Caution

Do not present offline fixture or fallback results as evidence about the real quantum optimization literature. This example is for validating GapForge behavior.
