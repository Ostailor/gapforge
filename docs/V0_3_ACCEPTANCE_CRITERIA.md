# GapForge v0.3 Acceptance Criteria

These criteria define concrete pass/fail behavior for v0.3. They preserve the v0.1/v0.2 safety contract: GapForge assists ideation but does not claim exhaustive review, guaranteed novelty, or publication readiness.

## Project Memory

Pass:

- `gapforge init-project` writes a project directory.
- A run can attach to a project with `--project-id` or `gapforge attach-run`.
- `gapforge sync-project-memory` deduplicates papers and syncs claims, gaps, rejected ideas, human decisions, and research directions.
- Reports distinguish project memory from current-run evidence.

Fail:

- Rejected ideas reappear as recommendations without explicit revision or override.
- Project memory overwrites run-local artifacts without audit.

## Hybrid Retrieval

Pass:

- `gapforge build-index --run-id` and `--project-id` persist reusable indexes.
- `gapforge search-index` returns paper/section/evidence/project-memory results with scores and locators.
- Deterministic offline retrieval works without API keys.
- Novelty/gap workflows can consume retrieval candidates.

Fail:

- Retrieval results lose object IDs or provenance.
- Tests require hosted embeddings.
- Semantic similarity is treated as proof of novelty.

## Source Policy and Stopping

Pass:

- `gapforge assess-coverage --profile <profile>` writes pass/fail coverage criteria.
- Strict reports use policy state.
- Novelty cannot become strong when policy-critical searches are missing.
- Offline fallback is labeled and does not satisfy live-source requirements.

Fail:

- Reports imply adequate coverage without policy assessment.
- Missing searches are hidden.

## Active Loop

Pass:

- `gapforge run "topic" --v3 --active --budget small` terminates.
- `active_decisions.md` records decision type, reason, evidence, expected value, cost, and status.
- Budgets are respected.
- Human review requests pause or stop automation safely.

Fail:

- The active loop expands indefinitely.
- Decisions are not auditable.

## Optional LLM Skills

Pass:

- Default mode remains `off`.
- `prompt-pack` and `fake` modes require no live calls.
- Provider mode is opt-in and isolated.
- JSON is schema-validated before state updates.
- Unsupported model claims are rejected, downgraded, or marked uncertain.
- No hidden chain-of-thought is stored.

Fail:

- Tests require a live LLM.
- Model output creates trusted citations or supported claims without evidence.

## Real-Run Validation Levels

Pass:

- Level 0 deterministic unit tests run in CI with no LLM.
- Level 1 offline smoke tests run with no network and no LLM.
- Level 2 fake LLM tests validate JSON guards, schema validation, evidence gates, and unsupported-claim rejection.
- Level 3 prompt-pack dry runs validate Codex/GPT-5.4 prompts without live calls.
- Level 4 Codex/GPT-5.4 canary runs complete in a manual/private workflow before claiming actual-run validation.
- Level 5 human-reviewed acceptance records review decisions on canary outputs.

Fail:

- CI requires Codex/GPT-5.4 or a live model provider.
- Fake LLM or prompt-pack output is counted as actual-run validation.
- A release claims canary validation when Codex/GPT-5.4 was unavailable.
- Canary pass status is inferred instead of recorded.

## Related Work and Direction Maturation

Pass:

- Related-work matrices classify prior work by relationship and expose must-cite/baseline papers.
- Directly solving prior work blocks or downgrades a direction.
- Direction maturity is evidence-gated.
- Human rejection and locks are respected.

Fail:

- A direction reaches manuscript-ready without novelty, protocol, reviewer, claim, and human-review gates.

## Experiment Protocols and Manuscript Packages

Pass:

- Protocols include datasets, baselines, metrics, statistics, ablations, reproducibility, compute, timeline, risks, and falsification conditions.
- Paper packages include evidence index and limitations.
- Expected results are labeled hypothetical.
- Rejected directions cannot export unless explicitly allowed.

Fail:

- Exported manuscripts present fake results as real.
- Bibliography or citations are invented.

## Review Queue and Dashboard

Pass:

- Review queue items are created for high-impact unsupported claims, unknown novelty, contradictions, waivers, and near-ready directions.
- Completed/dismissed queue items persist.
- Dashboard pages escape unsafe content and show evidence, uncertainty, warnings, and rejected ideas.

Fail:

- Open risks are buried or omitted from report/dashboard.

## Evals and CI

Pass:

- `make lint` passes.
- `make typecheck` passes.
- `make test` passes.
- `make eval` passes offline.
- `gapforge eval --v3` runs offline.
- v0.1 and v0.2 paths still work.
- At least one strict offline v0.3 smoke run refuses recommendation under poor coverage.

Fail:

- Generated runs, caches, PDFs, dashboards, transcripts, or paper packages are accidentally committed.
- Fixture data is described as real literature conclusions.

## v0.3 Release Real-Run Gate

Pass:

- At least one Codex/GPT-5.4 LLM-assisted literature run completes.
- At least one local-PDF full-text workflow completes.
- Strict report mode remains conservative.
- No unsupported high-confidence claims are accepted.
- No fake citations appear.
- Novelty dossiers include closest prior work or explicitly mark novelty unknown.
- Human review is recorded in run or project state.

Fail:

- Actual-run validation is skipped but release notes claim it passed.
- Strict report recommends a paper-ready direction under poor coverage.
- Novelty is marked strong without closest prior work.
- Human review exists only outside GapForge state with no audit record.
