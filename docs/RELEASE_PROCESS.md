# Release Process

GapForge releases should be conservative. A release should document what the system can do, what it cannot do, and which checks passed.

## Pre-Release Checklist

1. Confirm the version in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Update `docs/KNOWN_LIMITATIONS.md`.
4. Confirm README quickstart commands still match the CLI.
5. Run automated validation:

```bash
make ci
```

6. Run or review offline smoke validation:

```bash
GAPFORGE_DISABLE_NETWORK=1 gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
GAPFORGE_DISABLE_NETWORK=1 gapforge report --strict
```

7. Inspect `final_report.md` and confirm it does not present fallback/offline results as real literature conclusions.
8. For v0.3 releases, write `docs/releases/v0.3.0-real-run-acceptance.md` with machine-readable release-gate front matter.
9. For v0.3 releases that claim actual-run validation, complete the real-run canary process in `docs/V0_3_REAL_RUN_ACCEPTANCE.md` and `docs/V0_3_CANARY_RUNS.md`.
10. Confirm at least one actual Codex/GPT-5.4 canary has an accepted canary record before using the phrase "actual-run acceptance passed."
11. Record human review using `docs/REAL_RUN_REVIEW_CHECKLIST.md`.
12. For v0.4 releases, complete the campaign process in `docs/V0_4_AGENTIC_CAMPAIGNS.md` and `docs/V0_4_REAL_RUN_ACCEPTANCE.md`.
13. For v0.9 releases, complete the external pilot process in `docs/V0_9_EXTERNAL_PILOT.md`, acceptance criteria in `docs/V0_9_ACCEPTANCE_CRITERIA.md`, and v1 readiness gate in `docs/V0_9_V1_READINESS.md`.
14. For v0.9.1 migration remediation, follow `docs/V0_9_1_MIGRATION_REMEDIATION.md` and `docs/V1_MIGRATION_AND_COMPATIBILITY.md`.
15. For v2 releases, complete the Idea Discovery Engine process in `docs/V2_ROADMAP.md`, `docs/V2_ACCEPTANCE_CRITERIA.md`, `docs/V2_IDEA_DISCOVERY.md`, `docs/V2_IDEA_YIELD_METRICS.md`, `docs/V2_RESEARCH_AGENDA_MODE.md`, and `docs/V2_HUMAN_FEEDBACK.md`.
16. For v2.1 releases, complete the selected-idea execution process in `docs/V2_1_ROADMAP.md`, `docs/V2_1_SELECTED_IDEA.md`, `docs/V2_1_BENCHMARK_SPEC.md`, and `docs/V2_1_ACCEPTANCE_CRITERIA.md`.
17. Commit with a message that records constraints, rejected alternatives if useful, confidence, scope risk, tested commands, and known gaps.
18. Tag the release only after the checks pass.

## v0.3 Validation Levels

- Level 0: deterministic unit tests, no LLM, CI.
- Level 1: offline smoke tests, no LLM, no network.
- Level 2: fake LLM tests for JSON guards and evidence gates.
- Level 3: prompt-pack dry runs for Codex/GPT-5.4 prompt readiness.
- Level 4: actual Codex/GPT-5.4 canary runs, manual/private.
- Level 5: human-reviewed acceptance with recorded review decisions.

CI must not require Codex/GPT-5.4. Actual-run validation is required for a v0.3 release to claim actual-run readiness, but it is not part of normal automated tests.

If Codex/GPT-5.4 is unavailable, the release cannot claim actual-run validation passed. Never fake a canary pass.

For v0.3, actual-run validation requires an accepted canary record. A failed, rejected, planned, prompt-pack-only, or fake-agent canary is not sufficient.

## v0.4 Actual-Run Gate

v0.4 is the actual Codex/GPT-5.4 agentic campaign release. It must not claim actual-run acceptance unless multiple real Codex/GPT-5.4 campaigns completed and were accepted by human review.

For v0.4 releases:

- require multiple accepted real campaigns, not a single skill-level canary
- require campaign artifacts, validation records, imported-output summaries, strict-report behavior, and human review records
- require coverage across literature/novelty, local-PDF full-text reading, and undercoverage strict-refusal campaigns
- fake-agent campaigns remain CI checks only
- prompt-pack-only handoff does not count unless real Codex outputs are imported, validated, and reviewed
- release notes must say either `v0.4 actual-run acceptance passed` or `v0.4 actual-run acceptance not completed`

