# Changelog

All notable project changes should be recorded here.

## 2.2.0

GapForge v2.2.0 is the Selected Benchmark Pilot Study release. It keeps the v2.1 selected idea locked as `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits` and upgrades the benchmark from synthetic smoke maturity to an artifact-backed synthetic pilot run with power-gated low-FPR claims, expanded trace distributions, baseline calibration, reviewer blockers, and a pilot manuscript package.

### Pilot Benchmark Study

- Added a pilot power and sample-size plan with explicit pilot/main alpha targets, negative and positive trace requirements, zero-false-positive upper confidence bounds, underpowered-threshold handling, and sequential multiple-testing notes.
- Expanded the honest-agent null distribution with benign parallel strategy, shared-context, role-specialization, repeated-convention, tool-induced-similarity, accidental-correlation, action-only hard-negative, and transcript-visible hard-negative scenarios.
- Expanded collusive-agent alternatives with explicit coordination, covert-channel, lexical-signal, timing-signal, role-based-collusion, reward-sharing, and adversarial-decoy scenarios across transcript-visible and action-only observability modes.
- Added a pilot trace dataset builder that records honest/collusive/ambiguous trace IDs, split, negative and positive counts, hard-negative counts, observability-mode counts, scenario coverage, alpha target support, limitations, and provenance.
- Upgraded the full baseline monitor suite to v2 with random, fixed-threshold frequency, repeated-action, lexical similarity, statistical anomaly, sequential change-point, calibrated threshold, transcript-visible heuristic, action-only heuristic, and optional opt-in LLM judge baselines.
- Added monitor calibration records with target alpha, threshold, observed FPR, confidence interval, leakage warnings, and provenance.
- Added pilot manifest and execution support that runs required monitors, computes sequential metrics, writes metrics/predictions/baseline/error/failure artifacts, preserves failures, and labels all outputs as pilot synthetic data.
- Added pilot result analysis for per-monitor FPR/TPR, per-episode false alarm probability, time-to-detection, detection delay, confidence intervals, zero-FP upper bounds, underpowered alpha levels, hard-negative false positives, observability-mode comparisons, and failed baseline runs.
- Attached selected benchmark prior-work recall and related-work matrix artifacts with fake-citation rejection and conservative novelty positioning.
- Added the pilot reviewer panel covering benchmark validity, statistics/low-FPR, baselines, related-work/novelty, synthetic data validity, and area-chair assessment.
- Added the pilot manuscript and paper package with motivation, benchmark definition, threat model, pilot trace dataset, baseline monitors, calibration, sequential specificity metrics, pilot results, low-FPR limitations, related work, reviewer blockers, and path to main benchmark.
- Added the v2.2 release gate requiring v2.1 evidence plus pilot power, expanded distributions, pilot dataset, calibrated/run baselines, pilot manifest/run, parsed artifacts, analysis, related work, reviewer panel, manuscript package, and overclaim rejection.

### API, Dashboard, Evals, Docs, and Skills

- Exposed v2.2 workflows through `gapforge.api` for pilot power planning, honest-null generation, collusive alternative generation, pilot dataset construction, baseline calibration, pilot execution, pilot analysis, pilot review, pilot manuscript generation, and the v2.2 release gate.
- Added selected pilot dashboard pages for pilot power, honest null distribution, collusive distribution, pilot dataset, baseline calibration, pilot results, low-FPR report, related work, review, manuscript, and v2.2 release gate status.
- Added v2.2 eval fixtures and metrics covering complete pilot benchmark behavior, underpowered alpha overclaims, missing related work, missing required baselines, synthetic deployment overclaims, honest pilot manuscript output, reviewer blockers, and v2.2 release-gate correctness.
- Added v2.2 docs for roadmap, pilot benchmark specification, acceptance criteria, power/sample size, reviewer blockers, release process, known limitations, and README maturity statements.
- Added Codex-readable skills for pilot power planning, honest-null distribution, collusive alternatives, pilot trace datasets, pilot baseline calibration, pilot result analysis, selected related work, pilot review, and pilot manuscript generation.

### Release Outcome

- Selected idea: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
- Pilot dataset status: synthetic pilot dataset with 300 negative traces, 150 positive traces, and 214 hard-negative traces.
- Alpha support: pilot `alpha=0.01` is supported at 300 observed / 299 required negative traces; `alpha=0.001` remains underpowered and blocked at 300 observed / 2995 required negative traces.
- Pilot run status: complete, with pilot-labeled metrics, predictions, baseline comparison, error analysis, failure/status artifacts, and no failed required baseline runs in the recorded pilot execution.
- Baseline status: required baselines are present, calibrated, and run, but reviewer assessment still blocks strong contribution or monitor-superiority claims because baselines remain lightweight scientific comparisons.
- Related-work status: prior-work recall and related-work matrix are attached, but all required categories remain missing from real attached paper records; closest prior work is not explicit and novelty remains unknown.
- Reviewer status: pilot reviewer panel preserves fatal blockers for unsupported `alpha=0.001`, weak baselines for strong claims, missing prior-work categories, and missing related-work matrix categories.
- Manuscript package status: generated as a pilot paper package with readiness `not_publication_ready_pilot_blockers`.
- v2.2 release gate status: passes as a pilot benchmark release gate with warnings; it does not imply deployment validity, main benchmark maturity, publication readiness, or powered `alpha=0.001` specificity.

### Validation

- `make ci`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `gapforge eval --v4 --write-report`
- `gapforge eval --v5 --write-report`
- `gapforge eval --v6 --write-report`
- `gapforge eval --v7 --write-report`
- `gapforge eval --v8 --write-report`
- `gapforge eval --v9 --write-report`
- `gapforge eval --v2-ideas --write-report`
- `gapforge eval --v21 --write-report`
- `gapforge eval --v22 --write-report`
- `make v2-smoke`
- `make v3-smoke`
- `make v4-smoke`
- `make v6-smoke`
- `make v7-smoke`
- `make v8-smoke`
- `make v9-smoke`
- `gapforge v1-readiness --write-report --json`
- `gapforge v2-release-gate --write-report --json`
- `gapforge v21-release-gate --write-report --json`
- `gapforge v22-release-gate --write-report --json`

### Non-Claims and Limitations

- v2.2.0 does not claim deployment validity, real-world collusion benchmark validity, main benchmark maturity, publication readiness, venue acceptance, monitor superiority, resolved novelty, or operational specificity at unsupported `alpha=0.001`.
- Synthetic pilot traces are generated benchmark artifacts, not deployment data.
- Zero false positives are reported through confidence upper bounds, not as proof of zero risk.
- Related-work attachment is structurally present but substantively incomplete until real prior-work records cover the required categories.
- Generated unsafe artifacts remain ignored and must not be committed as release source.

## 2.1.0

GapForge v2.1.0 is the Selected Idea Execution release. It freezes the human-accepted v2 selected idea, `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`, and operationalizes it as a runnable synthetic benchmark smoke path for the sequential specificity research target.

