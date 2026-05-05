# Contributing

GapForge is evidence-first software. Contributions must preserve citation safety, auditability, deterministic tests, and conservative reporting.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
make install
pre-commit install
```

## Development Rules

- Prefer existing models, managers, and skills over parallel implementations.
- Keep deterministic/offline behavior working.
- Add tests for new state fields, CLI behavior, and validation gates.
- Do not require live network, LLM, or embedding APIs in tests.
- Do not commit generated runs, caches, PDFs, dashboards, transcripts, or paper packages unless they are tiny intentional fixtures.
- Use public reasoning summaries only; never persist hidden chain-of-thought.

## Evidence Rules

- Do not invent papers, citations, results, datasets, metrics, quotes, or venues.
- Mark synthetic fixtures as synthetic.
- Use claim ledger entries for nontrivial claims.
- Use EvidenceSpan locators for full-text evidence.
- Keep novelty claims conservative until closest prior work is recorded.
- Preserve rejected ideas and human review decisions.

## v0.3 Contribution Areas

When touching v0.3 features, update docs and tests for the relevant area:

- project memory
- hybrid retrieval
- optional LLM adapters
- source policy profiles
- active loop decisions
- related-work matrices
- direction maturation
- experiment protocols
- review panels and review queues
- manuscript exports
- dashboard and artifact safety

## Pull Request Checklist

- `make format-check` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes
- `make eval` passes
- docs updated for CLI/state/schema changes
- new skills or skill changes include validation and evidence rules
- no generated artifacts or secrets are staged
- limitations remain honest

## Release Hygiene

Before release, run:

```bash
make ci
GAPFORGE_DISABLE_NETWORK=1 gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
```

Then check:

```bash
gapforge audit-artifacts --run-id <run-id>
git status --short
```

Generated artifacts should remain ignored unless intentionally committed as fixtures.
