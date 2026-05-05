# v0.3 Real-Run Acceptance Contract

This contract separates automated correctness checks from real research-agent validation. GapForge must keep deterministic CI fast and offline, while also requiring private/manual Codex/GPT-5.4 assisted acceptance before a v0.3 release can claim actual-run validation.

GapForge still does not perform exhaustive autonomous literature review. A real-run pass means the system produced useful, auditable, human-reviewed research ideation artifacts under the conditions below.

## Validation Levels

### Level 0: Deterministic Unit Tests

- No LLM.
- No live model calls.
- Runs in CI.
- Validates code, schemas, persistence, source/cache behavior, state validation, reports, deterministic evals, and CLI contracts.
- Required commands: `make lint`, `make typecheck`, `make test`, `make eval`.

Level 0 must never require Codex/GPT-5.4, source APIs, hosted embeddings, or private PDFs.

### Level 1: Offline Smoke Tests

- No LLM.
- No network.
- Validates orchestration safety, skip behavior, coverage warnings, strict report conservatism, and generated artifact hygiene.
- Example:

```bash
GAPFORGE_DISABLE_NETWORK=1 gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
GAPFORGE_DISABLE_NETWORK=1 gapforge report --strict
```

Level 1 outputs are smoke-test artifacts, not literature conclusions.

### Level 2: Fake LLM Tests

- Fake model only.
- No live calls.
- Validates JSON guards, schema validation, evidence gating, transcript redaction, unsupported-claim rejection, and safe downgrade behavior.
- Example:

```bash
GAPFORGE_LLM_MODE=fake gapforge read-llm --run-id <run-id> --tier 1 --fake
GAPFORGE_LLM_MODE=fake gapforge mine-gaps-llm --run-id <run-id> --fake
GAPFORGE_LLM_MODE=fake gapforge novelty-check-llm --run-id <run-id> --all --fake
```

Level 2 proves LLM plumbing safety, not research quality.

### Level 3: Prompt-Pack Dry Runs

- No live calls.
- Produces prompts intended for Codex/GPT-5.4.
- Validates that prompts include relevant papers, sections, evidence spans, schemas, citation rules, uncertainty rules, and no hidden chain-of-thought request.
- Example:

```bash
GAPFORGE_LLM_MODE=prompt-pack gapforge read-llm --run-id <run-id> --tier 1 --dry-run-prompts
GAPFORGE_LLM_MODE=prompt-pack gapforge novelty-check-llm --run-id <run-id> --all --dry-run-prompts
```

Level 3 proves prompt readiness, not model performance.

### Level 4: Codex/GPT-5.4 Canary Runs

- Real Codex/GPT-5.4 assisted research-agent run.
- Manual or private workflow.
- Validates actual LLM-assisted deep reading, gap mining, novelty comparison, reviewer simulation, and report usefulness.
- Must use real source artifacts where possible, including at least one local-PDF full-text workflow.
- Must preserve all evidence, citations, and uncertainty.

CI must not run Level 4. If Codex/GPT-5.4 is unavailable, Level 4 has not passed. Never fake a canary pass.

### Level 5: Human-Reviewed Acceptance

- Human reviews Level 4 outputs.
- Validates that outputs are useful, conservative, not misleading, and suitable as research ideation artifacts.
- Human review records must be saved in GapForge state or project memory.

Level 5 is required before v0.3 can claim real-run acceptance.

## v0.3 Release Real-Run Requirements

Before tagging v0.3 as real-run validated:

- At least one Codex/GPT-5.4 LLM-assisted literature run must complete.
- At least one local-PDF full-text workflow must complete.
- Strict report mode must remain conservative.
- No unsupported high-confidence claims.
- No fake citations.
- Novelty dossiers must include closest prior work or explicitly mark novelty unknown.
- Human review must be recorded.

Actual-run validation is required for release claims, but not for normal automated tests.

## Required Evidence Bundle

For each release canary, preserve internally:

- run ID and project ID
- command transcript or run notes
- source coverage report
- full-text coverage report
- paper notes and evidence spans
- novelty dossiers
- final strict report
- review queue
- human review records
- artifact audit result

Do not commit private PDFs, model transcripts, generated dashboards, or sensitive evidence unless explicitly redacted and intended for release.

## Pass/Fail Rule

A v0.3 release may pass CI while failing real-run acceptance. In that case release notes must say automated validation passed but actual Codex/GPT-5.4 canary validation did not pass.

A v0.3 release must not claim actual-run validation unless Levels 4 and 5 were completed honestly.

## Latest Local Verification Status

Date: May 5, 2026.

Deterministic validation passed locally:

- `make format`
- `make format-check`
- `make lint`
- `make typecheck`
- `make test`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `make coverage`
- `make v2-smoke`
- `make v3-smoke`

Fake-agent validation passed:

- `GAPFORGE_DISABLE_NETWORK=1 gapforge canary-run --profile fake_agent_regression`
- Result: complete, valid fake AgentClient schema validation.

Actual Codex/GPT-5.4 validation did **not** pass in this environment:

- `GAPFORGE_ENABLE_REAL_RUNS` was unset.
- `GAPFORGE_AGENT_MODE`, `GAPFORGE_AGENT_NAME`, and `GAPFORGE_CODEX_MODEL` were unset.
- `low_fpr_collusion_codex` was recorded as failed/not passed.
- `manual_pdf_fulltext_codex` was recorded as failed/not passed.
- `gapforge real-run-acceptance` reported no accepted human-reviewed actual Codex/GPT-5.4 canary.

This is an honest not-passed release-gate state, not a canary success.