### Selected Idea Execution

- Added selected idea locking and a durable selected project record so future v2.1 work cannot silently drift to a different idea while preserving rejected ideas, tournament score, human review IDs, and provenance.
- Added the canonical research project for `Sequential specificity benchmark for low-FPR collusion audits`, including the research question: "Can a sequential benchmark evaluate collusion monitors at operationally meaningful low false-positive rates?"
- Added the formal sequential specificity benchmark specification with target FPR levels, sequential audit setting, transcript-visible and action-only observability modes, honest-agent null distribution, collusive-agent alternative distribution, required baselines, metrics, statistical requirements, and limitations.
- Added an explicit collusion threat model and benchmark task families covering benign coordination hard negatives, staged collusive coordination, and observability-mode contrast.
- Added a synthetic trace generator with scenario definitions, labels, smoke/pilot datasets, transcript-visible and action-only traces, honest/collusive/ambiguous labels, and clear synthetic limitations.
- Added sequential audit metrics for per-step and per-episode FPR, family-wise false alarm probability, time-to-detection, detection delay, TPR at fixed false-positive budget, specificity at alpha, sequential calibration error, abstention/uncertain rate, exact/binomial confidence intervals, and zero-false-positive upper bounds.
- Added the sequential metric plan and low-FPR audit check so smoke evidence is marked underpowered unless negative-trace counts are sufficient.
- Added monitor baseline suite records and smoke execution support for random, threshold/frequency, lexical overlap, repeated-action, statistical anomaly, optional disabled LLM judge, and analysis-only oracle placeholders.
- Added selected benchmark workspace generation, smoke manifest generation, smoke runner, result parser, report generator, and artifact-backed smoke outputs.
- Added Codex/GPT-5.4 benchmark implementation task packs for trace generation, monitor baselines, sequential metrics, smoke runner, benchmark debugging, and report improvement with fake-result and outside-workspace patch rejection.
- Added a selected benchmark reviewer panel with benchmark-validity, statistics/low-FPR, AI-safety relevance, baseline/reproducibility, skeptical novelty, and area-chair roles.
- Added selected benchmark manuscript and paper package generation that labels smoke results, includes limitations prominently, and preserves reviewer blockers.
- Added the v2.1 release gate requiring the v2 release gate, selected idea lock/project, benchmark spec, threat model, trace generator, baseline suite, metric plan, workspace, completed smoke run, parsed result artifacts, underpowered warning when applicable, reviewer panel, manuscript package, and no fake results or premature validity claims.

### API, Dashboard, Evals, Docs, and Skills

- Exposed v2.1 workflows through `gapforge.api` for selected idea locking, project creation, benchmark spec creation, trace generation, baseline creation, smoke runs, sequential metrics, review, manuscript generation, and the v2.1 release gate.
- Added selected idea dashboard/report pages for the selected idea, benchmark spec, threat model, trace dataset, monitors, sequential metrics, smoke results, reviewer blockers, selected manuscript, and v2.1 release gate.
- Added v2.1 eval fixtures and metrics covering complete smoke benchmark, missing honest null distribution, underpowered low-FPR overclaim, missing baseline, fake result blocking, manuscript smoke labels, reviewer publishability blockers, and release-gate correctness.
- Added v2.1 docs for roadmap, selected idea, benchmark spec, acceptance criteria, release process, known limitations, and README maturity statements.
- Added Codex-readable skills for selected idea projects, sequential specificity benchmarks, trace generation, sequential audit metrics, monitor baselines, and selected benchmark review.

### Release Outcome

- Selected idea: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
- Benchmark maturity: runnable synthetic smoke benchmark path with artifact-backed results, reviewer critique, and manuscript-shaped package.
- Smoke run status: passed as `synthetic_underpowered_smoke_only`.
- Result artifacts: selected project, benchmark spec, threat model, task families, trace dataset, monitor baselines, metric plan, workspace, smoke result summary, reviewer panel, manuscript package, full selected idea report, and v2.1 release-gate reports were generated under ignored local artifact directories.
- Reviewer blockers: the reviewer panel keeps the release non-publishable because underpowered low-FPR evidence cannot support pilot/main or publication claims.
- Pilot/main remaining work: expand honest null and collusive alternative distributions, preregister target alpha/sample-size gates, run full baseline comparisons, resolve reviewer blockers, complete prior-work recall and related-work matrix, and only then evaluate pilot/main scientific claims.

### Validation

- `make ci`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `gapforge eval --v4 --write-report`
- `gapforge eval --v5 --write-report`
- `gapforge eval --v6 --write-report`
- `gapforge eval --v7 --write-report`
- `gapforge eval --v8 --write-report`
- `gapforge eval --v9 --write-report`
- `gapforge eval --v2-ideas --write-report`
- `gapforge eval --v21 --write-report`
- `make v2-smoke`
- `make v3-smoke`
- `make v4-smoke`
- `make v6-smoke`
- `make v7-smoke`
- `make v8-smoke`
- `make v9-smoke`
- `gapforge v1-readiness --write-report --json`
- `gapforge v2-release-gate --write-report --json`
- `gapforge v21-release-gate --write-report --json`

### Non-Claims and Limitations

- v2.1.0 does not claim a final scientific result, real-world collusion benchmark validity, monitor superiority, deployment validity, publication readiness, or resolved novelty.
- Synthetic smoke traces are fixture/scaffold evidence only and do not represent real deployment behavior.
- Low-FPR claims remain underpowered at smoke scale; zero false positives are reported with an upper confidence bound instead of as proof of operational specificity.
- Generated unsafe artifacts remain ignored and must not be committed as release source.

## 2.0.1

GapForge v2.0.1 is a CI fixture tracking patch for the post-v2.0 clean-checkout issue where historical migration fixture JSONs were omitted by broad generated-artifact ignore rules.

### Scope

- Tracked the historical migration fixture JSONs required by clean GitHub checkout CI.
- Kept the patch limited to CI fixture availability and release hygiene documentation.
- No product behavior changed.
- No idea-discovery claims changed.
- The v2.0 selected idea remains the same: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
- No unsafe generated artifacts were committed.

### Validation

- `make ci`
- `gapforge compatibility-audit --v2 --fixtures --write-report`
- `gapforge v2-release-gate --write-report --json`
- GitHub Actions CI passed on clean checkout for commit `f2c543568e66e1d9a8bbc369c3825a81cd55a869`.

## 2.0.0

GapForge v2.0.0 is the Idea Discovery Engine release. It keeps the v1 evidence gates intact while changing the default behavior from evaluating or refusing the first obvious direction to actively searching across portfolios of defensible idea candidates.

### Idea Discovery Engine