Those campaigns should cover literature search/reading, novelty, experiment planning, reviewer/rebuttal planning, and manuscript package review where practical.

Recommended v0.4 release-gate commands:

```bash
make ci
gapforge eval --v4 --write-report
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge campaign-canary-plan --profile agentic_low_fpr_collusion
gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge v4-release-gate --project-id <project-id> --write-report --json
```

If direct Codex execution is unavailable, use task-pack handoff:

```bash
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
```

Never mark the handoff as accepted until the outputs were actually produced by Codex/GPT-5.4 and the validated import plus human review artifacts exist.

## v0.4.1 Codex Usability Patch Gate

v0.4.1 is a patch release for Codex workflow usability and actual-run reliability. It should not add new research features or weaken acceptance gates.

Before tagging v0.4.1:

```bash
make ci
gapforge eval --v4 --write-report
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge setup-codex
gapforge campaign-canary-plan --profile agentic_low_fpr_collusion
gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real
gapforge campaign-task --campaign-id <campaign-id> --type novelty_reviewer
gapforge codex-handoff --task-id <task-id>
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
```

Release notes must state whether the v0.4.1 task-pack Codex usability canary completed. That is not the same as full v0.4 actual-run acceptance, which still requires the v4 release gate and multiple accepted real campaigns.

## v0.5 Live-Literature Quality Gate

v0.5 must not claim research-quality validation based only on workflow canaries. It must require accepted live-literature campaigns over real source results and real paper metadata.

Before tagging v0.5:

```bash
make ci
gapforge eval --v4 --write-report
gapforge eval --v5 --write-report
gapforge setup-codex
gapforge v4-release-gate --write-report --json
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge live-source-diagnostic --topic "<topic>" --source-profile <profile> --write-report
gapforge real-literature-run --profile <live-literature-profile>
gapforge campaign-report --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --accept-quality --reviewer "<expert>"
gapforge v5-release-gate --project-id <project-id> --write-report --json
```

The v0.5 release gate should require:

- deterministic CI remains passing
- fake-agent campaign smoke remains passing
- v0.4.1 workflow path remains passing or is explicitly documented as unavailable
- at least three accepted live-literature campaigns
- at least two source-policy fields represented
- at least one accepted refusal campaign for poor coverage, weak novelty, or closest-prior-work conflict
- at least one experiment-ready campaign with source coverage, novelty dossier, related-work matrix, experiment protocol, and human review
- no fake citations, unsupported high-confidence claims, strong novelty without prior work, hidden missing searches, or fixture-only campaigns counted as research quality

The v0.5 release gate is different from the v0.4 workflow gate. v0.4 proves that Codex output can be validated/imported/attested/reviewed. v0.5 must prove that live source coverage, closest-prior-work recall, evidence grounding, and human research-quality review are adequate for the accepted campaigns.

Release notes must distinguish:

- deterministic/fake CI status
- v0.4.1 workflow canary status
- v0.5 live-literature campaign status
- accepted/rejected live campaigns
- expert-review findings
- missed-prior-work postmortems, if any

If live sources are unavailable, record the campaigns as not-run or refused. Do not fake a live-literature pass.

## v0.6 Experiment Execution Gate

v0.6 must not claim empirical validation based on protocols, scaffolds, task packs, smoke tests, or model-generated text. It must require executed experiment artifacts.

Before tagging v0.6, the release process should require:

```bash
make ci
gapforge eval --v5 --write-report
gapforge eval --v6 --write-report
gapforge v5-release-gate --write-report --json
gapforge experiment-workspace-create --project-id <project-id> --direction-id <direction-id>
gapforge dataset-register --workspace-id <workspace-id> --name "fixture examples" --path <path> --dataset-type fixture
gapforge baseline-register --workspace-id <workspace-id> --name "heuristic baseline" --baseline-type heuristic
gapforge metric-register --workspace-id <workspace-id> --name "false positive rate"
gapforge scaffold-experiment-code --workspace-id <workspace-id>
gapforge experiment-manifest-create --workspace-id <workspace-id> --run-type smoke --command "..." --expected-output results/metrics.json
gapforge experiment-run --workspace-id <workspace-id> --manifest-id <manifest-id>
gapforge parse-results --execution-id <execution-id>
gapforge analyze-results --execution-id <execution-id>
gapforge reproducibility-check --execution-id <execution-id>
gapforge empirical-review --execution-id <execution-id>
gapforge export-paper-package-v2 --workspace-id <workspace-id>
gapforge v6-release-gate --write-report --json
```

