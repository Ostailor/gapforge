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

## v0.5 Target and Limits

v0.5 is the real literature campaign quality release path. It should validate that GapForge can run useful multi-step campaigns over live literature, not merely that Codex/GPT-5.4 task execution works.

v0.5 must still preserve these limits:

- deterministic and fake-agent CI remain offline-safe
- live source calls are release-validation tasks, not normal test requirements
- v0.4.1 workflow canaries do not count as live-literature quality
- source connectors can miss papers, fail, rate-limit, or return incomplete metadata
- closest-prior-work recall can be measured and reviewed but not guaranteed exhaustive
- human expert review is required before treating a direction as credible
- model-generated novelty remains a hypothesis until closest prior work and counterevidence are visible
- experiment protocols are plans, not completed experiments or results

v0.5 non-goals:

- exhaustive autonomous literature review
- requiring live sources in CI
- weakening validation to make real runs pass
- counting fixture-only canaries as real literature quality
- presenting model-generated novelty as fact without closest prior work
- hiding missed prior work, poor coverage, or uncertainty behind polished reports

v0.5 added diagnostics and gates, not omniscience. The live source health check can show that a connector is reachable, but it cannot prove a source is complete. The prior-work recall gate can force exact/method/benchmark/survey/citation-style searches, but it cannot guarantee no paper was missed. Human quality review remains required before using a direction as a serious research lead.

Workflow canaries, fake-agent campaigns, dry runs, and fixture evals remain separate from live-literature quality. They should be described as implementation validation, not research validation.

## v0.6 Target and Limits

v0.6 is the experiment execution and empirical validation release. It moves GapForge from experiment-ready directions to executed, logged, statistically analyzed, reproducible experiment packages.

v0.6 must still preserve these limits:

- an experiment protocol is not an executed experiment
- a generated scaffold is not an executed experiment
- a smoke run validates wiring only and does not prove empirical success
- pilot runs are exploratory and must be labeled as such
- main-run claims still require result artifacts, parsed metrics, uncertainty analysis, and reproducibility status
- an empirical claim cannot be marked supported without a run record and result artifact
- failed and negative experiments must remain visible in reports
- dataset cards, baseline registries, metric registries, run manifests, logs, statistics, and reproducibility checks are required before empirical claims are trusted
- paper packages must separate real observed results from placeholders, expected results, and hypotheses
- v0.5 literature, novelty, and prior-work recall gates must not be weakened to reach experiment execution faster

v0.6 non-goals:

- fabricating experimental results
- marking experiments executed from protocols, scaffolds, task plans, or smoke tests alone
- requiring expensive experiments in normal CI
- claiming empirical success from fixture smoke outputs
- hiding failed runs, negative results, missing baselines, weak metrics, or irreproducible artifacts

v0.6 requires at least one executed fixture experiment and one failed or negative experiment path for release acceptance. That bar validates experiment execution mechanics and reporting honesty; it does not prove publishable empirical findings.

## v0.7 Benchmark and Replication Limits

v0.7 is the real benchmark execution and replication release. It moves beyond fixture smoke execution into explicit benchmark records, real or benchmark-like non-fixture benchmark runs, compute environment records, sweeps, ablations, comparison tables, error/slice analysis, low-FPR power checks, and replication packages.

v0.7 must still preserve these limits:

- fixture smoke does not prove benchmark performance
- local benchmark runs are not automatically full benchmark runs
- full benchmark runs may require external data, approval, compute, and human review
- GPU, cluster, and large external dataset workflows must not be required in normal CI
- large downloads must not occur without explicit user approval and cache/license metadata
- failed jobs, missing baselines, underpowered analyses, and negative results must remain visible
- v5 literature, novelty, and closest-prior-work gates must not be weakened
- v6 empirical claim gates must continue to require run records and result artifacts

v0.7 non-goals:

- claiming benchmark success from fixture runs
- silently downloading large datasets
- hiding failed jobs or missing baselines
- treating underpowered low-FPR numbers as strong empirical support
- claiming independent replication when no independent rerun package or review exists

The v0.7 release gate passed for an opt-in real/local public small benchmark canary using the UCI Iris dataset with explicit consent, cached download, artifact-backed metrics and predictions, comparison, error analysis, and replication package verification. This is not a broad benchmark suite, a GPU/cluster validation, or independent replication.