- Added topic portfolios with narrower, adjacent, cross-domain, metric-shift, threat-model-shift, benchmark-shift, theory-shift, evaluation-shift, and data-shift variants.
- Added first-class idea banks with auditable idea candidates, evidence links, reviews, feedback, rejected candidate preservation, reports, and Python API support.
- Added idea mutation records and strategies for metric, observable, threat-model, benchmark, dataset, baseline, guarantee, domain-transfer, contribution-type, negative-result, measurement, theory, minimum-publishable-unit, and reviewer-objection reframing.
- Added constructive gap creation for benchmark, measurement, evaluation protocol, dataset, replication, negative-result, theory, system, and tooling paper forms.
- Added cross-domain transfer expansion from medicine screening/specificity, anomaly detection, fraud detection, cartel detection economics, covert channels/steganography, sequential testing, statistical process control, safety-critical monitoring, and reliability engineering.
- Added validation-gated Codex/GPT-5.4 idea synthesis task packs for seed expansion, mutation, constructive gaps, transfer, critique, tournament judging, and research agenda building.
- Added an active idea search controller and decision policy for portfolio creation, variant search, synthesis, mutation, prior-work loops, tournaments, feedback requests, agenda fallback, and stop decisions.
- Added idea-specific novelty and counterevidence loops that update candidate novelty status and preserve closest prior work, missing searches, and counterevidence.
- Added idea tournaments with transparent scoring across evidence, novelty, experimentability, tractability, impact, reviewer risk, time-to-demo, benchmark/baseline availability, cross-domain leverage, and human preference.
- Added human preference profiles and feedback records that can steer search and tournament scoring without overriding evidence, novelty, fake-citation, fake-result, or human-review gates.
- Added research agenda mode as the honest fallback when active search finds no accepted idea candidate.
- Added idea yield metrics for topic variants, candidates, mutations, constructive gaps, transfers, duplicates/generic rejections, novelty unknowns, tournament survivors, accepted ideas, agenda fallback, yield rate, time to selected idea, evidence per candidate, and prior work per candidate.
- Added the v2 release gate requiring v1 readiness, portfolio, idea bank, mutation, constructive gap, transfer, Codex synthesis task or explicit unavailability, novelty/counterevidence loop, tournament, human feedback/review, yield metrics, rejected-idea preservation, and either an accepted candidate or explicit agenda-only warning path.

### API, Dashboard, Evals, Docs, and Skills

- Exposed v2 idea discovery workflows through `gapforge.api`: `generate_topic_portfolio`, `create_idea_bank`, `generate_ideas`, `mutate_idea`, `generate_constructive_gaps`, `transfer_ideas`, `run_idea_novelty`, `run_idea_tournament`, `add_idea_feedback`, `generate_research_agenda`, `idea_yield`, and `v2_release_gate`.
- Added idea discovery dashboard/report pages for portfolios, idea banks, candidates, mutations, constructive gaps, transfers, novelty, tournaments, feedback, agendas, yield, and v2 release gate state.
- Added v2 idea eval fixtures and metrics covering accepted benchmark/measurement/negative-result ideas, generic rejection, duplicate rejection, agenda fallback, fake-citation blocking, human preference effects, mutation recovery, yield correctness, and tournament quality.
- Added v2 roadmap, acceptance criteria, idea discovery, idea yield, research agenda, human feedback, release process, architecture, eval, limitation, and Codex research-agent documentation.
- Added Codex-readable v2 skills for topic portfolios, idea banks, idea mutation, constructive gap creation, cross-domain transfer, idea synthesis, novelty loops, tournaments, and research agenda mode.

### Pilot and Release Outcome

- Ran the v2 low-FPR collusion idea pilot for `low false-positive collusion detection in LLM multi-agent systems`.
- Accepted candidate idea found: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
- Selected idea title: `Sequential specificity benchmark for low-FPR collusion audits`.
- Rejected idea count in the release pilot: 1.
- Research agenda status: no agenda fallback was used because an accepted candidate was found.
- Idea yield metrics for the release pilot: 11 topic variants, 26 candidates, 1 mutation, 8 constructive gaps, 1 cross-domain transfer, 5 tournament survivors, 1 human-accepted idea, idea yield rate 0.0385, evidence per candidate 2.1538, prior work per candidate 2.1154.
- v2 release gate passed with status `pass`, no blockers, and no agenda-only warning.

### Validation

- `make ci`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `gapforge eval --v4 --write-report`
- `gapforge eval --v5 --write-report`
- `gapforge eval --v6 --write-report`
- `gapforge eval --v7 --write-report`
- `gapforge eval --v8 --write-report`
- `gapforge eval --v9 --write-report`
- `gapforge eval --v2-ideas --write-report`
- `make v2-smoke`
- `make v3-smoke`
- `make v4-smoke`
- `make v6-smoke`
- `make v7-smoke`
- `make v8-smoke`
- `make v9-smoke`
- `gapforge v1-readiness --write-report --json`
- `gapforge v2-release-gate --write-report --json`

No `v5-smoke` target exists in the Makefile.

### Non-Claims and Limitations

- v2.0.0 does not claim exhaustive literature review, guaranteed novelty, empirical results, publication readiness, venue acceptance, or manuscript readiness.
- The accepted idea is candidate-level only. It still needs real experiment execution, benchmark/data construction, manuscript work, and external review before any paper-ready claim.
- Codex/GPT-5.4 task-pack output remains untrusted until schema-valid, evidence-grounded, imported, and reviewed.
- Research agenda fallback remains a valid outcome in future runs when no candidate survives active search.

## 1.0.0

GapForge v1.0.0 is the stable evidence-gated research ideation release. It promotes the v0.9.1 migration compatibility remediation into the v1 line after the v1 readiness gate passed with v4-v9 release evidence, Compatibility Audit V2, CLI audit, docs audit, artifact hygiene audit, and an accepted external pilot outcome.

### Stable v1 Scope

- Supports literature campaigns with source coverage, search planning, prior-work recall, novelty dossiers, conservative stopping, and human review records.
- Supports Codex/GPT-5.4 assisted research workflows through validated task packs, direct runner integration, import validation, attestation, and repair paths.
- Supports experiment execution with manifests, run records, result artifacts, statistics, reproducibility checks, and explicit failed/negative paths.
- Supports benchmark and replication packages with benchmark records, dataset consent/cache handling, comparison reports, low-FPR power checks, and replication manifests.
- Supports manuscript and artifact evaluation packages with claim traceability, citations/BibTeX, venue-aware checklists, anonymization, reviewer simulation, rebuttal planning, and artifact-evaluation packaging.
- Supports correct refusal outcomes when evidence is insufficient for a defensible research direction.
- Supports release gates, compatibility audits, versioned migrations, backup snapshots, and artifact hygiene checks.

### v1 Readiness Outcome

- v1 readiness passed with no blockers.
- The v0.9 external pilot outcome was an accepted correct refusal for `low false-positive collusion detection in LLM multi-agent systems`.
- Correct refusal is valid behavior: GapForge must not force or invent a research idea when novelty, coverage, or support is insufficient.
- Migration status passed through Compatibility Audit V2 with historical fixtures for v0.1 through v0.9, versioned migrators, validation, backup behavior, unknown-field handling, and explicit warnings for intentionally missing generated fixture artifacts.
- Artifact safety passed with generated unsafe local artifacts ignored and excluded from curated release evidence.