The v0.6 release gate should require:

- deterministic CI remains passing
- v0.5 literature-quality gate remains passing or any limitation is explicitly documented
- at least one executed fixture experiment with run manifest, logs, result artifact, statistical analysis, reproducibility check, and result claim ledger
- at least one failed or negative experiment path with durable logs and visible report language
- paper package export separates real observed results, placeholders, expected/hypothetical results, smoke outputs, and missing results
- no result claim is marked supported without a linked result artifact
- no failed run or negative result is hidden from reports

Release notes must distinguish:

- protocol-ready directions
- generated scaffolds
- smoke runs
- executed experiments
- failed or negative experiments
- empirically supported claims
- unsupported or inconclusive result claims

If no executed experiment artifacts exist, record v0.6 empirical validation as not completed. Never fabricate a pass.

## v0.7 Real Benchmark Execution Gate

v0.7 must not claim real benchmark execution or replication readiness based only on fixture smoke, generated code, or Codex-written analysis. It must require at least one accepted real or benchmark-like non-fixture run, or mark real benchmark validation incomplete.

Before tagging v0.7, the release process should require:

```bash
make ci
make eval
gapforge eval --v2 --write-report
gapforge eval --v3 --write-report
gapforge eval --v4 --write-report
gapforge eval --v5 --write-report
gapforge eval --v6 --write-report
gapforge eval --v7 --write-report
make v2-smoke
make v3-smoke
make v4-smoke
make v6-smoke
make v7-smoke
gapforge v6-release-gate --write-report --json
gapforge benchmark-canary-run --profile local_public_small_benchmark --real --accept-download
gapforge v7-release-gate --write-report --json --claim-real
```

The v0.7 release gate should require:

- deterministic CI remains passing
- v5 literature gates and v6 empirical gates remain passing or limitations are explicitly documented
- at least one real or benchmark-like non-fixture run exists
- benchmark registry and benchmark card exist
- dataset card, license, cache path, and checksum/version metadata exist
- required baselines and metrics are recorded
- compute mode, command, logs, return code, and result artifacts are recorded
- comparison tables and error/slice analysis are generated
- low-FPR claims include power/sample-size and confidence-interval warnings
- failed jobs and missing baselines remain visible
- replication package is exported
- no fixture-only result is counted as real benchmark performance

Release notes must distinguish:

- fixture smoke
- local benchmark
- full benchmark
- failed jobs
- underpowered results
- replication package
- real benchmark acceptance status

If external downloads, GPU, cluster execution, or independent replication are unavailable, record those as not-run or incomplete. Do not fake a benchmark pass.

## v0.8 Manuscript and Artifact-Evaluation Gate

v0.8 must not claim submission-readiness based only on a polished draft, generated prose, reviewer simulation, or paper package export. It must require claim traceability, citation validity, artifact-backed results, artifact evaluation package state, blinding checks when applicable, reviewer-objection handling, and human review.

Before tagging v0.8, the release process should require:

```bash
make ci
make eval
gapforge eval --v2 --write-report
gapforge eval --v3 --write-report
gapforge eval --v4 --write-report
gapforge eval --v5 --write-report
gapforge eval --v6 --write-report
gapforge eval --v7 --write-report
gapforge eval --v8 --write-report
gapforge v7-release-gate --write-report --json
gapforge manuscript-create --project-id <project-id> --direction-id <direction-id> --workspace-id <workspace-id> --title "..."
gapforge bibliography-build --manuscript-id <manuscript-id>
gapforge citation-check --manuscript-id <manuscript-id>
gapforge manuscript-traceability --manuscript-id <manuscript-id>
gapforge manuscript-table --manuscript-id <manuscript-id> --type result_table
gapforge manuscript-figure --manuscript-id <manuscript-id> --type metric_plot
gapforge manuscript-set-venue --manuscript-id <manuscript-id> --venue generic_conference
gapforge submission-checklist --manuscript-id <manuscript-id>
gapforge anonymize-manuscript --manuscript-id <manuscript-id>
gapforge artifact-eval-package --manuscript-id <manuscript-id>
gapforge manuscript-review --manuscript-id <manuscript-id>
gapforge rebuttal-plan --manuscript-id <manuscript-id>
gapforge submission-package --manuscript-id <manuscript-id> --type review
gapforge dashboard --manuscript-id <manuscript-id>
gapforge v8-release-gate --write-report --json
```