If no real or benchmark-like non-fixture run exists in a future release candidate, the v0.7 release gate should mark real benchmark validation incomplete.

## v0.8 Manuscript and Artifact-Evaluation Limits

v0.8 adds manuscript, artifact evaluation, and reviewer-rebuttal workflow state. It moves beyond starter paper packages into explicit manuscript projects, claim-to-paper traceability, citation/BibTeX management, venue templates, section-level drafting, figure/table generation from artifacts, artifact evaluation packages, reviewer simulation, rebuttal planning, blinding support, camera-ready checklists, and submission-readiness gates.

v0.8 must still preserve these limits:

- manuscript-ready is not the same as submission-ready
- submission-ready is not the same as venue acceptance
- camera-ready requires explicit post-acceptance metadata and must not be inferred
- a manuscript claim is unsupported unless it links to claim ledger records, evidence, result artifacts, benchmark records, citations, or a visible hypothesis/limitation label
- citation and BibTeX records must come from known paper metadata or user-supplied records
- figures and tables must come from result artifacts, benchmark comparison state, statistical analysis, or explicit conceptual placeholders
- artifact evaluation packages are only as complete as the underlying replication and workspace state
- reviewer simulation is diagnostic and does not predict acceptance
- rebuttal plans must answer objections with evidence, manuscript changes, experiments, or concessions
- double-blind support can reduce deanonymization risk, but it cannot guarantee anonymity
- dashboards make blockers inspectable, but they are not readiness certificates
- normal CI must not require LaTeX, live sources, live LLM calls, GPUs, clusters, or large downloads

v0.8 non-goals:

- fabricating results, citations, BibTeX, DOIs, arXiv IDs, venues, or reviewer responses
- marking a manuscript submission-ready when novelty, result, reproducibility, artifact, citation, blinding, or human-review gates fail
- claiming venue acceptance
- requiring LaTeX installation in CI
- hiding negative results, failed experiments, missing baselines, failed jobs, failed replication attempts, or artifact-evaluation gaps
- weakening v5 literature gates, v6 empirical gates, or v7 benchmark/replication gates

The v0.8 workflow should make incomplete manuscripts safer to review by labeling blockers clearly. It does not make a paper publishable by formatting it.

## v0.9 External Pilot and v1-Readiness Limits

v0.9 is the external pilot and v1-readiness release. It moves beyond fixture validation by requiring one real end-to-end topic, but it still does not prove that GapForge can produce publishable research on demand.

v0.9 must still preserve these limits:

- one external pilot is not broad product validation
- a defensible direction is not publication readiness
- an evidence-backed refusal is a valid outcome and must not be treated as product failure by itself
- live literature coverage can still miss prior work
- source outages, rate limits, incomplete metadata, and unavailable full text remain material risks
- closest-prior-work review reduces novelty risk but does not guarantee novelty
- small real runs may be underpowered and must not be overstated
- fixture-only runs validate workflow mechanics only and cannot count as empirical success
- artifact packages are only as complete as their recorded workspaces, manifests, data access, and reproducibility state
- reviewer simulation remains diagnostic and cannot substitute for external feedback
- external pilot feedback is useful evidence, not venue acceptance or market validation
- v1 readiness is a separate gate and cannot be inferred from a successful manuscript draft or pilot run

v0.9 non-goals:

- forcing a research idea when novelty is weak
- claiming real publication readiness unless all gates pass
- fabricating experiments, citations, reviewers, artifact contents, or missing data
- counting fixture-only results as real empirical success
- weakening release gates to make the external pilot pass
- calling v1 before the v1 readiness gate passes

The recommended v0.9 pilot topic is `low false-positive collusion detection in LLM multi-agent systems`. If the pilot ends in refusal, release notes should treat the refusal as successful only when the refusal is backed by live search records, closest-prior-work review, human quality review, and clear next evidence requirements.

## v0.9.1 Migration Remediation Limits

v0.9.0 was not v1-ready because the migration/backward compatibility audit failed. v0.9.1 fixes that blocker by adding historical fixtures, versioned migrators, backup snapshots, compatibility audit v2, and v1 readiness wiring. It does not prove publication readiness, broad external product validation, or migration of every private local artifact.

