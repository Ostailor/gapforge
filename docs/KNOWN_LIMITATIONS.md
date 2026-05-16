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

## v2.1 Selected Idea Execution Limits

v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. v2.1 executes that selected idea as the Selected Idea Execution release. It should turn the accepted v2.0 candidate into a benchmark artifact path, not into a final scientific claim.

The synthetic smoke benchmark is not a final research result. Low-FPR claims require power, benchmark validity limitations remain open, and next steps toward pilot/main benchmark must be visible before any stronger claim is made.

v2.1 must still preserve these limits:

- selected idea execution does not reopen idea discovery by default
- benchmark scaffolding is not publication readiness
- a benchmark specification is not an executed benchmark
- a smoke run validates wiring and artifact persistence only
- synthetic fixtures do not prove real-world collusion benchmark validity
- honest-agent and collusive-agent distributions are design assumptions until externally reviewed
- low-FPR specificity estimates require adequate sample size, sequential correction, and uncertainty reporting before supporting strong claims
- baseline monitors must be reported honestly, including weak or failed baselines
- result analysis must derive from recorded artifacts, not generated prose
- manuscript package updates must label smoke outputs, missing evidence, and reviewer objections
- v1 prior-work gates and v2 accepted-candidate provenance must not be weakened to make execution look easier

v2.1 non-goals:

- claiming final scientific results from smoke runs
- claiming synthetic fixture validity for real deployments
- inventing datasets, baselines, metrics, citations, reviewer feedback, or empirical results
- treating a runnable benchmark path as evidence of monitor superiority
- marking the manuscript submission-ready without traceability, result artifacts, critique resolution, and human review
- silently replacing the selected v2.0 idea with a different idea

The v2.1 release gate should require a runnable smoke benchmark path with generated tasks, baseline monitor execution, sequential specificity metrics, result artifacts, analysis, critique, and manuscript package updates. If the smoke path is missing, v2.1 is incomplete.

## v2.2 Pilot-Scale Benchmark Study Limits

v2.2 is the Pilot-Scale Benchmark Study release for the locked selected idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. It moves beyond v2.1 smoke maturity, but it still does not turn synthetic pilot data into deployment evidence or main benchmark maturity.

v2.2 must still preserve these limits:

- a pilot run is exploratory unless the power report supports the specific claim being made
- synthetic pilot traces are not real deployment traces
- expanded honest-agent and collusive-agent distributions are still design assumptions until externally reviewed
- hard-negative coverage can expose false positives but cannot prove all benign coordination is covered
- low-FPR claims require adequate negative counts, sequential correction, and uncertainty reporting
- `alpha=0.001` operational specificity must not be claimed unless the sample size and corrected interval support it
- baseline monitors remain comparisons with declared assumptions, not proof of SOTA scientific strength
- prior-work recall and related-work matrix attachment remain required before publication-readiness claims
- reviewer blockers must be resolved with artifacts or preserved as visible warnings
- pilot manuscript packages must distinguish smoke, pilot, and main benchmark maturity

v2.2 non-goals:

- claiming deployment validity
- treating synthetic pilot data as real-world benchmark validation
- hiding unresolved reviewer blockers
- weakening low-FPR power checks
- converting an underpowered pilot into a main benchmark claim
- claiming publication readiness while prior-work, related-work, sample-size, baseline, or reviewer gates remain incomplete

The v2.2 release gate should require a locked pilot manifest, artifact-backed pilot results, full baseline execution or explicit baseline blockers, sequential low-FPR analysis with uncertainty, prior-work attachment status, reviewer-blocker classification, and overclaim prevention. If only smoke artifacts exist, v2.2 is incomplete.

v2.2 dashboards and API wrappers make pilot status easier to inspect and script, but they do not change the evidence standard. A green dashboard page means the artifact is present or parsed; it is not a deployment, publication, or main-benchmark certificate. v2.3 remains necessary for main-scale negative counts, externally reviewed scenario realism, stronger baseline comparisons, and any publication-readiness claim.

## v2.3 Main-Scale Benchmark and Publication-Readiness Limits

v2.3 is the Main-Scale Benchmark and Publication-Readiness Upgrade for the locked selected idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. It directly addresses v2.2 blockers, but it still cannot turn inadequate evidence into deployment validity or publication readiness.