The v0.8 release gate should require:

- deterministic CI remains passing
- v5 literature gates, v6 empirical gates, and v7 benchmark/replication gates remain passing or limitations are explicitly documented
- manuscript-ready, submission-ready, and camera-ready are documented as separate states
- a manuscript project links sections, claims, evidence, citations, figures, tables, artifacts, reviewer objections, and human decisions
- every manuscript claim is linked to evidence or explicitly labeled as hypothesis, limitation, future work, or unsupported
- novelty claims link to closest prior work and source-coverage context
- result claims link to execution records, result artifacts, statistical analysis, and reproducibility status
- benchmark claims link to benchmark records, compute logs, comparisons, error/slice analysis, and replication package state
- citations and BibTeX keys resolve to known paper metadata or user-supplied bibliographic records
- figures and tables are generated from recorded result artifacts or labeled conceptual placeholders
- artifact evaluation package is generated from replication and workspace state
- reviewer objections and rebuttal plans are evidence-backed and do not invent responses
- anonymization/blinding checks run when the venue profile requires them
- human review accepts any remaining submission risk or records blockers
- no unsupported result, citation, novelty, or artifact claim passes the gate

Release notes must distinguish:

- manuscript-ready versus review-ready versus submission-ready versus camera-ready
- manuscript-ready
- submission-ready
- camera-ready
- artifact evaluation package status
- citation and BibTeX audit status
- claim traceability status
- anonymization/blinding status
- open reviewer objections and rebuttal risks

If the manuscript cannot pass novelty, result, reproducibility, artifact, citation, blinding, or human-review gates, record it as manuscript-ready with blockers or submission not ready. Do not claim venue acceptance, and do not claim camera-ready status without explicit acceptance metadata.

The Python API mirrors this release path with `gapforge.api.create_manuscript`, `build_bibliography`, `draft_manuscript`, `render_manuscript`, `generate_manuscript_assets`, `run_traceability_check`, `set_venue`, `submission_checklist`, `anonymize_manuscript`, `create_artifact_eval_package`, `manuscript_review`, `rebuttal_plan`, `submission_package`, and `v8_release_gate`.

## v0.9 External Pilot and v1 Readiness Gate

v0.9 must not claim v1 readiness, external research success, or publication readiness based only on fixtures, generated prose, local artifacts, or a polished manuscript. It must run one real external pilot topic end to end and accept either a defensible direction or an evidence-backed refusal.

Before tagging v0.9, the release process should require:

```bash
make ci
make eval
gapforge eval --v5 --write-report
gapforge eval --v6 --write-report
gapforge eval --v7 --write-report
gapforge eval --v8 --write-report
gapforge v8-release-gate --write-report --json
gapforge init-project "v0.9 low-FPR collusion pilot"
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge live-source-diagnostic --topic "low false-positive collusion detection in LLM multi-agent systems" --source-profile ai_safety --write-report
gapforge real-literature-run --profile live_low_fpr_collusion
gapforge campaign-report --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --reviewer "<expert>"
gapforge real-literature-acceptance --campaign-id <campaign-id>
gapforge v9-release-gate --project-id <project-id> --write-report --json
gapforge compatibility-audit --v2 --write-report
gapforge v1-readiness --write-report --json
```

The exact pilot command path may change during v0.9 CLI cleanup. If a listed command is missing or confusing, the release candidate must document the actual replacement path, update the README/runbook, and classify the issue as fixed, accepted scope, v0.9.1 required, or v1 blocker.

The v0.9 release gate should require:

