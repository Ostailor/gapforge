# Known Limitations

GapForge is a research ideation aid, not an autonomous literature reviewer or publication decision system.

## Cross-Version Limits

- It does not guarantee exhaustive search.
- It does not guarantee novelty.
- It does not replace expert reading or domain judgment.
- Offline fallback and synthetic fixtures are smoke-test artifacts.
- Source APIs can be incomplete, rate-limited, stale, or unavailable.
- PDF extraction can miss text, tables, references, equations, and layout.
- Citation counts and venue heuristics can bias ranking.

## v0.1 Limits

v0.1 is deterministic and metadata/abstract-heavy. It can create useful scaffolding but should not be treated as real literature coverage.

## v0.2 Limits

v0.2 adds full-text artifacts, evidence spans, coverage reports, citation graphs, novelty dossiers, and strict reports. Remaining risks:

- full-text parsing is lightweight and may miss section boundaries
- closest-prior-work search is still conservative and partly lexical
- cross-domain analogies may remain query-only
- gap evidence matrices are only as strong as available notes and spans
- human review is still necessary before pursuing directions

## v0.3 Limits

v0.3 adds project memory, hybrid retrieval, active-loop decisions, optional LLM-backed skills, related-work matrices, maturation, protocols, review queues, dashboards, and manuscript packages. Remaining risks:

- semantic retrieval ranks candidates but does not prove relevance or novelty
- deterministic hash embeddings are useful for offline tests but not research-grade semantic models
- optional provider LLM outputs remain untrusted until schema-valid and evidence-located
- actual Codex/GPT-5.4 canary validation is opt-in; the May 6, 2026 local release-gate pass validated the direct Codex workflow with small canary campaigns, not broad literature-review quality
- project memory can carry stale beliefs if not reviewed
- source policy profiles are transparent heuristics, not field-complete standards
- manuscript packages are starter kits and must not imply results

## v0.3 Goals

- improve closest-prior-work search using retrieval, citation graph, source policies, and project memory
- make unsupported claims, contradictions, and rejected ideas visible
- guide human review with explicit queues
- mature research directions through evidence gates
- export honest writing packages with missing-work labels

## v0.3 Non-Goals

- exhaustive autonomous literature review
- mandatory live LLM, embedding, or source API calls
- silent trust in model-generated citations
- hiding poor coverage behind polished reports
- presenting fixture/fallback data as real literature conclusions
- exporting fake results or publication-ready claims without human validation

## v0.4 Target and Limits

v0.4 is the actual Codex/GPT-5.4 agentic campaign release path. Its main goal is to fix the v0.3 actual-run gap by making real Codex/GPT-5.4 campaigns executable or handoff/import-completable, validated, recoverable, and human-reviewable.

v0.4 must still preserve these limits:

- deterministic mode remains available
- normal CI does not require Codex/GPT-5.4
- fake-agent canaries do not count as actual-run acceptance
- prompt-pack-only workflows do not count unless real Codex outputs are imported, validated, and reviewed
- unvalidated model output cannot mutate state
- actual-run acceptance cannot be claimed without multiple accepted real campaigns
- GapForge still does not perform exhaustive autonomous literature review
- direct Codex execution depends on `GAPFORGE_CODEX_COMMAND` and may be unavailable in some environments
- task-pack/manual-handoff workflows require disciplined external Codex execution and validated import
- v4 eval fixtures are offline behavior checks, not proof of research quality

See `docs/V0_4_REAL_RUN_ACCEPTANCE.md` for the release gate.

## v0.4 Non-Goals

- removing deterministic or fake-agent paths
- requiring Codex/GPT-5.4 for normal CI
- accepting unvalidated agent output
- treating human attestation as evidence
- counting fake-agent campaigns as actual-run acceptance
- claiming autonomous exhaustive literature review

## Operational Guidance

Use strict mode and coverage assessment before interpreting outputs:

```bash
gapforge coverage --run-id <run-id>
gapforge assess-coverage --run-id <run-id> --profile ai_safety
gapforge report --run-id <run-id> --strict
gapforge review-queue --run-id <run-id>
```

When in doubt, treat GapForge output as a to-do list for search, reading, and review rather than a conclusion.

## Latest Verification Limitation

The May 6, 2026 local verification pass succeeded for the v0.4 actual-run release gate. Three real Codex/GPT-5.4 workflow canaries were executed through the direct runner, validated/imported, attested, human-reviewed, and accepted by `gapforge v4-release-gate`. This resolves the v0.4 release-gate blocker for the workflow path, but it does not prove exhaustive literature-review quality or broad field coverage.

## v0.4.1 Planned Limitation Fix

v0.4.1 is planned as a usability patch for Codex actual-run workflows. It does not change the research bar. It should make these limits easier to diagnose:

- direct runner command missing or malformed
- successful command with no output files
- handoff output written to the wrong directory
- Codex returning markdown when JSON patches are required
- validation errors that do not show repair steps
- task-pack output imported without attestation
- fake-agent success being confused with real acceptance

The intended v0.4.1 docs are `docs/V0_4_1_CODEX_FIX_PLAN.md`, `docs/V0_4_1_CODEX_ACCEPTANCE.md`, and `docs/V0_4_1_CODEX_TROUBLESHOOTING.md`.
