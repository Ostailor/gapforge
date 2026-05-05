# Testing

GapForge tests are designed to run offline. Live source APIs, PDF downloads, and LLM calls must not be required for CI.

## Local Commands

Install development dependencies:

```bash
make install
```

Run formatting, linting, type checking, tests, and offline evals:

```bash
make ci
```

Run individual checks:

```bash
make format-check
make lint
make typecheck
make test
make eval
make coverage
```

Run a v0.2 offline smoke workflow:

```bash
make v2-smoke
```

## Network Discipline

Tests and evals should set or inherit:

```bash
GAPFORGE_DISABLE_NETWORK=1
```

Use mocked HTTP clients or fixture sources for source connectors, PDF downloads, related-work expansion, and novelty search behavior.

## Fixture Policy

Fixtures under `tests/fixtures/` are synthetic but realistic. They are intended to exercise behavior, not to claim real literature conclusions.

When adding fixtures:

- Include enough metadata to test ranking, coverage, novelty, and evidence behavior.
- Include negative cases such as unsupported claims and duplicate ideas.
- Add full-text sections and evidence spans for v0.2 fixtures when the behavior depends on grounding.
- Keep fixture content deterministic and small.

## Coverage

`make coverage` uses `pytest-cov` and reports terminal coverage for `gapforge`. Coverage is a diagnostic signal, not the only acceptance criterion; evidence discipline and offline determinism matter more than raw percentage.
