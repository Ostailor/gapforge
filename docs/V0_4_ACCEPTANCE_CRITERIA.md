# GapForge v0.4 Acceptance Criteria

These criteria define pass/fail behavior for the v0.4 actual Codex/GPT-5.4 agentic campaign release.

## Release Goal

v0.4 actual-run success is the main release goal. The release is not complete if it only improves deterministic tests, fake-agent canaries, or prompt-pack generation. It must support accepted real Codex/GPT-5.4 campaigns or explicitly state that actual-run acceptance is not completed.

## Deterministic Compatibility

Pass criteria:

- `gapforge run "topic"` still works.
- `gapforge run "topic" --v2` still works.
- `gapforge run "topic" --v3` still works.
- v0.4 campaign additions do not require live Codex/GPT-5.4 for normal CI.
- Existing run and project state can still load.
- Deterministic and fake-agent paths remain offline-safe.

Fail criteria:

- Any normal CI check requires Codex/GPT-5.4, provider LLMs, live network, or user secrets.
- Deterministic/fake-agent runs silently mutate state with unvalidated model output.

## Actual Codex/GPT-5.4 Run Path

Pass criteria:

- `GAPFORGE_ENABLE_REAL_RUNS=1` and configured Codex/GPT-5.4 settings can execute or complete a real campaign workflow.
- If direct execution is unsupported in the current environment, GapForge produces a first-class task-pack handoff and import path with explicit status, not fake success.
- Missing Codex/GPT-5.4 capability fails clearly.
- Real-run records identify agent name, model, task specs, output paths, validation results, import decisions, and errors.

Fail criteria:

- Real mode returns success without actual Codex execution or validated imported outputs.
- Prompt-pack-only work is counted as real-run acceptance.
- Fake-agent outputs are counted as real-run acceptance.

## Campaign-Level Orchestration

Pass criteria:

- Campaign state persists objective, project, run IDs, source profile, steps, budgets, status, artifacts, validations, imports, failures, and human review.
- Campaigns support resume after interruption.
- Failed agent steps can be retried or skipped with explicit records.
- Campaign dashboards/reports show status, failures, validation summaries, and next actions.

Fail criteria:

- Campaign state is only implicit in logs.
- Failed steps overwrite or delete audit evidence.
- Resume cannot determine which outputs were validated or imported.

## Validated Import

Pass criteria:

- No agent output mutates state until validation passes.
- Validators reject fake citations, unknown paper IDs, invalid EvidenceSpan locators, unsupported high-confidence claims, unsupported novelty claims, missing closest prior work, and malformed JSON.
- Rejected fields are recorded in validation artifacts.
- Accepted imports preserve provenance and label real Codex-backed sections.

Fail criteria:

- Any Codex output bypasses validation.
- Unsupported claims become supported because the model asserted them.
- Unknown citations enter the corpus as real papers without search/metadata confirmation.

## Canary Campaigns

Pass criteria:

- At least three real Codex/GPT-5.4 campaigns are completed and accepted by human review before v0.4 can claim actual-run acceptance.
- Required campaign coverage includes:
  - literature plus novelty campaign
  - local-PDF full-text reading campaign
  - strict undercoverage/refusal campaign
- A reviewer/rebuttal campaign is completed or explicitly listed as not tested.
- Fake-agent campaign remains in CI but is labeled non-acceptance.

Fail criteria:

- One single-skill canary is treated as sufficient for v0.4 actual-run acceptance.
- A failed, rejected, fake, or prompt-pack-only campaign is counted as accepted.

## Human Acceptance Review

Pass criteria:

- Each accepted campaign has a structured human review artifact.
- Human review checks source coverage, evidence grounding, citation honesty, novelty honesty, gap quality, experiment quality, uncertainty visibility, and strict report behavior.
- Any fake citation, unsupported high-confidence claim, strict-report overclaim, or unvalidated import blocks acceptance.

Fail criteria:

- Campaign acceptance is inferred from command exit code alone.
- Human review notes are not linked to campaign records.

## Strict Release Gate

Pass criteria:

- Release notes state one of:
  - `v0.4 actual-run acceptance passed`
  - `v0.4 actual-run acceptance not completed`
- The `passed` statement is allowed only when campaign artifacts and human reviews prove multiple accepted real campaigns.
- Release process refuses actual-run acceptance if canary artifacts are missing, fake-only, prompt-pack-only, rejected, or unreviewed.

Fail criteria:

- Release notes claim actual-run acceptance based only on CI, fake-agent canaries, or manual statements without artifacts.

## Documentation

Pass criteria:

- README distinguishes deterministic tests, fake-agent tests, prompt-pack handoff, and actual Codex/GPT-5.4 campaigns.
- v0.4 docs state that actual-run success is the main release goal.
- Known limitations state v0.3 did not complete actual-run acceptance and v0.4 is intended to fix it.
- Codex agent docs describe campaign-level execution and validated import rules.

Fail criteria:

- Docs imply exhaustive autonomous literature review.
- Docs imply fake-agent canaries prove actual Codex/GPT-5.4 behavior.

## Programmatic API and CLI Parity

Pass criteria:

- `gapforge.api` exposes campaign creation, controller execution, next-action preview, task-pack creation, output validation/import, attestation, campaign review, campaign acceptance, v4 release gate evaluation, and experiment code task generation.
- CLI commands and API functions call the same managers and validators.
- API imports obey the same validation, provenance, attestation, and rollback rules as CLI imports.

Fail criteria:

- Scripting through the API bypasses validation or lets unreviewed agent output mutate campaign state.
- API acceptance reports fake-agent output as actual Codex/GPT-5.4 evidence.

## v0.4 Evals

Pass criteria:

- `gapforge eval --v4` runs offline.
- v4 eval fixtures cover fake-agent campaigns, novelty re-search, undercovered refusal, invalid agent output, experiment-ready direction gates, and reviewer fatal flaws.
- Eval reports show v0.1/v0.2/v0.3/v0.4 metric groups separately.

Fail criteria:

- v4 evals require live Codex, network access, provider LLMs, or private PDFs.