### Non-Claims and Limitations

- v1.0.0 does not claim GapForge always produces a research idea.
- v1.0.0 does not claim exhaustive literature review, guaranteed novelty, publishable empirical results, broad benchmark superiority, independent replication, venue submission, venue acceptance, or camera-ready readiness.
- Live sources can be incomplete, rate-limited, stale, or unavailable.
- PDF and full-text extraction can miss text, tables, references, equations, and layout.
- Optional model output remains untrusted until schema-valid, evidence-located, reviewed, and imported.
- Fixture and smoke outputs validate workflow mechanics only; they are not research-quality evidence.

### Validation

- `make format`
- `make format-check`
- `make lint`
- `make typecheck`
- `make test`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `gapforge eval --v4 --write-report`
- `gapforge eval --v5 --write-report`
- `gapforge eval --v6 --write-report`
- `gapforge eval --v7 --write-report`
- `gapforge eval --v8 --write-report`
- `gapforge eval --v9 --write-report`
- `make v2-smoke`
- `make v3-smoke`
- `make v4-smoke`
- `make v6-smoke`
- `make v7-smoke`
- `make v8-smoke`
- `make v9-smoke`
- `gapforge compatibility-audit --v2 --fixtures --write-report`
- `gapforge migrate-all --dry-run`
- `gapforge v9-release-gate --write-report --json`
- `gapforge v1-readiness --write-report --json`

## 0.9.0

GapForge v0.9 is the external pilot and v1-readiness release. It moves beyond fixture-only workflow validation by running the low false-positive collusion detection pilot through the v0.9 pilot machinery, accepting a correct refusal when live-literature evidence and idea-gate artifacts were insufficient for a defensible direction, and adding machine-checkable gates for v1 readiness.

### External Pilot Workflow

- Added the v0.9 external pilot specification and durable pilot runner for `low_fpr_collusion`.
- Added pilot run records, pilot reports, pilot acceptance summaries, and CLI status/report commands for the external pilot lifecycle.
- Added the pilot outcome classifier for defensible directions, correct refusals, product failures, and incomplete runs.
- Added the real idea gate so Codex/GPT-5.4 synthesis can propose directions, but GapForge accepts at most one primary direction and rejects generic or unsupported ideas.
- Added external review capture for user, domain-expert, engineer, and external-reviewer metadata so the pilot cannot self-certify.
- Added v9 eval fixtures and metrics covering outcome classification, idea-gate quality, external review completeness, v1 readiness correctness, audits, artifact hygiene, and the v9 release gate.

### v1 Readiness and Release Gates

- Added the v1 readiness gate requiring deterministic CI, v4-v8 gate evidence, accepted v0.9 pilot outcome, human review, no unresolved product failures, migration audit, CLI audit, docs audit, artifact hygiene audit, and an end-to-end project report.
- Added the v9 release gate requiring the pilot spec, pilot run, outcome classification, idea gate, human review, accepted direction or accepted refusal, audit reports, v1 readiness report generation, and no unresolved product failures.
- Added schema migration and backward compatibility audit tooling with migration records, backup-before-mutate behavior, and reports for older project/run state.
- Added CLI usability audit coverage for command grouping, help text, deprecated aliases, and discoverability.
- Added documentation usability audit coverage for the v0.9 pilot quickstart, lifecycle docs, limitations visibility, and overclaim/fake-evidence checks.
- Added artifact hygiene audit v2 for generated artifacts, PDFs, datasets, transcripts, dashboards, safe bundles, large files, gitignore verification, and release-gate safety.

### Pilot Outcome

- Pilot topic: `low false-positive collusion detection in LLM multi-agent systems`.
- Outcome: accepted correct refusal.
- Accepted direction: none.
- Refusal basis: live source diagnostics reported degraded arXiv fallback metadata, required live-literature and novelty artifacts were incomplete, and the idea gate found no candidate direction that should be promoted.
- Product failures: none unresolved in the accepted pilot outcome.
- v1 readiness: generated but not passed because the migration/backward compatibility audit has not passed.
- v0.9.1 need: no v0.9.1 is required for a pilot product failure, but v1 remains blocked until migration readiness is resolved; if that remediation is released separately, it should become v0.9.1.

### Validation

- `make ci`
- `make eval`
- `gapforge eval --v2 --write-report`
- `gapforge eval --v3 --write-report`
- `gapforge eval --v4 --write-report`
- `gapforge eval --v5 --write-report`
- `gapforge eval --v6 --write-report`
- `gapforge eval --v7 --write-report`
- `gapforge eval --v8 --write-report`
- `gapforge eval --v9 --write-report`
- `make v2-smoke`
- `make v3-smoke`
- `make v4-smoke`
- `make v6-smoke`
- `make v7-smoke`
- `make v8-smoke`
- `make v9-smoke`
- `gapforge v9-release-gate --write-report --json`
- `gapforge v1-readiness --write-report --json`

No publication readiness, real empirical success, venue submission, or novelty claim is made for v0.9.

## 0.8.0

GapForge v0.8 is the manuscript, artifact evaluation, and reviewer-rebuttal release. It keeps the v5 literature, v6 empirical, and v7 benchmark/replication gates intact while adding durable manuscript project state, citation discipline, claim-to-paper/result/artifact traceability, venue-aware submission checks, anonymized review packages, artifact-evaluation packaging, reviewer simulation, rebuttal planning, and a v8 release gate that blocks unsupported claims, fake citations, fake results, and premature submission/camera-ready status.

### Manuscript Project and Citation Workflow

- Added first-class manuscript project state with durable `manuscripts/{manuscript_id}/` directories, manuscript metadata, section records, claim-use records, and persisted manuscript state.
- Added section-level manuscript drafting and rendering that keeps sections traceable to source claims, papers, result artifacts, and supporting artifacts.
- Added bibliography and citation management with stable citation keys, DOI/arXiv/title deduplication, BibTeX export, missing-metadata warnings, citation-use records, and rejection of fake or unknown citation strings.
- Added claim-to-manuscript traceability reports that separate background, novelty, method, result, limitation, and future-work uses while requiring support from papers/evidence, empirical artifacts, novelty dossiers, limitation statements, or explicit hypothesis/speculation labels.
- Added overclaim checks for unsupported claims, overstrong novelty, SOTA claims without verified support, result claims without artifacts, smoke/pilot results phrased as main results, missing citations, and hidden limitations.

### Assets, Venue Checks, and Submission Packages