v2.3 must still preserve these limits:

- a main-scale sample-size plan is required before main outcomes are inspected
- `alpha=0.001` must be powered or explicitly dropped from claims
- an underpowered alpha target remains a blocker even if observed false positives are low
- synthetic main-scale traces are still synthetic and do not prove deployment validity
- hard-negative coverage can improve stress testing but cannot prove all benign coordination is covered
- stronger baselines must be grounded in prior work or explicitly labeled as limited
- missing or infeasible baselines must remain visible in reports
- real prior-work records are required for required related-work categories
- related-work matrix completion is required before publication-readiness claims
- closest-prior-work search reduces novelty risk but does not prove exhaustive coverage
- publication-readiness claims require a reviewer panel with no fatal blockers
- manuscript package polish cannot substitute for main-run artifacts, citations, replication package, or human review

v2.3 non-goals:

- claiming deployment validity from synthetic evidence
- claiming `alpha=0.001` while underpowered
- hiding missing real prior work
- treating category labels or search queries as citations
- weakening v2.2 reviewer blockers to pass v2.3
- claiming monitor superiority without powered comparisons and credible baselines
- calling the manuscript publication-ready while fatal reviewer blockers remain
- treating an explicit no-go as a failure to document; a no-go is the correct outcome when evidence remains inadequate

The v2.3 release gate should require either main-scale readiness or an explicit no-go. If the main dataset, main run, related-work records, baseline suite, or publication panel are incomplete, the release must preserve those gaps and narrow or block claims.

## v2.4 Related Work Completion and Publication-Readiness Remediation Limits

v2.4 is the remediation release after the v2.3 `revise_benchmark` outcome for `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. v2.3 completed the synthetic main benchmark workflow, but publication readiness remained blocked because required related-work categories had no real attached paper records.

v2.4 must still preserve these limits:

- related-work search campaigns can reduce coverage risk but cannot prove exhaustive search
- every required related-work category needs real traceable paper records or an explicit incomplete/impossible status
- fallback-only records, generated citations, and category labels do not count as related-work coverage
- closest-prior-work review can weaken or defeat novelty claims and must not be hidden
- contribution claims must be softened when prior work overlaps the benchmark, protocol, metric, baseline, or threat model
- benchmark positioning against prior work does not turn synthetic evidence into deployment validity
- the v2.3 synthetic/deployment limitation remains active
- publication-readiness claims require completed related-work, novelty, citation, manuscript, and reviewer gates

v2.4 non-goals:

- claiming publication readiness while related work remains fallback-only
- inventing citations, identifiers, venues, authors, or BibTeX metadata
- hiding closest prior work that weakens novelty
- claiming real-world deployment validity
- weakening the v2.3 synthetic benchmark limitation
- treating an explicit revise or no-go as a failure to document

If required categories remain incomplete, v2.4 must produce a visible `revise_benchmark`, `no_go_related_work`, `no_go_novelty`, or `no_go_publication` decision instead of publication-ready language.

## v2.5 Real Benchmark Grounding, Venue-Style Paper, and OpenReview Reviewer Training Limits

v2.5 is the hardening release after the v2.4 `publication_candidate` outcome for `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. It adds real benchmark grounding, venue-style manuscript packaging, and OpenReview-calibrated reviewer critique, but it still cannot turn a bounded benchmark/protocol package into venue acceptance or deployment validity.

v2.5 must still preserve these limits:

- real benchmark grounding is separate from synthetic benchmark scaffolding
- a known or respected dataset does not prove the selected benchmark protocol is valid
- vetted benchmark adapters support only the scope justified by their source labels, splits, license, and mapping rules
- adapter results cannot be generalized to real-world collusion deployment without additional evidence
- public paper TeX/source may be inspected only for allowed structure, style, and format analysis
- venue style is not copied prose, copied captions, copied equations, copied distinctive macros, or copied reviewer responses
- OpenReview-style reviewer modeling calibrates critique and severity, not truth
- reviewer models and rubrics can miss objections, overstate concerns, or hallucinate unless checked
- simulated review scores do not predict top-conference acceptance
- harsh reviewer objections must remain visible unless resolved with evidence, manuscript changes, narrowed claims, or explicit concessions

