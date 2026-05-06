# Real-Run Review Checklist

Use this checklist for human-reviewed acceptance of Codex/GPT-5.4 task-pack, manual-handoff, direct, and campaign runs. For v0.4 and v0.4.1, review the whole campaign or canary workflow, not just one JSON file.

## Identity

- [ ] Run ID recorded if a run exists.
- [ ] Project ID recorded if a project exists.
- [ ] Campaign ID recorded.
- [ ] Task ID recorded.
- [ ] Canary ID recorded if this is a canary.
- [ ] Topic recorded.
- [ ] Mode recorded: deterministic, fake-agent, task-pack, manual-handoff, or direct.
- [ ] Agent/model recorded: `codex` / `gpt-5.4`.
- [ ] Reviewer name and date recorded.

## Actual-Run Eligibility

- [ ] Fake-agent output is not counted as actual Codex/GPT-5.4 acceptance.
- [ ] Task-pack/manual-handoff output was produced by Codex/GPT-5.4.
- [ ] Direct output came from the configured direct runner, not fake fallback.
- [ ] Output was validated before import.
- [ ] Imported objects are visible in import records.
- [ ] Task-pack/manual-handoff output has attestation:

```bash
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
```

- [ ] Actual-run status was checked:

```bash
gapforge actual-run-status --campaign-id <campaign-id>
```

## Source and Evidence

- [ ] Source coverage is visible.
- [ ] Missing searches and failed sources are visible.
- [ ] Offline/fallback data is labeled.
- [ ] Full-text or PDF coverage is visible when relevant.
- [ ] Evidence-backed claims cite paper IDs and EvidenceSpan locators.
- [ ] Abstract-only claims are not high confidence.

## Codex Output Safety

- [ ] JSON output matches the expected task schema.
- [ ] Every paper ID resolves to a known paper.
- [ ] Every EvidenceSpan ID/locator resolves to known evidence.
- [ ] No fake citations, invented DOIs, invented arXiv IDs, or invented papers.
- [ ] No invented datasets, metrics, baselines, quotes, or results.
- [ ] No supported/high-confidence claim lacks evidence.
- [ ] No hidden chain-of-thought is requested or stored.
- [ ] Public reasoning summaries are concise and safe.

## Novelty and Recommendations

- [ ] Every recommended direction has a novelty dossier or explicit refusal reason.
- [ ] Closest prior work is listed, or novelty is marked unknown.
- [ ] Missing searches are visible.
- [ ] Strong novelty is not claimed under poor coverage.
- [ ] If coverage is poor, strict mode refuses to recommend a direction.

## Repair and Revalidation

If validation failed:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
gapforge validate-repair-output --repair-id <repair-id>
gapforge import-repair-output --repair-id <repair-id>
```

- [ ] Repair prompt included exact validation errors.
- [ ] Repair prompt included known paper IDs and evidence locators.
- [ ] Repair did not ask Codex to invent evidence or citations.
- [ ] Repaired output was validated before import.

## Campaign Acceptance

- [ ] `campaign_report.md` inspected.
- [ ] Stop reason is explicit and appropriate.
- [ ] Human review was recorded:

```bash
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
```

- [ ] `gapforge campaign-acceptance --campaign-id <campaign-id>` inspected.
- [ ] Dashboard actual-run pages distinguish fake, task-pack, handoff, and direct modes.
- [ ] `gapforge v4-release-gate --explain` inspected if this contributes to release acceptance.

## Blocking Failures

Reject the campaign if any are true:

- [ ] Fake citation found.
- [ ] Unsupported high-confidence claim found.
- [ ] Obvious prior work missed.
- [ ] Strong novelty claimed without closest prior work.
- [ ] Strict report overclaimed readiness or novelty.
- [ ] Task-pack output imported without attestation.
- [ ] Human review accepted a fake-agent-only campaign as actual.
- [ ] Hidden chain-of-thought was requested or stored.

## Decision

- [ ] Pass.
- [ ] Pass with limitations.
- [ ] Fail.

```text
Reviewer:
Date:
Campaign ID:
Task ID:
Decision:
Blocking issues:
Required fixes:
Residual risks:
```