- deterministic CI remains passing
- v5 literature, v6 empirical, v7 benchmark/replication, and v8 manuscript gates remain passing or limitations are explicitly documented
- one named real external pilot topic exists, preferably `low false-positive collusion detection in LLM multi-agent systems`
- live literature campaign evidence exists, or source failures are recorded and drive an honest blocked/refusal outcome
- closest prior work, novelty risk, missed searches, and human quality review are recorded
- the pilot outcome is either a defensible direction or an evidence-backed refusal
- experiment protocol records datasets, baselines, metrics, falsification criteria, compute assumptions, and artifact requirements
- any small real run has run records, logs, result artifacts, analysis, and review
- fixture-only runs are labeled as workflow mechanics and never counted as real empirical success
- artifact package, manuscript draft, reviewer/rebuttal plan, and external feedback records exist, or blocked/refusal artifacts explain why they do not
- migration/backward compatibility from v0.1 through v0.9 state is audited with compatibility audit v2
- CLI workflow cleanup and docs usability findings are fixed, accepted, or scheduled
- artifact hygiene separates safe-to-commit, private, generated, cache-only, and reviewer-facing artifacts
- v1 readiness is assessed as `ready`, `ready_with_explicit_scope`, or `not_ready`

Release notes must distinguish:

- external pilot topic and outcome
- defensible direction versus evidence-backed refusal
- live source coverage and missed-search limitations
- fixture smoke versus small real run evidence
- artifact package and manuscript status
- reviewer/rebuttal status
- external feedback findings
- migration/backward compatibility status
- CLI/docs usability status
- v0.9.1 required or not
- v1 readiness outcome

If no real external pilot was completed, record `v0.9 external pilot not completed`. If the pilot exposes a narrow fixable blocker, record `v0.9 external pilot failed; v0.9.1 required`. Never use v0.9.1 to lower evidence standards or bypass the v1 readiness gate.

## v0.9.1 Migration Remediation Gate

v0.9.0 was not v1-ready because the migration/backward compatibility audit failed. v0.9.1 is the patch lane for that blocker only. It should not add new research features, weaken evidence gates, or claim v1 readiness by itself.

Before tagging v0.9.1:

```bash
make ci
gapforge compatibility-audit --v2 --write-report
gapforge migrate-all --dry-run
# Apply only after reviewing the dry run.
gapforge migrate-all --apply
gapforge migration-report
gapforge compatibility-audit --v2 --write-report
gapforge v1-readiness --write-report --json
```

The compatibility audit must distinguish curated compatibility evidence from messy local generated artifacts. Ignored/generated unsafe local artifacts can be warnings when they are not curated release evidence. Fixture failures, current-schema load failures, protected-data loss risk, missing backup behavior, and unsafe curated evidence are blockers.

If migration fails, restore from `data/migrations/backups/`, inspect `data/migrations/records/`, add an explicit version marker or dedicated migrator, and rerun the dry run plus v2 audit. Do not claim v1 until `gapforge v1-readiness --write-report --json` passes.

## v2 Idea Discovery Engine Gate

v2 must not claim idea-discovery success based on brainstorming volume, a single obvious seed, a tournament ranking, or Codex/GPT-5.4 suggestions. It must actively search for defensible candidates and keep every v1 evidence gate intact.

Before tagging v2, the release process should require:

```bash
make ci
make eval
gapforge eval --v5 --write-report
gapforge eval --v6 --write-report
gapforge eval --v7 --write-report
gapforge eval --v8 --write-report
gapforge v1-readiness --write-report --json
gapforge topic-portfolio --project-id <project-id>
gapforge idea-generate --project-id <project-id> --max-candidates 50
gapforge mutate-rejected-ideas --project-id <project-id>
gapforge constructive-gaps --project-id <project-id>
gapforge transfer-ideas --project-id <project-id>
gapforge idea-codex-task --project-id <project-id> --type idea_seed_expansion
gapforge idea-codex-import --task-id <task-id>
gapforge idea-search --project-id <project-id> --max-iterations 5
gapforge idea-novelty --project-id <project-id> --top-k 10
gapforge idea-tournament --project-id <project-id> --top-k 5
gapforge idea-feedback --idea-id <selected-idea-id> --action accept --rationale "<human review>"
gapforge idea-yield --project-id <project-id> --write-report
gapforge dashboard --project-id <project-id> --include-ideas
gapforge v2-release-gate --write-report --json
```

