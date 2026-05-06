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
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
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

## v0.4 Coverage

v0.4 tests should cover campaign and agent behavior without live Codex:

- campaign creation, persistence, stop/resume, and reports
- campaign controller decisions and budgets
- campaign task-pack generation and compact context selection
- output validation, partial import, repair prompts, and rollback
- fake-agent campaign canaries
- novelty re-search loops
- reviewer/rebuttal loops
- experiment code task generation
- dashboard actual-run pages
- campaign human review and acceptance summaries
- v4 release gate failure modes
- `gapforge eval --v4`

Fake-agent tests validate plumbing only. They must never assert that actual Codex/GPT-5.4 research behavior passed.

## v0.4.1 Codex Workflow Checks

Codex/GPT-5.4 real-run workflows are not required in CI, but the CLI must make them diagnosable offline. Tests should cover:

- `gapforge setup-codex`
- `gapforge codex-doctor --task-id <task-id>`
- `gapforge codex-handoff --task-id <task-id> --print-prompt`
- `gapforge validate-import-all --task-id <task-id>`
- `gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff`
- `gapforge validate-repair-output --repair-id <repair-id>`
- `gapforge import-repair-output --repair-id <repair-id>`
- `gapforge v4-release-gate --explain`
- `gapforge v4-release-gate --next-commands`

These tests should use fake or fixture outputs. They must verify that:

- fake-agent output never counts as actual acceptance
- task-pack output needs validation, import, attestation, and human review
- direct mode fails gracefully when `GAPFORGE_CODEX_COMMAND` is missing or malformed
- validation errors include repair commands
- hidden chain-of-thought is not requested or stored
- fake citations and unsupported claims remain rejected

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

For v0.4 campaign changes, also run:

```bash
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge eval --v4 --write-report
```

Real Codex/GPT-5.4 campaign validation is a release-gate activity, not a CI requirement.

Manual real-run validation should follow `docs/CODEX_QUICKSTART.md` and `docs/REAL_RUN_REVIEW_CHECKLIST.md`.

## v0.5 Real-Literature Tests

v0.5 tests must remain offline and deterministic. They should use mocked sources and fixtures to cover:

- `gapforge source-health` disabled, healthy, degraded, and unavailable states
- `gapforge real-campaign-dry-run` profile/custom-topic planning
- `gapforge plan-search-strategy` query families and source-policy targets
- paper canonicalization and merge reports
- prior-work recall blocking missing required rounds
- real-literature human review separating workflow acceptance from research-quality acceptance
- `gapforge v5-release-gate` failure modes and fixture pass cases
- dashboard/report quality sections showing fallback counts, missing prior-work rounds, and refusal reasons

Useful commands:

```bash
gapforge eval --v5 --write-report
PYTHONPATH=src pytest tests/test_real_literature.py tests/test_source_health.py tests/test_search_strategy.py tests/test_prior_work_recall.py
PYTHONPATH=src pytest tests/test_release_gate.py tests/test_dashboard.py
```

Live source and real Codex/GPT-5.4 campaigns are release-validation tasks. Do not add tests that require live network, API keys, or a Codex runner.
