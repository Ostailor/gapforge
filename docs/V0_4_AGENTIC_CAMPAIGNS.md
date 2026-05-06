# v0.4 Agentic Campaigns

An agentic campaign is a multi-step research workflow executed with explicit campaign state, Codex/GPT-5.4 task execution, validated imports, recovery behavior, and human acceptance review.

Campaigns are larger than v0.3 task packs. A task pack asks Codex to do one bounded skill. A campaign coordinates several tasks toward a research objective.

## Campaign State

Campaign state should include:

- campaign ID
- project ID
- run IDs
- topic and objective
- source policy profile
- mode: deterministic, fake-agent, prompt-pack, codex
- agent name and model
- step plan
- current step
- budget and limits
- task specs
- task-pack paths
- output paths
- validation records
- import records
- failures and retry counts
- human review status
- campaign report and dashboard paths

Campaign state must be durable. It must be possible to inspect a campaign after interruption and know which steps ran, which failed, which outputs were validated, and which outputs were imported.

Primary CLI:

```bash
gapforge campaign-create "topic" --project-id <project-id> --mode deterministic
gapforge campaign-status --campaign-id <campaign-id>
gapforge campaign-next --campaign-id <campaign-id>
gapforge campaign-run --campaign-id <campaign-id> --mode codex_task_pack --max-iterations 5
gapforge campaign-report --campaign-id <campaign-id>
```

Programmatic API:

```python
from gapforge import api

campaign = api.create_campaign(project_id, "topic", mode="codex_task_pack", agent_name="codex", model="gpt-5.4")
action = api.campaign_next(campaign.campaign.id)
state = api.run_campaign(campaign.campaign.id, mode="codex_task_pack", max_iterations=1)
```

## Required Lifecycle

Each campaign step should move through explicit states:

- planned
- packed
- dispatched
- running
- completed
- failed
- validated
- imported
- rejected
- retried
- skipped
- superseded

State transitions must be auditable. A failed step should not erase its task pack or output files.

## Campaign Types

### Literature and Novelty Campaign

Objective:
Find source-backed gaps and run closest-prior-work checks with Codex/GPT-5.4 assistance.

Required steps:

- source search and source coverage
- retrieval index build
- Codex-backed deep reading or validated reading task packs
- gap mining with evidence matrix
- novelty dossier creation
- strict report
- human acceptance review

Acceptance focus:

- no fake citations
- closest prior work listed or novelty unknown
- no unsupported high-confidence claims
- source coverage limitations visible

### Local-PDF Full-Text Campaign

Objective:
Validate manual PDF ingestion, parsing, evidence spans, and Codex-backed full-text reading.

Required steps:

- manual local PDF ingest
- artifact hashing
- PDF parsing and sectionization
- evidence span creation
- Codex-backed deep reading
- validated import
- full-text coverage report
- human acceptance review

Acceptance focus:

- full-text versus abstract-only distinction
- locator-backed claims
- no invented quotes, results, tables, or citations

### Undercoverage Refusal Campaign

Objective:
Verify that strict mode refuses to recommend a direction when source coverage is poor.

Required steps:

- run sparse or offline search
- source policy assessment
- novelty dossier or missing-search report
- strict final report
- human acceptance review

Acceptance focus:

- strict report refuses unsupported novelty
- next searches are recommended
- fallback/offline data is labeled

### Reviewer and Rebuttal Campaign

Objective:
Attack a direction or experiment protocol and produce a rebuttal plan without inventing results.

Required steps:

- related-work matrix
- experiment protocol
- Codex-backed reviewer panel or validated task pack
- rebuttal plan
- manuscript/paper package review
- human acceptance review

Acceptance focus:

- missing baselines are major/fatal
- novelty risks are explicit
- rebuttal plan asks for evidence or experiments rather than inventing results

## Execution Modes

### Deterministic

No Codex/GPT-5.4. Useful for offline campaign skeletons and CI safety. Does not count as actual-run acceptance.

### Fake Agent

Uses FakeAgentClient. Useful for schema and lifecycle tests. Does not count as actual-run acceptance.

### Prompt-Pack Handoff

Writes task packs for external/manual Codex execution. This can support real-run acceptance only if real Codex outputs are later imported, validated, reviewed, and linked to the campaign.

### Codex Actual Run

Executes Codex/GPT-5.4 through the configured actual-run pathway. Requires explicit real-run opt-in. Counts toward actual-run acceptance only after validated imports and human acceptance review.

## Task-Pack Import Contract

Campaign task packs are written under:

```text
projects/<project>/campaigns/<campaign_id>/agent_tasks/<task_id>/
  CAMPAIGN_TASK.md
  HANDOFF.md
  expected_outputs.json
  schema_examples.json
  validation_rules.md
  evidence_rules.md
  outputs/
```

Codex should write only expected output files into `outputs/`. GapForge then runs:

```bash
gapforge validate-import-all --task-id <task-id>
```

Invalid JSON, fake citations, unknown paper IDs, invalid evidence locators, unsupported high-confidence claims, and strong novelty without prior work are rejected. Partial import is allowed only when accepted and rejected portions are explicitly recorded.

## Actual-Run Attestation

Task-pack and manual-handoff campaigns require attestation:

```bash
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
```

Attestation does not bypass validation. It records that a human asserts Codex/GPT-5.4 produced the validated outputs. Fake-agent output cannot be attested as actual Codex work.

## Failure Diagnosis

Campaign reports should diagnose:

- Codex unavailable
- real-run opt-in missing
- task pack generated but not executed
- output file missing
- malformed JSON
- invalid EvidenceSpan locator
- unknown paper or prior-work ID
- fake citation
- unsupported high-confidence claim
- strict report overclaim
- source coverage insufficient
- human review rejection
- budget exhausted

## Recovery

v0.4 campaigns should support:

- resume from latest durable campaign state
- retry a failed step
- replace a bad output with a corrected file and revalidate
- skip a failed step with explicit reason
- request human review when automation should pause
- preserve rejected outputs for audit

## Release Implication

A campaign is not accepted because it completed. It is accepted only after validation and human review. v0.4 actual-run acceptance requires multiple accepted real Codex/GPT-5.4 campaigns.