If Codex/GPT-5.4 is unavailable, record an explicit unavailability artifact instead of skipping the requirement silently. Do not synthesize replacement citations or results.

The v2 release gate should require:

- deterministic CI remains passing
- v1 readiness remains passing or any limitation is explicitly documented
- at least one topic portfolio was searched
- multiple idea candidates were generated and preserved
- idea mutation, constructive gap creation, and cross-domain transfer expansion were attempted
- Codex/GPT-5.4 idea synthesis tasks ran and were validated before import, or explicit unavailability was recorded
- the active idea search controller recorded decisions and stop reasons
- novelty and counterevidence loops ran on serious candidates
- an idea tournament compared candidates under shared criteria
- human preference feedback and human review were recorded
- idea yield metrics were generated
- every accepted idea candidate meets the accepted-candidate standard in `docs/V2_ACCEPTANCE_CRITERIA.md`
- if no candidate is accepted, a research agenda fallback exists and the release gate records explicit idea-discovery failure

Release notes must distinguish:

- topic portfolios searched
- candidate counts and mutation lineage
- constructive gaps and transfer expansions
- Codex/GPT-5.4 synthesis task status
- novelty and counterevidence findings
- tournament results
- human feedback impact
- accepted idea candidates, if any
- rejected candidates and top rejection reasons
- research agenda fallback status
- idea yield metrics
- v2 release-gate outcome

If at least one candidate is accepted, release notes may say `v2 idea discovery passed with accepted candidate`. If no candidate is accepted, release notes must say either `v2 idea discovery failed; v2.0.1 required` or `v2 idea discovery failed; v2.1 planning required`. `gapforge v2-release-gate --allow-agenda-only` is permitted only for an explicit `idea_discovery_incomplete` warning pass. Do not claim v2 success from a fallback agenda.

## v2.1 Selected Idea Execution Gate

v2.1 must not claim selected-idea execution success based only on roadmap prose, generated benchmark scaffolding, synthetic fixture definitions, or manuscript text. It must require a runnable benchmark smoke path for the frozen v2.0 selected idea.

v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`; v2.1 executes that selected idea. The synthetic smoke benchmark is not a final research result. Low-FPR claims require power, benchmark validity limitations must remain explicit, and next steps toward pilot/main benchmark must be recorded before stronger claims are made.

Selected idea:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`

Before tagging v2.1, the release process should require:

```bash
make ci
make eval
gapforge v1-readiness --write-report --json
gapforge v2-release-gate --write-report --json
gapforge selected-idea-lock --idea-id idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits
gapforge selected-idea-project-create --idea-id idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits
gapforge selected-benchmark-spec --project-id <selected-project-id>
gapforge threat-model --benchmark-id <benchmark-id>
gapforge benchmark-task-families --benchmark-id <benchmark-id>
gapforge generate-traces --benchmark-id <benchmark-id> --count 100 --split smoke
gapforge selected-monitor-baselines --benchmark-id <benchmark-id>
gapforge run-monitor-baseline --benchmark-id <benchmark-id> --monitor random
gapforge run-monitor-baseline --benchmark-id <benchmark-id> --monitor threshold
gapforge sequential-metric-plan --benchmark-id <benchmark-id>
gapforge selected-benchmark-workspace --benchmark-id <benchmark-id>
gapforge selected-benchmark-run --workspace-id <workspace-id> --run-type smoke
gapforge selected-benchmark-review --benchmark-id <benchmark-id>
gapforge selected-benchmark-manuscript --benchmark-id <benchmark-id>
gapforge selected-benchmark-paper-package --benchmark-id <benchmark-id>
gapforge dashboard --project-id <selected-project-id> --include-selected-idea
gapforge selected-idea-full-report --project-id <selected-project-id>
gapforge v21-release-gate --write-report --json
```

Equivalent scripts may use the `gapforge.api` wrappers for the same steps. The release candidate must still keep the same evidence requirements and must not replace a missing artifact with prose.

The v2.1 release gate should require:

- deterministic CI remains passing
- v1 readiness and v2 selected-candidate evidence remain available
- selected idea freeze exists and no silent pivot occurred
- formal benchmark specification exists
- threat model and observability assumptions exist
- honest-agent baseline distribution is defined
- collusive-agent scenario distribution is defined
- hard-negative benign scenarios are represented
- sequential audit protocol is specified
- low-FPR specificity metrics are computed over audit windows
- baseline monitors run and record allowed inputs, thresholds, and failures
- power/sample-size plan classifies smoke, pilot, main, and underpowered states
- experiment workspace exists with benchmark, dataset, baseline, metric, manifest, and run records
- smoke benchmark path generates tasks, runs monitors, writes result artifacts, parses metrics, and writes analysis
- result analysis is artifact-backed and labels smoke outputs as smoke outputs
- reviewer critique attacks novelty, threat model, benchmark validity, baselines, statistics, and manuscript claims
- manuscript package update links benchmark claims to artifacts and labels missing work
- generated reports, runs, projects, caches, transcripts, dashboards, PDFs, and large artifacts remain excluded from source unless explicitly curated and safe

Release notes must distinguish:

- selected idea freeze status
- benchmark specification status
- threat model and observability assumptions
- smoke versus pilot versus main benchmark status
- honest-agent and collusive-agent scenario coverage
- baseline monitor coverage
- sequential specificity metric status
- power/sample-size status
- experiment workspace and smoke execution status
- result artifact and analysis status
- reviewer critique findings
- manuscript package status
- unsupported claims and remaining risks

If the runnable smoke path is missing, release notes must say `v2.1 selected idea execution incomplete; benchmark smoke path not ready`. If smoke runs exist, release notes may say `v2.1 selected idea execution passed with runnable benchmark smoke path`, but must not claim final scientific results, real-world collusion benchmark validity, monitor superiority, or publication readiness.

## Tagging

Use semantic version tags:

```bash
git tag v0.3.0
git push origin main --tags
```

## Release Notes

Release notes should include:

- headline capability changes
- migration notes, if any
- validation commands and results
- validation level status, including whether Level 4 and Level 5 passed, failed, or were not run
- known limitations
- whether the default path requires network access or API keys
- whether example outputs are smoke-test artifacts or source-backed conclusions

## Release Boundaries

- Do not tag a release with failing tests, lint, or evals unless the release notes explicitly identify the failure and the release is marked pre-release.
- Do not describe planned features as implemented features.
- Do not claim exhaustive literature review capability.
- Do not claim actual Codex/GPT-5.4 canary validation unless the canary ran and human review was recorded.
- Do not claim actual-run acceptance unless the release-gate front matter says `actual_run_acceptance_passed: true` and at least one real canary is accepted.
- For v0.4, do not claim actual-run acceptance unless multiple real Codex/GPT-5.4 campaigns are accepted and the campaign release gate passes.
- For v0.5, do not claim live-literature quality unless accepted live-source campaigns and expert reviews prove it.
- For v0.6, do not claim empirical validation unless executed experiment artifacts, failed/negative path artifacts, statistical analysis, reproducibility checks, and result-claim links prove it.
- For v0.7, do not claim real benchmark execution or replication unless a real or benchmark-like non-fixture run, compute logs, benchmark artifacts, comparison/error analysis, and replication package prove it.
- For v0.8, do not claim submission-readiness unless claim traceability, citation/BibTeX audit, artifact-backed results, artifact evaluation package state, blinding checks when applicable, reviewer-objection handling, and human review prove it.
- Do not claim camera-ready status without explicit acceptance metadata and a completed camera-ready checklist.
- For v0.9, do not claim external pilot success unless one real topic completed the required pilot path with either a defensible direction or an evidence-backed refusal.
- Do not claim v1 readiness unless the v1 readiness gate passes as `ready` or `ready_with_explicit_scope`.
- For v2, do not claim idea-discovery success unless at least one idea candidate is accepted by the v2 release gate.
- For v2, if no idea candidate is accepted, record explicit idea-discovery failure and plan v2.0.1 or v2.1 instead of claiming success.
- For v2.1, do not claim selected-idea execution success unless the selected idea is frozen and a runnable benchmark smoke path produces result artifacts, analysis, reviewer critique, and a manuscript package update.
- For v2.1, do not claim final scientific results, real-world benchmark validity, monitor superiority, or publication readiness from synthetic fixtures or smoke runs.
- Do not publish generated `runs/`, caches, or local environment artifacts as source.