Important limits:

- migration does not regenerate missing PDFs, datasets, transcripts, prompt packs, caches, dashboards, or task outputs
- ignored/generated unsafe local artifacts can remain warnings when they are not curated release evidence
- missing artifact references remain visible warnings unless the referenced artifact is required curated evidence
- unknown legacy fields are preserved under `_compatibility.unknown_fields` when practical, but ambiguous protected data still blocks
- failed migrations must be repaired from backups or explicit migrator rules, not ignored
- v1 must not be claimed until `gapforge v1-readiness --write-report --json` passes

## v2 Idea Discovery Engine Limits

v2 is the Idea Discovery Engine release line. It should actively search for defensible research ideas instead of evaluating only the first obvious idea.

v2 must still preserve these limits:

- active search does not guarantee that a good idea exists
- topic portfolios can miss important subfields, venues, or source families
- idea candidates are provisional search artifacts, not research directions, manuscripts, or publication claims
- idea mutation can create more variants without creating novelty
- constructive gap creation can propose useful frames, but every frame still needs closest-prior-work review
- cross-domain transfer can be suggestive without being novel, feasible, or accepted by either domain
- Codex/GPT-5.4 synthesis tasks remain untrusted until schema-valid, evidence-grounded, imported, and reviewed
- idea tournaments rank candidates under chosen criteria, but ranking does not prove novelty or feasibility
- human preference feedback can steer search but cannot waive evidence gates
- idea yield metrics can diagnose search productivity but cannot prove research quality by themselves
- research agenda fallback is an honest no-accepted-idea outcome, not a successful idea-discovery claim
- the v2 release gate must fail unless at least one idea candidate is accepted or explicit idea-discovery failure is recorded for v2.0.1 or v2.1 planning

v2 non-goals:

- weakening evidence gates
- inventing citations, datasets, baselines, metrics, or results
- forcing a generic idea to pass
- treating speculative seeds as paper-ready
- removing correct refusal as a possible outcome
- bypassing human review
- using candidate volume as a proxy for quality

An accepted v2 idea candidate means the candidate survived portfolio search, novelty and counterevidence review, feasibility review, tournament comparison, and human review for a stated scope. It does not mean the idea is empirically proven, manuscript-ready, submission-ready, or publishable.

Current operational limits:

- `seed` ideas are allowed to be incomplete and risky; scripts and reports must not present them as accepted.
- Human feedback can up-rank, down-rank, reject, request mutation, request search, or accept a candidate, but acceptance still requires novelty, evidence, and release-gate checks.
- Codex/GPT-5.4 task packs can propose patches only. Import validation must reject fake citations, fake results, generic ideas, unresolved evidence links, and unsupported strong novelty.
- Cross-domain transfer without supporting evidence is a search request, not an idea candidate.
- Agenda-only fallback is honest incompleteness for v2.0 unless explicitly allowed with warning release notes.

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

The follow-up v0.5 verification pass completed live-literature quality acceptance locally. `gapforge v5-release-gate --write-report --json` passed after two campaigns were accepted for research quality: one experiment-ready live-literature smoke campaign and one conservative refusal campaign. This validates the v0.5 gate and workflow behavior, but it still does not prove exhaustive literature review, broad expert acceptance, or complete field coverage.

The v0.6 release pass completed fixture experiment execution acceptance locally. `gapforge v6-release-gate --write-report --json` passed with successful fixture execution, failed-path preservation, parsed result artifacts, artifact-backed empirical claims, reproducibility checks, empirical review, and paper package v2 export. This validates empirical workflow mechanics, not real benchmark performance or independent replication.

The v0.7 release pass completed fixture benchmark and opt-in real/local public benchmark acceptance locally on May 7, 2026. `gapforge v7-release-gate --write-report --json --claim-real` passed for a small UCI Iris canary with explicit dataset consent and replication package verification. This validates the benchmark and replication path, not broad benchmark coverage, SOTA performance, GPU/cluster execution, or independent third-party reproduction.

v0.8 deterministic fixtures and release-gate mechanics validate the manuscript workflow behavior offline. They do not prove that any real manuscript is novel, accepted, independently reproduced, double-blind safe, or venue-ready without the recorded evidence and human review required by the gate.

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
