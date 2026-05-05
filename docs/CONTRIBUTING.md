# Contributing

GapForge is an evidence-first research ideation system. Contributions should preserve the project’s core discipline: no fabricated citations, no hidden reasoning traces in persisted artifacts, and clear uncertainty when coverage is weak.

## Setup

Use Python 3.11 or newer:

```bash
python -m venv .venv
. .venv/bin/activate
make install
```

Install pre-commit hooks if you want local checks before each commit:

```bash
pre-commit install
```

## Development Workflow

Keep changes small and testable. Prefer extending existing models, state managers, and skill interfaces over adding parallel paths.

Before opening a pull request, run:

```bash
make ci
```

For v0.2 workflow changes, also run:

```bash
make v2-smoke
```

Both commands run with `GAPFORGE_DISABLE_NETWORK=1` where network access is not required, so CI and local verification do not depend on live APIs.

## Evidence Rules

- Do not invent papers, results, datasets, metrics, quotes, or citation metadata.
- Mark synthetic fixtures as fixtures; do not present them as real research conclusions.
- Persist concise public reasoning summaries only.
- Use claim ledger entries for nontrivial claims.
- Use `EvidenceSpan` locators when a claim depends on full text.
- Keep novelty claims conservative unless closest prior work is recorded.

## Pull Request Checklist

- Tests cover new behavior or a clear reason is documented.
- `make format-check`, `make lint`, `make typecheck`, `make test`, and `make eval` pass.
- New run artifacts are deterministic in offline mode.
- Documentation is updated when CLI behavior, state schema, or skill behavior changes.
- No live network access is required for tests.
