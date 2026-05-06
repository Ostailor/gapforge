# GapForge v0.5 Acceptance Criteria

v0.5 acceptance is about research quality in live-literature campaigns. Passing v0.4.1 workflow canaries is necessary background, but not sufficient.

## Validation Levels

### Level 0: Deterministic CI

- No live source calls.
- No Codex/GPT-5.4 requirement.
- Tests schema, persistence, validation, reports, fake agents, and deterministic evals.

### Level 1: Offline Smoke

- No network and no live model.
- Verifies campaign orchestration fails closed and labels fallback data as smoke-test data.

### Level 2: Fake-Agent Campaigns

- No live model.
- Verifies output validation, repair, rollback, attestation blockers, and release-gate messaging.
- Does not count as actual research quality.

### Level 3: Codex Workflow Canaries

- Real Codex/GPT-5.4 or task-pack/manual-handoff output.
- Validates task execution, import, attestation, and human review.
- Does not count as live-literature quality unless live sources and real-paper review criteria are met.

### Level 4: Live-Literature Campaigns

- Uses live source connectors unless a source is explicitly unavailable and recorded.
- Runs a multi-step campaign over real paper metadata and available full text.
- Produces auditable search coverage, closest-prior-work dossiers, related-work matrix, and experiment protocol or explicit refusal.

### Level 5: Human Expert Acceptance

- A human reviewer evaluates campaign quality using the v0.5 review checklist.
- Reviewer must reject campaigns with fake citations, unsupported high-confidence claims, obvious missed prior work, or novelty overclaim.

## Release Requirements

To claim v0.5 live-literature campaign quality passed:

- Deterministic CI passes.
- Fake-agent campaign smoke passes.
- v0.4.1 Codex workflow path remains passing or explicitly documented if unavailable.
- At least three live-literature campaigns complete and are human accepted.
- At least two fields are represented across accepted campaigns.
- At least one campaign correctly refuses a recommendation due to poor coverage, weak novelty, or closest prior work.
- At least one campaign produces an experiment-ready direction with:
  - source coverage assessment
  - closest-prior-work dossier
  - related-work matrix
  - experiment protocol
  - reviewer panel or blocking issue review
- Every accepted campaign includes:
  - live SearchQueryRecord entries
  - source failure records where applicable
  - retrieval index
  - source coverage report
  - novelty dossier or explicit unknown/refusal
  - evidence locators for full-text-backed claims
  - explicit stop reason
  - human review

## Blocking Failures

Any of these blocks v0.5 live-literature acceptance:

- Fake citation.
- Unsupported high-confidence claim.
- Strong novelty without closest prior work.
- Missing search coverage hidden by report language.
- Fixture-only campaign counted as live-literature quality.
- Obvious prior work missed without postmortem.
- Experiment protocol lacks baselines/metrics/falsification.
- Strict report recommends a direction despite poor coverage or unresolved novelty.

## CI Requirement

CI must remain deterministic and offline-safe. Live source checks and Codex/GPT-5.4 real campaigns are release validation tasks, not normal automated tests.

## Minimum Command Evidence

A release candidate should include evidence from:

```bash
make ci
gapforge eval --v5 --write-report
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge live-source-diagnostic --topic "<topic>" --source-profile <profile> --write-report
gapforge real-literature-run --profile <profile>
gapforge prior-work-recall --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --accept-quality --reviewer "<expert>"
gapforge v5-release-gate --project-id <project-id> --write-report --json
```

Dry-run, fake-agent, and fixture results can support implementation confidence, but the release statement must not count them as live-literature quality acceptance.

## Latest Verification Status

As of the May 6, 2026 local verification pass:

- Deterministic checks passed: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `gapforge eval --v4 --write-report`, `gapforge eval --v5 --write-report`, `make coverage`, `make v2-smoke`, `make v3-smoke`, and `make v4-smoke`.
- `gapforge setup-codex` reported direct real-run execution disabled in the current shell, with task-pack/manual-handoff still available.
- `gapforge v4-release-gate --explain` passed from existing accepted workflow-canary artifacts.
- `gapforge source-health` found several reachable sources; topic-specific AI-safety checks may still degrade, so v0.5 diagnostics use broader source-profile checks only as reachability evidence and keep topic-specific warnings visible.
- `gapforge real-campaign-dry-run --profile live_low_fpr_collusion` rendered the planned campaign. Dry runs still do not count as live-literature validation.
- Live-literature campaign records were created for `live_low_fpr_collusion`, `live_llm_monitor_evasion`, and `live_undercovered_refusal`.
- `campaign-20260506T031950Z-low-false-positive-collusion-detection-in-llm-agents` was accepted for research quality as an experiment-ready live-literature smoke campaign with search rounds, canonicalization, retrieval, prior-work recall, novelty dossier, related-work matrix, experiment protocol, and human review.
- `campaign-20260506T031746Z-low-false-positive-collusion-detection-in-llm-agents` was accepted for research quality as a conservative refusal campaign because closest-prior-work/coverage risk remained too high.
- `gapforge v5-release-gate --write-report --json` passed with no blockers.

Therefore v0.5 live-literature release acceptance is complete for this local verification pass. This validates the v0.5 quality gate and conservative campaign behavior; it still does not claim exhaustive literature review or broad expert validation across fields.