v2.5 non-goals:

- claiming benchmark validity merely from using a known dataset
- claiming top-conference acceptance, likely acceptance, or camera-ready status
- copying copyrighted paper text or disallowed source material
- training reviewer models that fabricate citations, datasets, baselines, metrics, or results
- hiding severe reviewer objections to make the paper look ready
- weakening v2.4 related-work, novelty, synthetic/deployment, citation, or reviewer gates

If no vetted benchmark adapter, venue-style manuscript package, or OpenReview-calibrated reviewer pass exists, v2.5 must end in revise or no-go language instead of review-candidate language.

## v2.6 Drastic Review Remediation and Real Artifact Package Limits

v2.6 is the remediation release after the v2.5 `revise_for_reviews` outcome for `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`. It directly addresses the v2.5 drastic-review fatal blockers: missing loadable related-work matrix and missing loadable artifact evaluation package.

v2.6 must still preserve these limits:

- recovering a related-work matrix does not prove exhaustive literature coverage
- a related-work matrix is useful only when it loads, references real traceable paper records, and preserves missing or weak categories
- related-work prose cannot substitute for an auditable matrix
- recovering or creating an artifact package does not create new experiments, results, benchmarks, or independent reproduction
- an artifact package is loadable only when its manifest and reviewer files resolve to recorded state or explicit blockers
- package directories, broken manifests, and invented file references do not count as artifact package remediation
- the v2.5 synthetic benchmark fixture remains adapter plumbing and workflow evidence, not real collusion benchmark grounding
- a real external/public benchmark adapter can support only the scope justified by source labels, splits, access, license, and mapping rules
- benchmark no-fit is an honest outcome, not external validity evidence
- venue-style manuscript revision cannot hide remaining fatal blockers
- drastic review reruns must preserve harsh standards and evidence labels
- top-conference readiness decisions are readiness classifications, not acceptance predictions or camera-ready status

v2.6 non-goals:

- claiming acceptance, likely acceptance, or camera-ready readiness
- hiding or softening v2.5 fatal reviewer blockers without loadable evidence
- treating synthetic fixture benchmarks as real benchmark grounding
- inventing artifact package files, commands, hashes, datasets, results, or reviewer checklists
- inventing citations, reviewers, review outcomes, baselines, or benchmark labels
- copying paper prose from venue-style sources
- weakening drastic reviewer standards to obtain a better decision
- claiming real collusion benchmark validity unless the benchmark mapping supports it

If either the selected related-work matrix or artifact package remains missing or unloadable, v2.6 cannot pass publication readiness. The strongest allowed outcomes are `revise_for_reviews`, `benchmark_no_fit`, or `no_go`, depending on the remaining evidence and blockers.

## v2.6.1 Eval Recalibration Limits

v2.6.1 recognizes that current eval is not proof of top-conference quality. Existing eval scores are useful for regression, safety, and workflow checks, but they can overstate readiness if interpreted as paper-quality evidence.

v2.6.1 must still preserve these limits:

- regression evals protect fixture correctness, schema/load/save behavior, release-gate behavior, and known blocker preservation
- safety evals reject fake citations, fake results, copied prose, unsupported novelty, and hidden missing categories
- workflow evals confirm artifact existence, matrix/package loading, reviewer reruns, and revision-package generation
- paper-quality evals must be reported separately from workflow evals
- a workflow pass does not imply novelty strength, baseline strength, benchmark fit, statistical adequacy, related-work completeness, manuscript persuasiveness, or top-conference readiness
- harsh reviewer likely score remains diagnostic and uncertain, not an acceptance prediction
- `workshop_candidate` and `borderline_reject` can coexist with passing regression, safety, and workflow checks

v2.6.1 non-goals:

- claiming top-conference readiness from fixture or workflow eval scores
- hiding paper-quality blockers behind a green release gate
- treating artifact loadability as manuscript persuasiveness
- treating safety compliance as reviewer enthusiasm
- weakening drastic-review signals to align with existing eval scores

Future release gates should report paper-quality status separately. If paper quality remains `borderline_reject`, `reject_likely`, or `not_ready`, release notes must say so even when regression, safety, and workflow layers pass.

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