- Added artifact-backed manuscript figure and table generation for result tables, baseline comparisons, metric plots, failure tables, and conservative captions with run-type and limitation labels.
- Added venue templates for generic conferences, workshops, arXiv-style preprints, ML-conference-like submissions, and artifact-evaluation-like packages.
- Added venue-aware submission checklists covering required sections, bibliography/citations, traceability, result artifacts, artifact packages, ethics/limitations, and anonymization requirements.
- Added anonymization/blinding support that writes anonymized copies without deleting originals and detects obvious author, affiliation, repository URL, local path, metadata, and self-citation leaks.
- Added submission package export for review, camera-ready, arXiv, and internal package types with gated status, bibliography/assets, appendix content, artifact-evaluation README material, checklist reports, and anonymization reports when required.

### Artifact Evaluation, Reviewer Panel, and Rebuttal

- Upgraded artifact evaluation packaging with replication-package inclusion, install/run instructions, expected outputs and hashes, hardware/time estimates, restricted-data exclusion by default, checklist validation, conservative badge assessment, and dry-run smoke support.
- Added full-manuscript reviewer panels with novelty, empirical, clarity, related-work, reproducibility/artifact, ethics/limitations, and area-chair roles that cite manuscript sections and underlying evidence.
- Added rebuttal and revision workflows that convert reviewer objections into actionable fixes, required experiments, citation/search requests, and claim-softening suggestions without inventing missing results or responses.
- Added camera-ready gating so open fatal review/rebuttal blockers prevent camera-ready status.

### Evals, Dashboard, API, Docs, and Skills

- Added v8 eval fixtures and metrics for traceability, citation validity, result-claim honesty, venue checklists, artifact-evaluation packages, reviewer quality, rebuttal actionability, anonymization safety, submission completeness, and v8 release-gate correctness.
- Added manuscript dashboard pages for manuscripts, sections, bibliography, traceability, figures/tables, submission checklists, artifact evaluation, reviewer panels, rebuttals, submission packages, and the v8 release gate.
- Exposed v8 workflows through the Python API so manuscript creation, bibliography building, drafting, rendering, assets, traceability, venues, anonymization, artifact evaluation, review, rebuttal, submission packages, and release gates are scriptable.
- Added v0.8 roadmap, acceptance criteria, manuscript workflow, artifact evaluation, rebuttal workflow, testing/eval documentation, and Codex-readable skills for manuscript planning, bibliography management, traceability, drafting, asset generation, venue checklists, artifact evaluation, manuscript review, rebuttal planning, and submission packaging.

### Validation

- Manuscript smoke validation passed locally with manuscript creation, bibliography building, draft generation, result-table generation, traceability, venue setting, submission checklist, artifact-evaluation package creation, reviewer panel, rebuttal plan, review submission package export, and v8 release-gate execution.
- `gapforge v8-release-gate --write-report --json` passed locally for the release fixture with a generated review-ready submission package, artifact-evaluation package, traceability report, bibliography, reviewer panel, rebuttal/revision plan, and blocked unsupported/fake citation fixture paths.
- No real venue submission happened. No venue acceptance, SOTA claim, broad benchmark claim, real manuscript peer review, or third-party artifact evaluation is claimed.

## 0.7.0

GapForge v0.7 is the real benchmark execution and replication upgrade. It keeps the v5 literature gates and v6 empirical-claim gates intact while adding first-class benchmark artifacts, explicit dataset consent and cache handling, compute/job abstractions, benchmark canaries, replication packages, and a v7 release gate that separates fixture validation from opt-in real/local public benchmark validation.

### Benchmarks, Data, and Compute

- Added a benchmark registry with benchmark records, tasks, suites, cards, readiness checks, and fixture labeling.
- Added external dataset download planning, cache management, explicit consent records, license/terms warnings, manual-download handling, download hashes, and cache reporting.
- Added compute environment abstraction for local, Docker, GPU-local, Slurm, and custom environments with resource requests and availability checks that remain CI-safe.
- Added job runner and scheduler abstractions with local execution, queue persistence, cancellation, Docker/Slurm unavailable reporting, and execution-record integration.
- Added experiment sweeps, ablation plans, and seed plans so parameter changes and stochastic runs are explicit and controlled.

### Results, Analysis, and Comparison

- Added a result database and aggregation layer that normalizes parsed metric results, preserves run-type labels, aggregates across seeds/splits, exports CSV, and excludes failed runs from aggregates while listing them.
- Added error analysis and slice analysis from prediction artifacts, with false-positive emphasis for low-FPR contexts and no fabricated examples.
- Added benchmark comparison and leaderboard reports that separate baseline/proposed rows, smoke/pilot/main run types, internal/external sources, missing baselines, limitations, and anti-SOTA guardrails.
- Added low-FPR power planner v2 with negative-sample sizing, zero-false-positive upper bounds, alpha target guidance, exact/binomial helpers, and underpowered-claim warnings.

### Replication and Release Gates

- Added safe-by-default replication package export, replication manifests, package verification, reproduction runner, and multi-environment reproducibility matrix.
- Added benchmark canary profiles for fixture success, fixture failure, opt-in local public small benchmark, low-FPR underpowered warning, and replication package validation.
- Added a v7 release gate requiring fixture benchmark success and failure paths, benchmark comparison, aggregation, error analysis, replication export/verification, low-FPR underpowered warning coverage, no fake results, and preserved smoke/pilot/main labels.
- Added opt-in real/local public benchmark claim checks requiring an accepted real benchmark canary, dataset consent, artifact-backed results, and a replication package for the real benchmark workspace.
- Added v7 eval fixtures/metrics, dashboard pages, Python API functions, documentation, and Codex-readable benchmark/replication skills.

### Validation

- Fixture benchmark gate passed locally with successful and failed benchmark canaries, result aggregation, error analysis, replication package export/verification, and low-FPR underpowered warning coverage.
- Real benchmark validation was attempted and passed for the opt-in `local_public_small_benchmark` canary using the public UCI Iris dataset with explicit dataset consent, cached download, artifact-backed metrics and predictions, benchmark comparison, error analysis, and replication package verification.
- `gapforge v7-release-gate --write-report --json --claim-real` passed with fixture gate true, real benchmark gate true, and no blockers.
- No fake benchmark results or SOTA claims are accepted. The real/local public benchmark canary validates the benchmark-and-replication path; it is not a broad performance claim across large external benchmarks, GPU/cluster runs, or independent replication by another researcher.

## 0.6.0

GapForge v0.6 is the experiment execution and empirical validation release. It keeps the v4 Codex workflow and v5 real-literature quality gates intact while adding durable experiment workspaces, artifact-backed result parsing, statistical analysis, reproducibility checks, empirical reviewer simulation, and honest paper-package exports.

### Experiment Workspaces and Registries

- Added first-class experiment workspaces with workspace state, run manifests, execution records, result artifacts, logs, reports, code, data, and config directories.
- Added dataset registry, dataset cards, loaders, and validation so fixture, synthetic, benchmark, generated, and real datasets are labeled with license, leakage, privacy, bias, and intended-use warnings.
- Added baseline registry, baseline cards, and related-work-driven baseline selection so required baselines become explicit experiment blockers instead of prose-only assumptions.
- Added metric registry and statistical test planning with built-in false positive rate, true positive rate, precision, recall, AUROC, AUPRC, calibration error, abstention, cost-weighted error, and runtime templates.
- Added low-FPR statistical planning warnings for rare false-positive claims, including sample-size and exact/binomial confidence-interval guidance.

