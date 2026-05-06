# GapForge v0.4 Roadmap

v0.4 is the actual Codex/GPT-5.4 agentic campaign release. Its primary purpose is to close the v0.3 gap: v0.3 shipped task packs, fake-agent canaries, and validated import infrastructure, but did not complete accepted real Codex/GPT-5.4 canaries and did not provide a working direct actual-run path.

v0.4 must make real Codex/GPT-5.4 research campaigns executable, auditable, recoverable, and human-reviewable without weakening deterministic CI or evidence safety.

## Why v0.4 Exists

v0.3 proved the deterministic and fake-agent architecture:

- project memory and hybrid retrieval work offline
- Codex task packs can be generated
- agent output import can be validated
- fake-agent canaries can exercise schema and safety gates
- release docs can distinguish automated tests from actual research-agent validation

The remaining release-critical gap is actual execution. v0.4 exists to make GapForge run real Codex/GPT-5.4 campaign workflows and to require multiple accepted real campaigns before claiming actual-run acceptance.

## Must Have

### Actual Codex/GPT-5.4 Run Path

- Implement a working actual-run pathway for Codex/GPT-5.4.
- Support either direct execution through a stable configured adapter or a first-class task-pack handoff/import workflow that can be completed and audited.
- Fail clearly when Codex/GPT-5.4 is unavailable.
- Never silently downgrade a requested real run into fake-agent success.
- Require `GAPFORGE_ENABLE_REAL_RUNS=1` or equivalent explicit real-run opt-in.

### Campaign-Level State and Orchestration

- Add campaign state above individual agent tasks.
- Track campaign objective, topic, project, run IDs, source profile, planned steps, active step, status, budget, artifacts, and review state.
- Support multi-step campaigns spanning search, reading, retrieval, novelty, gap mining, reviewer simulation, report critique, and paper package review.
- Save after every campaign step.

### Agent Task Execution Lifecycle

- Define lifecycle states for planned, packed, dispatched, running, completed, failed, validated, imported, rejected, retried, skipped, and superseded.
- Record command logs, task-pack paths, expected outputs, produced outputs, validation results, and import decisions.
- Preserve public reasoning summaries only.
- Redact secrets in transcripts and logs.

### Validated Output Import

- Keep validated import as the only path from Codex output to state mutation.
- Reject unsupported high-confidence claims, invalid locators, unknown prior-work IDs, fake citations, and unlisted output files.
- Convert model-proposed unknown citations into search requests rather than accepting them as sources.
- Make rejected fields visible in validation reports.

### Multi-Step Canary Campaigns

- Replace single-skill canaries with multi-step campaigns.
- Include at least:
  - low-FPR collusion Codex literature/novelty campaign
  - manual local-PDF full-text Codex reading campaign
  - undercovered-topic strict-refusal campaign
  - reviewer/rebuttal campaign over an experiment protocol or direction
- Keep a fake-agent regression campaign for CI, but do not count it as actual-run acceptance.

### Human Acceptance Reviews

- Require structured human review for each real campaign.
- Store acceptance/rejection decisions with reasons, scores, blocking failures, and accepted/rejected artifacts.
- A campaign cannot pass if fake citations, unsupported high-confidence claims, missing closest prior work, strict-report overclaiming, or unvalidated imports are found.

### Strict Release Gate

- v0.4 may pass CI without real Codex/GPT-5.4, but it may not claim actual-run acceptance without accepted real campaigns.
- Require multiple accepted Codex/GPT-5.4 campaigns before release notes can say actual-run acceptance passed.
- The gate must be auditable from campaign records and human review artifacts.

### Campaign Dashboards and Reports

- Add campaign dashboards or dashboard sections for task status, failures, validations, imports, human reviews, coverage, and final recommendations.
- Add campaign reports that separate deterministic, fake-agent, prompt-pack, and real Codex-backed work.
- Show unresolved failures and recovery options.

### Failure Diagnosis and Recovery

- Provide clear diagnostics for:
  - Codex unavailable
  - task pack generated but not executed
  - missing output files
  - malformed JSON
  - invalid evidence locators
  - fake or unknown citations
  - budget exhaustion
  - human rejection
- Support resume/retry after failed agent steps.
- Preserve failed outputs for audit without importing them.

## Should Have

- Campaign templates for common research workflows.
- Better local replay of validation failures from stored task packs.
- Side-by-side deterministic versus Codex-backed comparison reports.
- Campaign-level source coverage and stopping assessment summaries.
- Campaign export bundle with redacted artifacts for human review.
- Better CLI summaries for partially completed campaigns.

## Future v0.5 Work

- Autonomous long-horizon research programs across many campaigns.
- Collaborative multi-human review workflows.
- External reference-manager and paper-library integrations.
- Experiment execution adapters and result ingestion.
- Richer browser/UI-assisted Codex workflows.
- Real-world expert-labeled benchmark campaigns.

## Explicit Non-Goals

- Do not remove deterministic mode.
- Do not require Codex/GPT-5.4 for normal CI.
- Do not claim exhaustive autonomous literature review.
- Do not allow unvalidated model output to mutate state.
- Do not count fake-agent canaries as actual-run acceptance.
- Do not fake a passing real canary.

## Success Definition

v0.4 succeeds only if a user can run or complete a real Codex/GPT-5.4 campaign, validate and import its outputs safely, recover from failures, generate campaign reports, and record human acceptance. Automated tests alone are not enough to claim v0.4 actual-run acceptance.

## User-Facing Workflow Targets

The v0.4 UX should make these paths explicit:

```bash
# CI-safe campaign skeleton
gapforge campaign-run --campaign-id <id> --mode deterministic

# CI-safe fake-agent regression
gapforge campaign-canary-run --profile fake_agent_campaign_regression

# Manual Codex/GPT-5.4 handoff
gapforge campaign-task --campaign-id <id> --type novelty_reviewer
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"

# Direct runner when configured
gapforge codex-run --task-id <task-id> --direct

# Acceptance and release gate
gapforge campaign-review --campaign-id <id> --accept --reviewer "<name>"
gapforge v4-release-gate --project-id <project-id> --write-report
```

These commands must remain honest about mode. Deterministic, fake-agent, and prompt-pack-only paths are useful engineering validation; they are not real research-agent acceptance.
