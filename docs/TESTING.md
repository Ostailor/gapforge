# Testing

GapForge tests must run offline. Live source APIs, PDF downloads, embedding providers, and LLM calls must not be required for CI.

## Local Commands

```bash
make install
make format-check
make lint
make typecheck
make test
make eval
make ci
```

Smoke workflows:

```bash
make v2-smoke
make v3-smoke
GAPFORGE_DISABLE_NETWORK=1 gapforge run "low false positive collusion detection" --v3 --active --budget small
```

`make v3-smoke` creates a temporary project, runs the staged v0.3 path offline, builds a project retrieval index, writes a project report, and generates a static dashboard. The active-loop smoke command is separate; it writes active-loop decisions to `active_decisions.md`.

## Network Discipline

Set:

```bash
GAPFORGE_DISABLE_NETWORK=1
```

Use mocked HTTP clients, fixture sources, fake PDF downloaders, deterministic retrieval clients, and `FakeLLMClient`. Do not add tests that depend on live arXiv, CrossRef, Semantic Scholar, OpenReview, provider LLMs, or hosted embedding APIs.

## LLM Test Discipline

Allowed in tests:

- `GAPFORGE_LLM_MODE=off`
- prompt-pack generation
- `FakeLLMClient`
- malformed JSON fixtures

Not allowed in tests:

- provider API keys
- live model calls
- hidden chain-of-thought assertions
- accepting model output without schema validation

## Fixture Policy

Fixtures under `tests/fixtures/` are behavior tests, not literature claims.

When adding fixtures:

- keep them deterministic and small
- label synthetic content clearly
- include negative controls
- include evidence spans when testing full-text grounding
- include source coverage expectations when testing strict reports
- do not commit copyrighted PDFs

## v0.3 Coverage

v0.3 tests should cover:

- project memory creation and run attachment
- hybrid retrieval indexing/search
- active loop decisions and budget termination
- source policy stopping assessments
- optional LLM fake/prompt-pack paths
- related-work matrices
- direction maturation gates
- protocol and manuscript package honesty
- review queue generation
- artifact redaction and safe bundle export

## Verification Before Completion

Before claiming a v0.3 change is complete, run at least:

```bash
make format-check
make lint
make typecheck
make test
make eval
```

For orchestration changes, also run an offline v0.3 smoke command in a temporary directory so generated artifacts do not pollute the repository.