### Code, Execution, and Results

- Added experiment code scaffold v2 with runnable workspace code, smoke configs, tests, and scripts while keeping generated outputs separate from result artifacts.
- Added constrained Codex/GPT-5.4 experiment code tasks for dataset loaders, baselines, metrics, runners, ablations, tests, smoke debugging, and result analysis.
- Added the experiment runner to execute manifests, capture redacted stdout/stderr logs, record return codes, detect expected outputs, hash result artifacts, and preserve failed runs.
- Added result parsing for metrics JSON artifacts, metric results, result summaries, and empirical claims.
- Added empirical claim ledger integration so no empirical claim is supported unless a run record and result artifact exist.
- Added statistical analysis helpers for binomial confidence intervals, paired summaries, bootstrap placeholders, multiple-testing warnings, low-FPR sample warnings, and exact count summaries.

### Reproducibility, Review, and Export

- Added reproducibility checks for dataset cards, baseline cards, metric definitions, random seeds, environments, manifests, commands, logs, hashes, confidence intervals, code scaffold version, and fake/fixture data labels.
- Added empirical reviewer simulation for empirical rigor, statistics, reproducibility, novelty with result context, and area-chair-style review.
- Upgraded paper package export to v2 so planned experiments, smoke runs, pilot/main results, failed results, negative results, and hypothetical expected results are labeled separately.
- Added v6 release gate requirements for executed fixture experiments, failed experiment paths, parsed result artifacts, artifact-backed empirical claims, reproducibility checks, empirical review, and paper package v2 export.
- Added v6 eval fixtures and metrics for experiment execution integrity, result-artifact grounding, empirical-claim validity, statistical caution, reproducibility, empirical review, fake-result rejection, paper-package honesty, and v6 release-gate correctness.
- Added experiment dashboard pages for workspaces, runs, datasets, baselines, metrics, results, reproducibility, empirical reviews, and paper-package status.
- Added v6 Python API helpers for experiment workspaces, registries, scaffolding, execution, result parsing, analysis, reproducibility, empirical review, paper-package v2 export, and release-gate checks.
- Added v6 documentation and Codex-readable skills for experiment workspaces, dataset cards, baseline selection, metric planning, experiment-code implementation, result analysis, reproducibility checks, empirical review, and paper-package v2.

### Validation

- Fixture experiment execution passed locally on May 6, 2026 with a successful smoke execution, a recorded failed execution path, a parsed metrics artifact, an artifact-backed empirical claim, reproducibility checks, empirical review, and paper package v2 export.
- A real Codex/GPT-5.4 experiment-code task ran locally through the configured direct Codex wrapper, produced a valid implementation patch, imported under the workspace code boundary, and passed workspace smoke validation. This validates the Codex experiment-code workflow, not a real empirical study.
- No real-world main experiment was run for this release; real empirical results remain not tested.
- `make ci`, `make eval`, v2/v3/v4/v5/v6 eval reports, v2/v3/v4/v6 smoke targets, and `gapforge v6-release-gate --write-report --json` pass for the release candidate.

## 0.5.0

GapForge v0.5 is the real literature campaign quality release. It keeps the deterministic/offline and v4 Codex workflow paths intact while adding live-source diagnostics, planned search rounds, closest-prior-work recall, and human research-quality acceptance gates.

### Live Literature Campaign Quality

- Added live source diagnostics and `live-source-diagnostic` reports that distinguish healthy, degraded, disabled, fallback-heavy, and unavailable source behavior.
- Added real literature campaign profiles for low-FPR collusion, LLM monitor evasion, multi-agent covert channels, cross-domain specificity, and undercovered-refusal validation.
- Added the real campaign dry-run planner so users can inspect source checks, search rounds, expected artifacts, budget, blockers, and acceptance criteria before running live campaigns.
- Added the real-literature campaign controller path so campaigns gather source health, execute planned search rounds, canonicalize papers, build retrieval, mine gap evidence, run prior-work recall, and stop with an explicit conservative reason.

### Search, Canonicalization, and Novelty Safety

- Added the search strategy planner with initial, survey, benchmark/dataset, novelty, counterevidence, and adjacent-field rounds.
- Added paper canonicalization v2 for DOI, arXiv, OpenReview, normalized-title, and high-confidence title/author/year merge decisions with auditable reports.
- Added the prior-work recall gate to block strong novelty until exact, method/metric, benchmark/dataset, survey, citation-neighborhood, and adjacent-field searches are complete as required by the source profile.
- Tightened novelty/prior-work candidate selection so deterministic fallback records remain visible in coverage but do not dominate closest-prior-work decisions when live paper records are available.

### Codex, Review, Reporting, and APIs

- Added the Codex research synthesis task for evidence-gated direction synthesis after live search, retrieval, and prior-work recall gates pass.
- Added human real-literature quality review with separate workflow acceptance and research-quality acceptance.
- Added live campaign dashboard/report sections for source health, search strategy, search rounds, canonicalized papers, full-text/abstract coverage, prior-work recall, Codex synthesis artifacts, and quality review.
- Added the v5 release gate to require deterministic evidence, a passing v4 workflow gate, live-literature campaign records, research-quality accepted campaigns, a conservative refusal campaign, and an experiment-ready campaign.
- Added v5 eval fixtures and metrics for live-source coverage, search strategy completeness, prior-work recall gates, canonicalization quality, refusal quality, research-direction quality proxy, quality-review gate correctness, and v5 release-gate correctness.
- Added v5 API functions for source health, search planning, real-literature campaigns, canonicalization, prior-work recall, quality review, and release-gate checks.
- Added v5 documentation and Codex-readable skills for live literature scouting, search planning, prior-work recall, real-literature review, and research synthesis.

### Validation

- Recorded a local May 6, 2026 v5 release-gate pass with two quality-accepted live-literature campaigns: one experiment-ready campaign and one conservative refusal campaign.
- `make ci`, `make eval`, v2/v3/v4/v5 eval reports, v2/v3/v4 smokes, and `gapforge v5-release-gate --write-report --json` pass for the release candidate.

## 0.4.1

GapForge v0.4.1 is a focused Codex workflow usability patch. It does not add new research claims or count fake-agent canaries as real acceptance.

### Codex Workflow Usability

- Added `gapforge setup-codex` as a setup wizard that reports direct, task-pack, manual-handoff, and fake mode availability.
- Added `gapforge codex-doctor` to diagnose task-pack paths, outputs, validation/import status, attestation, review, and actual-run blockers.
- Added copy-paste handoff v2 files: `README_FIRST.md`, `CODEX_PROMPT.md`, `OUTPUT_CONTRACT.md`, `VALIDATE_AND_IMPORT.sh`, minimal output skeletons, and examples.
- Added direct command preview and dry-run support for Codex command templates.
- Added a local direct Codex runner wrapper for `codex exec` when real runs are enabled and the Codex CLI is available.
- Improved command-template validation, placeholder warnings, redaction, output directory handling, and direct-run failure messages.

### Validation, Import, and Attestation

- Added flexible output contract levels so partial but useful Codex output can validate without weakening evidence/citation rules.
- Added `validate-import-all`, task output discovery, latest task lookup, and easier validate/import command flows.
- Added valid and invalid Codex output examples for deep reading, gap mining, novelty, reviewer, manuscript, fake-citation rejection, and unsupported-claim rejection.
- Improved actual-run attestation status so users can see validation/import, attestation, human review, and remaining blockers.
- Improved repair UX with latest-invalid lookup, repair handoff prompts, exact validation errors, known valid IDs, and repair validate/import commands.
- Improved release-gate messaging with blocker categories, next commands, accepted-real-campaign counters, and fake-vs-real explanations.

### Canary Workflows

- Added `single_task_codex_handoff` and `single_task_fake_handoff_regression` to debug the smallest Codex task-pack workflow.
- Added `manual_pdf_codex_reading_handoff` and a fake companion to validate local-PDF/full-text Codex reading workflow mechanics.
- Validated three real Codex/GPT-5.4 workflow canaries locally on May 6, 2026: one conservative refusal workflow, one manual-PDF/full-text reading workflow, and one fixture-backed experiment-ready workflow.
- `gapforge v4-release-gate --write-report --json` passed locally with 3 accepted real campaigns and no blockers.

### Documentation

- Added `docs/CODEX_QUICKSTART.md`.
- Added v0.4.1 fix plan, acceptance, troubleshooting, release notes, and Codex usage status docs.
- Rewrote Codex usage documentation around setup, task-pack handoff, direct command dry run, validation/import, attestation, review, repair, and release-gate acceptance.

### Validation

- `make format-check` passes.
- `make lint` passes.
- `make typecheck` passes.
- `make test` passes with 465 tests.
- `make eval` passes offline.
- `gapforge eval --v4 --write-report` passes offline.
- `gapforge v4-release-gate --write-report --json` passes with 3 accepted real Codex/GPT-5.4 workflow canaries.

## 0.4.0

GapForge v0.4 prepares the system for actual Codex/GPT-5.4 agentic research campaigns. It does not claim exhaustive autonomous literature review, and it does not count fake-agent success as real-run acceptance.

### Agentic Campaigns

- Added first-class campaign state, campaign steps, campaign decisions, campaign milestones, campaign budgets, stop conditions, and campaign reports.
- Added campaign controller logic for deterministic, fake-agent, Codex task-pack, Codex direct, and manual-handoff modes.
- Added explicit stop reasons so campaigns can end as ready, not ready, blocked, pending handoff, invalid-output, or budget-exhausted.
- Added campaign canary profiles for low-FPR collusion, monitor evasion, cross-domain specificity, undercovered refusal, manual PDF, and fake-agent regression.

### Codex/GPT-5.4 Actual-Run Path

- Added real-run diagnostics for environment status, agent runtime status, task-pack status, import validator status, canary status, blockers, and recommended next commands.
- Upgraded the AgentClient runtime contract with direct, task-pack, manual-handoff, and fake capabilities plus actual-run attestation rules.
- Added runtime capability reporting for direct, task-pack, manual-handoff, and fake execution methods.
- Added Codex runner and handoff support with configured command execution, task-pack handoff files, validation/import commands, and redacted command logs.
- Added campaign-level Codex task packs for planning, literature scouting, batch reading, gap synthesis, novelty review, experiment architecture, reviewer panel, and stop decisions.
- Added actual-run attestation records so task-pack/manual-handoff outputs can count only when real Codex/GPT-5.4 execution is attested, validated, imported, and human-reviewed.
- Added diagnostics for real-run blockers and setup guidance for direct versus task-pack/handoff execution.

### Validation, Import, and Recovery

- Added robust campaign output validation, partial import, rollback snapshots, import records, and rollback commands.
- Added agent output repair task generation so invalid Codex JSON can be corrected without weakening validation.
- Added retrieval-backed task context selection with explicit budgets and context-limited flags.
- Added agentic search requests and novelty re-search loops so Codex can propose searches while GapForge validates and executes them.

### Research Workflows

- Added campaign-level reviewer and rebuttal loops.
- Added experiment code task generation and experiment repository scaffolding for experiment-ready directions.
- Added campaign-level human review and acceptance summaries.
- Added dashboard pages for campaigns, actual runs, canaries, agent tasks, imports, human reviews, rejected outputs, fake-vs-real labels, and release-gate status.
- Added campaign reports with explicit stop reasons and acceptance blockers.

### Evaluation, API, and Release Gates

- Added v4 campaign eval fixtures and metrics for campaign decisions, stop reasons, output validation strictness, actual-run gates, novelty loops, direction maturity, report honesty, review queues, code tasks, and rollback safety.
- Exposed v0.4 campaign and actual-run workflows through the Python API.
- Added a machine-checkable v0.4 release gate requiring deterministic evidence, fake-agent campaign canary success, at least three accepted real Codex/GPT-5.4 campaigns, a strict-refusal campaign, an experiment-ready campaign, and a manual-PDF/full-text campaign.
- Added `make v4-smoke` for CI-safe fake-agent campaign smoke validation. The target writes a release-gate report but expects the actual-run gate to fail unless real campaigns have been accepted.
- Updated v0.4 docs and Codex-readable skills for campaign control, Codex campaign tasks, output validation, novelty loops, experiment code tasks, reviewer panels, and real-run acceptance.

### Validation

- Deterministic checks passed locally on May 5, 2026: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `gapforge eval --v4 --write-report`, `make coverage`, `make v2-smoke`, `make v3-smoke`, and `make v4-smoke`.
- Fake campaign canary `fake_agent_campaign_regression` passed.
- Actual Codex/GPT-5.4 campaign acceptance was **not completed** in this environment. `GAPFORGE_ENABLE_REAL_RUNS`, `GAPFORGE_AGENT_NAME`, and `GAPFORGE_CODEX_MODEL` were not configured, so real campaign canaries were refused or recorded as non-actual.
- `gapforge v4-release-gate --write-report` correctly fails because there are zero accepted real Codex/GPT-5.4 campaigns.

## 0.3.0

GapForge v0.3 extends the v0.2 full-text evidence system with project memory, hybrid retrieval, optional Codex/GPT-5.4 task-pack workflows, research direction maturation, and manuscript package exports. It is still not an exhaustive autonomous literature reviewer.

### Project Memory and Retrieval

- Added project-level memory for topics, corpus papers, rejected ideas, human decisions, memory records, and research directions.
- Added a Python API layer for notebooks, scripts, and future UI surfaces without shelling out to the CLI.
- Added project claim graphs with deterministic duplicate/contradiction detection and human resolution records.
- Added hybrid lexical/local-semantic retrieval over papers, sections, evidence spans, notes, claims, gaps, dossiers, and project memory.
- Added source policy profiles and coverage stopping assessments.
- Added active-loop decision records and budget-aware stop conditions.

### Codex/GPT-5.4 Agent Support

- Added an optional provider LLM adapter with JSON guards, budget tracking, transcript redaction, and graceful provider-unavailable failures.
- Added optional LLM-backed deep-reading, gap-mining, novelty-dossier, and reviewer workflows behind deterministic/fake/prompt-pack/provider modes.
- Added `AgentClient` separately from `LLMClient`.
- Added Codex-compatible task packs, strict schema validation, validated output import, fake-agent CI mode, and canary run profiles.
- Added `gapforge run --v3 --mode deterministic|prompt-pack|fake-agent|llm-assisted`.
- Added human review harness and release-gate status for actual Codex/GPT-5.4 canary acceptance.

### Research Direction Workflow

- Added related-work matrices, must-read lists, baseline candidates, experiment protocols, reproducibility checklists, review panels, rebuttal plans, and manuscript/paper package exports.
- Added review queue and static dashboard for project/run inspection.
- Added artifact safety auditing, redaction, safe-bundle export, and generated-artifact hygiene.

### Full-Text and Evaluation

- Added v0.3 PDF structure extraction hooks for references, tables, equations, captions, and OCR-status records.
- Added v0.3 curated fixture layout and metrics for retrieval relevance, prior-work recall proxy, direction maturity, protocol completeness, manuscript honesty, contradiction detection, source-policy compliance, and LLM grounding.

### Validation

- Deterministic checks passed locally: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `make coverage`, `make v2-smoke`, and `make v3-smoke`.
- Fake-agent canary `fake_agent_regression` passed.
- Actual Codex/GPT-5.4 real-run acceptance was **not completed** because the real-run environment was unavailable. The release must not claim actual-run validation passed.

## 0.2.0

GapForge v0.2 upgrades the project from an abstract/metadata-heavy smoke-test system into a full-text-aware, evidence-located research ideation system with conservative novelty checking. It is still not an exhaustive autonomous literature reviewer.

### Full-Text and Evidence

- Added full-text artifact models for PDFs, HTML/text/metadata artifacts, parsed paper sections, evidence spans, search query records, source coverage, and citation graphs.
- Added PDF artifact storage under run directories with safe filenames, SHA256 hashing, duplicate detection, and durable `PaperArtifact` records.
- Added PDF download support with cache-aware HTTP, max-size guards, PDF validation, network-disable handling, and non-fatal failure recording.
- Added PDF parsing and sectionization with page-preserving extraction, common section classification, fallback sections, and section text artifacts.
- Upgraded deep reading to use parsed full-text sections when available, produce evidence spans, distinguish abstract-only notes, and avoid extracting results without evidence.
- Added evidence-span-aware validation and report language so abstract/metadata-only claims are not presented as full-text evidence.

### Search, Coverage, and Prior Work

- Added first-class search query ledger records for initial, analogy, novelty, citation-expansion, and manual searches.
- Added source coverage and full-text coverage reports that show searched sources, failures, fallback/offline papers, PDF/full-text coverage, and warnings.
- Added citation graph construction from explicit metadata and conservative related-work expansion.
- Upgraded novelty checking with closest-prior-work dossiers, query planning, deterministic structured comparison, missing-search tracking, and conservative verdict rules.
- Added source ranking v2 with paper roles, source/role diversity, full-text availability, novelty importance, and adjacent-field transfer signals.

### Research Skills

- Upgraded gap mining with evidence matrices, counterevidence, confidence rules, and full-text/coverage-sensitive behavior.
- Added gap evidence matrix artifacts in JSON and Markdown.
- Upgraded cross-domain analogy into status-tagged transfer candidates with query-only, evidence-found, promoted, and rejected states.
- Added cross-domain transfer candidate artifacts and report integration.
- Upgraded experiment design and reviewer simulation to respect stronger novelty, baseline, falsification, and reviewer blocking-issue rules.

### Human Review and LLM Extension Points

- Added human-in-the-loop review/edit commands for approving/rejecting gaps, annotating and marking claims, adding evidence, locking objects, and viewing audit logs.
- Added durable human review records and audit artifacts.
- Added optional LLM adapter interfaces, deterministic fake client, and prompt-pack generation without requiring live model calls.

### Evaluation and Reporting

- Added v0.2 synthetic fixtures with paper sections, evidence spans, novelty dossiers, gap evidence matrices, source coverage, duplicate ideas, and expected reviewer objections.
- Added v0.2 metrics for full-text coverage, evidence-span grounding, gap evidence matrices, novelty dossier completeness, source coverage transparency, human review respect, and report uncertainty.
- Upgraded the final report into a v0.2 evidence-located dossier with source coverage, full-text coverage, evidence locators, gap matrices, cross-domain transfer candidates, novelty dossiers, human review summary, rejected ideas, uncertainty, and strict report mode.
- Strict report mode refuses to recommend a top direction when coverage, evidence, novelty, or reviewer gates are weak.

### CLI, Docs, and Release Hygiene

- Added v0.2 orchestration flags for `gapforge run --v2`, PDF download/parse controls, deep novelty, strict reports, and bounded related-work expansion.
- Added manual ingestion commands for papers, arXiv IDs, DOIs, local PDFs, and URLs.
- Added coverage, citation graph, related-work expansion, prompt-pack, and human review CLI commands.
- Added v0.2 roadmap, acceptance criteria, known limitations, release process, contributing guide, testing guide, and v0.2 workflow documentation.
- Added GitHub Actions CI and pre-commit configuration.
- Added Makefile targets for `format-check`, `typecheck`, `ci`, `coverage`, `v2-smoke`, `clean-runs`, and `clean-cache`.

### Validation

- `make ci` passes.
- `make eval` passes offline.
- `make v2-smoke` passes offline.
- `gapforge eval --v2 --write-report` passes offline.

### Known Limitations

- v0.2 remains deterministic and heuristic.
- Offline/fallback runs are smoke tests, not literature conclusions.
- Full-text quality depends on available PDFs and extractable text.
- Novelty dossiers are conservative prior-work aids, not proof of novelty.

## 0.1.0

- Created the initial GapForge Python package and CLI.
- Added persistent research run state under `runs/`.
- Added source connector interfaces and keyless first-pass connectors with caching and graceful fallback.
- Added modular skills for literature mapping, paper triage, deep reading, gap mining, cross-domain analogy, novelty gating, experiment design, and reviewer simulation.
- Added claim ledger, provenance tracking, validation rules, evaluator fixtures, and final report generation.
- Added Codex-readable skill folders under `skills/`.
- Added README, examples, docs, Makefile, Ruff, mypy, and pytest tooling.

Note: v0.1 outputs are deterministic heuristic artifacts. Offline and fixture outputs are smoke-test signals, not real literature conclusions.
