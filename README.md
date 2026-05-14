# GapForge

GapForge v1.0 is a stable, evidence-gated research ideation OS. It turns a broad topic into auditable research state: papers, notes, claims, evidence, gaps, novelty dossiers, experiment plans, benchmark records, manuscript packages, reviewer objections, release gates, and reports.

GapForge v2 is the Idea Discovery Engine line. v2 searches across topic portfolios, generates and mutates idea candidates, expands constructive gaps and cross-domain transfers, runs novelty/counterevidence loops and idea tournaments, captures human preference feedback, and measures idea yield. The v2 principle is simple: GapForge should try much harder to find a good idea, but it must not force a bad one.

GapForge v1.0 supports:

- literature campaigns
- Codex/GPT-5.4 assisted research workflows
- novelty and prior-work gates
- experiment execution
- benchmark and replication packages
- manuscript and artifact evaluation packages
- correct refusal outcomes
- release gates and compatibility audits

GapForge v2 planning docs:

- [v2 roadmap](docs/V2_ROADMAP.md)
- [v2 acceptance criteria](docs/V2_ACCEPTANCE_CRITERIA.md)
- [v2 idea discovery](docs/V2_IDEA_DISCOVERY.md)
- [v2 idea yield metrics](docs/V2_IDEA_YIELD_METRICS.md)
- [v2 research agenda mode](docs/V2_RESEARCH_AGENDA_MODE.md)
- [v2 human feedback](docs/V2_HUMAN_FEEDBACK.md)
- [v2.1 selected idea execution roadmap](docs/V2_1_ROADMAP.md)
- [v2.1 selected idea](docs/V2_1_SELECTED_IDEA.md)
- [v2.1 benchmark specification](docs/V2_1_BENCHMARK_SPEC.md)
- [v2.1 acceptance criteria](docs/V2_1_ACCEPTANCE_CRITERIA.md)
- [v2.2 pilot benchmark roadmap](docs/V2_2_ROADMAP.md)
- [v2.2 pilot benchmark specification](docs/V2_2_PILOT_BENCHMARK.md)
- [v2.2 acceptance criteria](docs/V2_2_ACCEPTANCE_CRITERIA.md)
- [v2.2 power and sample-size plan](docs/V2_2_POWER_AND_SAMPLE_SIZE.md)
- [v2.2 reviewer blockers](docs/V2_2_REVIEWER_BLOCKERS.md)
- [v2.3 main-scale benchmark roadmap](docs/V2_3_ROADMAP.md)
- [v2.3 main benchmark specification](docs/V2_3_MAIN_BENCHMARK.md)
- [v2.3 related-work completion plan](docs/V2_3_RELATED_WORK_COMPLETION.md)
- [v2.3 publication-readiness gate](docs/V2_3_PUBLICATION_READINESS.md)
- [v2.3 acceptance criteria](docs/V2_3_ACCEPTANCE_CRITERIA.md)
- [v2.4 related-work remediation roadmap](docs/V2_4_ROADMAP.md)
- [v2.4 related-work completion](docs/V2_4_RELATED_WORK_COMPLETION.md)
- [v2.4 publication remediation](docs/V2_4_PUBLICATION_REMEDIATION.md)
- [v2.4 acceptance criteria](docs/V2_4_ACCEPTANCE_CRITERIA.md)
- [v2.5 real benchmark grounding roadmap](docs/V2_5_ROADMAP.md)
- [v2.5 real benchmark grounding](docs/V2_5_REAL_BENCHMARK_GROUNDING.md)
- [v2.5 venue-style manuscript](docs/V2_5_VENUE_STYLE_MANUSCRIPT.md)
- [v2.5 OpenReview reviewer dataset](docs/V2_5_OPENREVIEW_REVIEWER_DATASET.md)
- [v2.5 acceptance criteria](docs/V2_5_ACCEPTANCE_CRITERIA.md)

GapForge is intentionally skeptical. It can recommend a direction only when evidence gates support one, and it can refuse when literature coverage, novelty evidence, or empirical support is insufficient. It is not an exhaustive autonomous literature reviewer, and it must not fabricate citations, experimental results, venue acceptance, publication readiness, or novelty claims. Deterministic and offline-safe paths remain the default.

## Version Lineage

- **v0.1**: deterministic research OS foundation with run state, source connectors, skill orchestration, claim ledger, novelty gate, evals, and reports.
- **v0.2**: full-text evidence and novelty dossier upgrade with PDF artifacts, sections, evidence spans, source coverage, citation graph, gap evidence matrices, human review, and strict reports.
- **v0.3**: semantic plus LLM-assisted plus multi-run project-memory upgrade with hybrid retrieval, source policy profiles, active loop decisions, related-work matrices, direction maturation, protocols, review queues, dashboard, and paper packages.
- **v0.4**: actual Codex/GPT-5.4 agentic campaign release path with campaign-level state, task packs, direct/handoff runner support, strict validated import, repair/rollback, campaign dashboards/reports, v4 evals, and release gates. Fake-agent success still does not count as real-run acceptance.
- **v0.5**: real literature campaign quality layer. v0.5 validates multi-step live-literature campaigns, source coverage quality, closest-prior-work recall, real-paper citation grounding, expert review, experiment protocol quality, and correct rejection behavior when novelty is weak.
- **v0.6**: experiment execution and empirical validation layer. v0.6 distinguishes protocols, scaffolds, smoke runs, pilot/main runs, failed/negative experiments, statistical analyses, reproducibility checks, and artifact-backed empirical claims.
- **v0.7**: real benchmark execution and replication layer. v0.7 distinguishes fixture smoke, local benchmark, full benchmark, failed jobs, underpowered runs, benchmark comparison, replication packages, and real/local public benchmark validation.
- **v0.8**: manuscript, artifact evaluation, and reviewer-rebuttal layer. v0.8 distinguishes manuscript-ready, submission-ready, and camera-ready while requiring claim, citation, result, artifact, blinding, and human-review traceability.
- **v0.9**: external pilot and v1-readiness layer. v0.9 runs one real topic through the full workflow and accepts either a defensible direction or an evidence-backed refusal, with migration, CLI, docs, artifact hygiene, external feedback, and v1-readiness gates.
- **v0.9.1**: migration remediation patch. v0.9.0 was not v1-ready because the migration/backward compatibility audit failed; v0.9.1 adds historical fixtures, versioned migrators, backup snapshots, and compatibility audit v2 without adding research features.
- **v1.0.0**: stable evidence-gated release. v1.0.0 passes the v1 readiness gate after v4-v9 evidence, compatibility audit v2, CLI/docs audits, artifact hygiene checks, and an accepted correct-refusal external pilot.
- **v2.0.0**: Idea Discovery Engine release line. v2 actively searches across topic portfolios for defensible idea candidates using mutation, constructive gap creation, cross-domain transfer, Codex/GPT-5.4 synthesis tasks, active search control, novelty/counterevidence loops, idea tournaments, human feedback, research agenda fallback, and idea yield metrics. The v2 gate requires at least one accepted idea candidate or explicit idea-discovery failure routed to v2.0.1 or v2.1 planning.
- **v2.0.1**: CI fixture tracking patch. v2.0.1 keeps historical migration fixture JSONs available in clean checkouts without changing product behavior, idea-discovery claims, or the v2.0 selected idea.
- **v2.1.0**: Selected Idea Execution release. v2.1 freezes the accepted v2.0 idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits` and turns it into a benchmark specification, threat model, task/data generator, baseline suite, sequential specificity metrics, power plan, experiment workspace, smoke benchmark run, result analysis, reviewer critique, and manuscript package update. The smoke path is runnable and artifact-backed, but remains synthetic and underpowered.
- **v2.2.0**: Pilot-Scale Benchmark Study release. v2.2 requires a pilot run manifest, expanded honest-agent null distribution, expanded collusive-agent alternatives, stronger hard negatives, full baseline monitor suite, pilot result artifacts, sequential low-FPR uncertainty analysis, prior-work and related-work attachment, reviewer-blocker classification, and a pilot manuscript package. It must not claim deployment validity, unsupported `alpha=0.001` operational specificity, main benchmark maturity, or publication readiness from synthetic pilot data.
- **v2.3.0**: Main-Scale Benchmark and Publication-Readiness Upgrade. v2.3 directly addresses v2.2 blockers by requiring a main-scale sample-size plan, an explicit `alpha=0.001` power-or-drop decision, real prior-work records for required categories, related-work matrix completion, stronger baselines, main dataset generation or no-go, main benchmark execution or no-go, publication-readiness reviewer panel, manuscript package upgrade, and a clear go/no-go recommendation.
- **v2.4.0**: Related Work Completion and Publication-Readiness Remediation. v2.4 starts from the v2.3 `revise_benchmark` outcome: the synthetic main benchmark completed and powered `alpha=0.001`, but publication readiness remained blocked because required related-work categories had no real attached paper records. v2.4 requires real category-specific search campaigns, real paper attachment, closest-prior-work dossier refresh, novelty and benchmark positioning updates, contribution claim softening when needed, reviewer rerun, manuscript revision, and an updated go/no-go decision. It must not claim publication readiness from fallback-only related work, hide prior work, weaken synthetic/deployment limits, or invent citations.
- **v2.5.0**: Real Benchmark Grounding, Venue-Style Paper, and OpenReview Reviewer Training. v2.5 starts from the v2.4 publication-candidate package and requires at least one vetted benchmark adapter, one venue-style manuscript package, and one OpenReview-calibrated reviewer pass. It treats known datasets as bounded grounding evidence, venue style as structure/rhetoric/format rather than copied prose, and reviewer modeling as critique calibration rather than truth generation or acceptance prediction.

## Why Not Just Summarization?

A summarizer compresses papers. GapForge tracks beliefs, evidence, uncertainty, and rejected ideas.

GapForge keeps:

- durable run and project directories
- normalized paper metadata, local artifacts, parsed sections, and evidence spans
- a claim ledger with support, counterevidence, confidence, and verification state
- source coverage and stopping assessments
- closest-prior-work novelty dossiers
- human review records and review queues
- research directions that mature from seed to manuscript-ready or rejected
- final reports that distinguish evidence-backed claims from hypotheses

The system is intentionally skeptical. It should attack an idea before recommending it, and it should not claim novelty until closest prior work and missing searches are explicit.

## Installation

Requires Python 3.11+.

```bash
git clone <repo-url> GapForge
cd GapForge
python -m venv .venv
source .venv/bin/activate
make install
```

Equivalent:

```bash
python -m pip install -e ".[dev]"
```

## v0.3 Quickstart

Run a deterministic, offline-safe v0.3 smoke workflow:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
gapforge report --strict
gapforge coverage
```

Run the full project-level offline v0.3 smoke target:

```bash
make v3-smoke
```

`make v3-smoke` initializes a temporary project, runs the staged v0.3 path offline with a small budget, builds the project retrieval index, writes the project report, and generates the static dashboard. It checks for `project_report.md`, `source_coverage.md`, `final_report.md`, `direction_maturity_report.md`, `related_work_matrix.md`, `review_queue.md`, and `dashboard/index.html`. Active-loop decisions are generated only by `gapforge run --v3 --active` and are written to `active_decisions.md`.

Expected behavior:

- network PDF/search expansion steps skip with coverage warnings
- retrieval index artifacts are built from fallback/offline state
- strict report remains conservative and may refuse a top direction
- outputs are smoke-test artifacts, not real literature conclusions

## v0.4 Campaign Quickstarts

v0.4 introduces project-level campaigns. Campaigns coordinate search, source coverage, retrieval, Codex task packs, validated imports, novelty loops, reviewer loops, experiment protocols, code-task handoff, dashboards, and human acceptance. For the complete Codex command path, see [docs/CODEX_QUICKSTART.md](docs/CODEX_QUICKSTART.md).

### Deterministic Campaign

This is the safest first run. It does not use Codex/GPT-5.4 and does not count as actual-run acceptance.

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge init-project "v4 deterministic campaign"
gapforge campaign-create "low false positive collusion detection" --project-id v4-deterministic-campaign
gapforge campaign-run --campaign-id <campaign-id> --mode deterministic --max-iterations 3
gapforge campaign-report --campaign-id <campaign-id>
gapforge dashboard --project-id v4-deterministic-campaign --include-actual-runs
```

### Fake-Agent Campaign Smoke

Fake-agent mode is CI-safe. It exercises task-pack, schema, validation, import, and campaign-state plumbing. It is never evidence that Codex/GPT-5.4 worked.

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge eval --v4 --write-report
```

### Codex Task-Pack Actual-Run Workflow

Use this when no stable direct Codex runner is configured. It can count as real actual-run evidence only after Codex/GPT-5.4 writes outputs, GapForge validates/imports them, a human attests the task, and campaign review accepts the result.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge latest-codex-task --campaign-id <campaign-id>
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 manually and write JSON outputs into outputs/.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge actual-run-status --campaign-id <campaign-id>
```

If validation fails, repair without weakening validation:

```bash
gapforge codex-doctor --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
gapforge validate-repair-output --repair-id <repair-id>
gapforge import-repair-output --repair-id <repair-id>
```

### Direct Runner Workflow

Use direct mode only when a trusted local Codex command runner is configured. Preview it before execution.

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=direct
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4
export GAPFORGE_CODEX_COMMAND='codex run --model {model} --task-pack {task_pack} --output-dir {outputs_dir}'
gapforge setup-codex
gapforge codex-command-preview --task-id <task-id>
gapforge codex-run --task-id <task-id> --direct --dry-run
gapforge codex-run --task-id <task-id> --direct
gapforge validate-import-all --task-id <task-id>
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
```

### Campaign Acceptance and Release Gate

Campaign completion is not acceptance. Acceptance requires validated imports, actual-run attestation when task-pack/manual-handoff is used, source coverage, explicit stop reason, campaign report, and human review. Fake-agent campaigns are excluded.

```bash
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id <campaign-id>
gapforge v4-release-gate --project-id <project-id> --write-report
gapforge v4-release-gate --explain
gapforge v4-release-gate --next-commands
```

`gapforge v4-release-gate` requires deterministic CI evidence, a passed fake-agent campaign canary, at least three accepted real Codex/GPT-5.4 campaigns, one experiment-ready campaign, one strict-refusal campaign, and one manual-PDF/full-text campaign. If those artifacts are missing, the gate fails closed.

Current verification status from the May 6, 2026 local pass:

- Deterministic checks passed: `make format`, `make format-check`, `make lint`, `make typecheck`, `make test`, `make eval`, `gapforge eval --v2 --write-report`, `gapforge eval --v3 --write-report`, `gapforge eval --v4 --write-report`, `make coverage`, `make v2-smoke`, `make v3-smoke`, and `make v4-smoke`.
- Fake-agent campaign canary passed with valid schema validation.
- Direct Codex/GPT-5.4 execution was available through the local `codex` CLI.
- Three real Codex/GPT-5.4 workflow canaries were validated/imported, attested, and human-reviewed: one refusal canary, one manual-PDF/full-text reading canary, and one fixture-backed experiment-ready canary.
- `gapforge v4-release-gate --write-report --json` passed with 3 accepted real campaigns and no blockers. These are release-gate workflow canaries, not evidence of exhaustive literature-review quality.

### v0.4.1 Codex Workflow Commands

v0.4.1 is scoped to Codex workflow reliability. The main commands are:

```bash
gapforge setup-codex
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge codex-doctor --task-id <task-id>
gapforge validate-import-all --task-id <task-id>
gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff --print-prompt
```

The v0.4.1 golden path is the single-task handoff canary:

```bash
export GAPFORGE_ENABLE_REAL_RUNS=1
export GAPFORGE_AGENT_MODE=task-pack
export GAPFORGE_AGENT_NAME=codex
export GAPFORGE_CODEX_MODEL=gpt-5.4

gapforge setup-codex
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
# Run Codex/GPT-5.4 and write JSON outputs to outputs/.
gapforge validate-import-all --task-id <task-id>
gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"
gapforge campaign-canary-complete --canary-id <canary-id>
```

See `docs/CODEX_QUICKSTART.md`, `docs/V0_4_1_CODEX_FIX_PLAN.md`, `docs/V0_4_1_CODEX_ACCEPTANCE.md`, and `docs/V0_4_1_CODEX_TROUBLESHOOTING.md`.

## v0.5 Real Literature Campaign Quality

v0.4.1 proves the actual Codex/GPT-5.4 workflow path. It does not prove broad live-literature research quality. v0.5 is scoped to that next step.

v0.5 acceptance must require live-literature campaigns that:

- search live source connectors and record every query/failure
- satisfy field-specific source policy or refuse recommendation
- find and cite closest prior work, or explicitly mark novelty unknown
- ground real-paper claims in paper IDs and EvidenceSpan locators when full text is available
- build related-work matrices and experiment protocols for recommended directions
- undergo human expert review
- reject or downgrade weak novelty, poor coverage, and unsupported claims

The v0.5 docs are:

- `docs/V0_5_ROADMAP.md`
- `docs/V0_5_ACCEPTANCE_CRITERIA.md`
- `docs/V0_5_REAL_LITERATURE_CAMPAIGNS.md`
- `docs/V0_5_QUALITY_GATES.md`
- `docs/V0_5_LIVE_SOURCE_POLICY.md`

Normal CI remains deterministic and offline. Fixture-only canaries and fake-agent campaigns do not count as v0.5 live-literature quality.

Latest v0.5 validation status: `gapforge v5-release-gate --write-report --json` passed locally on May 6, 2026. The accepted quality campaigns were one experiment-ready low-FPR collusion campaign and one conservative refusal campaign. This is live-literature release-gate acceptance, not a claim of exhaustive literature review.

## v0.6 Experiment Execution and Empirical Validation

v0.5 can say a direction is experiment-ready. v0.6 says whether an experiment actually ran, what artifacts it produced, how results were analyzed, whether the run is reproducible, and whether empirical claims are supported by result artifacts.

The v0.6 docs are:

- `docs/V0_6_ROADMAP.md`
- `docs/V0_6_ACCEPTANCE_CRITERIA.md`
- `docs/V0_6_EXPERIMENT_EXECUTION.md`
- `docs/V0_6_EMPIRICAL_VALIDATION.md`
- `docs/V0_6_REPRODUCIBILITY_POLICY.md`
- `docs/releases/v0.6.0.md`
- `docs/releases/v0.6.0-empirical-validation.md`

Core boundary:

- an experiment protocol is not an executed experiment
- a scaffold is not an executed experiment
- a smoke run validates wiring only; it is not empirical success
- pilot/main results require execution records and result artifacts
- failed or negative experiments are first-class results
- no empirical claim is supported unless a run record and result artifact exist
- generated paper packages must separate real results from placeholders and hypothetical expected results

Minimal local workflow:

```bash
gapforge experiment-workspace-create --project-id <project-id> --direction-id <direction-id>
gapforge dataset-register --workspace-id <workspace-id> --name "fixture examples" --path data/fixture.csv --dataset-type fixture --license MIT
gapforge baseline-register --workspace-id <workspace-id> --name "heuristic baseline" --baseline-type heuristic --implementation-path code/src/baselines.py
gapforge metric-register --workspace-id <workspace-id> --name "false positive rate"
gapforge scaffold-experiment-code --workspace-id <workspace-id>
gapforge experiment-manifest-create --workspace-id <workspace-id> --run-type smoke --command "python code/src/run_experiment.py" --expected-output results/smoke_metrics.json --random-seed 123
gapforge experiment-run --workspace-id <workspace-id> --manifest-id <manifest-id>
gapforge parse-results --execution-id <execution-id>
gapforge analyze-results --execution-id <execution-id>
gapforge reproducibility-check --execution-id <execution-id>
gapforge empirical-review --execution-id <execution-id>
gapforge export-paper-package-v2 --workspace-id <workspace-id>
gapforge v6-release-gate --write-report --json
```

Codex/GPT-5.4 can implement experiment code through constrained workspace code tasks:

```bash
gapforge experiment-code-task --workspace-id <workspace-id> --type implement_metric
gapforge experiment-code-handoff --task-id <task-id>
gapforge experiment-code-import --task-id <task-id>
```

Codex code tasks are bounded to `experiment_workspaces/<workspace-id>/code/`. They may create code, tests, configs, and analysis scripts; they must not create fake result metrics, claim an experiment ran, or edit evidence/claim state outside the validated import path.

The v0.6 release gate requires at least one executed fixture experiment and one failed or negative experiment path, while keeping CI free of expensive experiment execution.

Latest v0.6 validation status: fixture experiment execution passed locally on May 6, 2026, and `gapforge v6-release-gate --write-report --json` passed. One real Codex/GPT-5.4 experiment-code task was executed and imported as a validated workspace-bounded implementation patch. No real-world main experiment was run, and no real empirical result is claimed.

## v0.7 Real Benchmark Execution and Replication

v0.6 validates experiment execution mechanics. v0.7 validates benchmark execution and replication plumbing: external data policies, compute environments, sweeps, ablations, comparison tables, error/slice analysis, low-FPR power checks, and replication packages.

The v0.7 docs are:

- `docs/V0_7_ROADMAP.md`
- `docs/V0_7_ACCEPTANCE_CRITERIA.md`
- `docs/V0_7_REAL_BENCHMARKS.md`
- `docs/V0_7_COMPUTE_AND_REPLICATION.md`
- `docs/V0_7_BENCHMARK_RELEASE_GATE.md`
- `docs/releases/v0.7.0.md`
- `docs/releases/v0.7.0-benchmark-replication.md`

Core boundary:

- fixture smoke validates wiring only
- local benchmark may count when it uses real or benchmark-like non-fixture data with complete artifacts
- full benchmark requires intended data, baselines, metrics, compute records, and analysis
- replication requires rerunnable package instructions, checksums/version IDs, expected artifacts, and review
- no GPU, cluster, live source, or external download is required in normal CI
- no large dataset should be downloaded without explicit user approval
- no benchmark success should be claimed from fixture runs

v0.7 must preserve v5 literature gates and v6 empirical claim gates. Benchmark output should become a supported claim only when execution records, result artifacts, statistical analysis, and review justify it.

Minimal fixture benchmark smoke:

```bash
export GAPFORGE_DISABLE_NETWORK=1
gapforge benchmark-canary-run --profile fixture_benchmark_success
gapforge benchmark-canary-run --profile fixture_benchmark_failure
gapforge benchmark-canary-run --profile low_fpr_underpowered_benchmark
gapforge benchmark-canary-run --profile replication_package_canary
gapforge v7-release-gate --write-report --json
```

Opt-in real/local public benchmark validation:

```bash
gapforge benchmark-canary-run --profile local_public_small_benchmark --real --accept-download
gapforge v7-release-gate --write-report --json --claim-real
```

Latest v0.7 validation status: fixture benchmark gate and opt-in real/local public benchmark gate passed locally on May 7, 2026. The real benchmark canary used explicit dataset consent, a cached public UCI Iris download, artifact-backed metrics and predictions, benchmark comparison, error analysis, and replication package verification. This validates the benchmark-and-replication path; it is not a SOTA claim, a large-scale benchmark study, a GPU/cluster validation, or independent replication by another researcher.

## v0.8 Manuscript, Artifact Evaluation, and Rebuttal Workflow

v0.8 is the manuscript release boundary. It turns project, literature, experiment, benchmark, and replication state into auditable manuscript and artifact-evaluation packages without hiding missing work.

The v0.8 docs are:

- `docs/V0_8_ROADMAP.md`
- `docs/V0_8_ACCEPTANCE_CRITERIA.md`
- `docs/V0_8_MANUSCRIPT_WORKFLOW.md`
- `docs/V0_8_ARTIFACT_EVALUATION.md`
- `docs/V0_8_REBUTTAL_WORKFLOW.md`
- `docs/releases/v0.8.0.md`
- `docs/releases/v0.8.0-manuscript-submission.md`

Core boundary:

- manuscript-ready means a draft package can be assembled, possibly with visible blockers
- submission-ready means the venue profile, traceability, citations, results, artifact package, blinding, reviewer-objection, and human-review gates pass
- camera-ready means a post-acceptance checklist has been completed after explicit acceptance metadata
- manuscript claims must trace to claim ledger entries, evidence spans, result artifacts, benchmark records, reviewer decisions, and citations
- figures and tables must be generated from recorded result artifacts or explicitly labeled conceptual placeholders
- artifact evaluation packages must be generated from replication and workspace state
- rebuttal plans must answer reviewer objections with evidence, changes, experiments, or honest concessions
- normal CI must remain deterministic, offline, and free of LaTeX, GPU, cluster, live-source, large-download, and live-LLM requirements

v0.8 must not fabricate results, citations, BibTeX, novelty, rebuttal evidence, venue acceptance, or camera-ready status. It must not mark a manuscript submission-ready when novelty, result, reproducibility, artifact, citation, blinding, or human-review gates fail.

## v0.9 External Pilot and v1 Readiness

v0.9 is the first real external pilot release. It should run GapForge on one real topic from broad framing through live literature, novelty review, protocol, execution path, artifact package, manuscript draft, reviewer/rebuttal plan, external feedback, and v1 readiness assessment.

The recommended pilot topic is `low false-positive collusion detection in LLM multi-agent systems`.

The v0.9 docs are:

- `docs/V0_9_ROADMAP.md`
- `docs/V0_9_ACCEPTANCE_CRITERIA.md`
- `docs/V0_9_EXTERNAL_PILOT.md`
- `docs/V0_9_V1_READINESS.md`
- `docs/V0_9_1_MIGRATION_REMEDIATION.md`
- `docs/V1_MIGRATION_AND_COMPATIBILITY.md`
- `docs/V0_9_FAILURE_MODES.md`
- `docs/pilots/low_fpr_collusion/PILOT_SPEC.md`
- `docs/pilots/low_fpr_collusion/ACCEPTANCE_CRITERIA.md`
- `docs/pilots/low_fpr_collusion/REVIEW_CHECKLIST.md`

Core boundary:

- v0.9 may pass with a defensible direction or an evidence-backed refusal
- fixture-only results validate workflow mechanics only
- no research direction should be forced when novelty, coverage, or feasibility is weak
- small real runs require run records, logs, result artifacts, analysis, and review before supporting empirical claims
- external reviewer or pilot feedback is required
- migration/backward compatibility from v0.1 through v0.9 state must be audited with compatibility audit v2
- CLI/docs usability and artifact hygiene issues found during the pilot must be fixed, scoped, or recorded
- v1 cannot be claimed until the v1 readiness gate passes

Suggested pilot path:

```bash
gapforge pilot-list
gapforge pilot-spec --name low_fpr_collusion
gapforge pilot-run --name low_fpr_collusion
gapforge pilot-status --name low_fpr_collusion
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge live-source-diagnostic --topic "low false-positive collusion detection in LLM multi-agent systems" --source-profile ai_safety --write-report
gapforge real-literature-run --profile live_low_fpr_collusion
gapforge campaign-report --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --reviewer "<expert>"
gapforge real-literature-acceptance --campaign-id <campaign-id>
gapforge idea-gate --pilot-id <pilot-id>
gapforge pilot-outcome --pilot-id <pilot-id>
gapforge pilot-review --pilot-id <pilot-id> --accept-outcome --reviewer-role external_reviewer
gapforge pilot-report --pilot-id <pilot-id>
gapforge compatibility-audit --v2 --write-report
gapforge migrate-all --dry-run
# Review the planned MigrationRecord output before applying.
gapforge migrate-all --apply
gapforge migration-report
gapforge cli-audit --write-report
gapforge docs-audit --write-report
gapforge v1-readiness --write-report --json
```

If the v0.9 CLI surface is incomplete, the pilot must record the gap as a CLI cleanup blocker rather than pretending the command exists in a validated release path.

v1 readiness must not be claimed from the pilot alone. The v2 compatibility audit must pass, and warning-only generated local artifacts are acceptable only when they are ignored and not curated release evidence.

### v0.5 Live Literature Campaign Workflow

Use v0.5 when you want GapForge to assess whether a real literature campaign is research-useful, not merely whether the workflow ran.

```bash
gapforge real-literature-profiles
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge source-health --topic "low false positive collusion detection" --source arxiv
gapforge live-source-diagnostic --topic "low false positive collusion detection in LLM agents" --source-profile ai_safety --write-report
gapforge real-literature-run --profile live_low_fpr_collusion
gapforge real-literature-status --record-id <record-id>
```

The dry run does not contact live sources or spend Codex budget. It previews expected source checks, search rounds, Codex tasks, artifacts, likely blockers, commands, and acceptance requirements.

### v0.5 Search and Source Health Workflow

Plan searches before asking Codex to synthesize:

```bash
gapforge plan-search-strategy "low false positive collusion detection in LLM agents" --source-profile ai_safety
gapforge execute-search-strategy --run-id <run-id> --strategy-id <strategy-id>
gapforge search-rounds --run-id <run-id>
gapforge canonicalize-papers --run-id <run-id>
gapforge prior-work-recall --run-id <run-id> --gap-id <gap-id>
```

If `GAPFORGE_DISABLE_NETWORK=1`, source health and execution commands must report disabled/skipped state. That can support offline smoke testing, but not live-literature acceptance.

### v0.5 Quality Review Workflow

Workflow acceptance and research-quality acceptance are separate:

```bash
gapforge campaign-report --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --accept-quality --reviewer "<expert>"
gapforge real-literature-acceptance --campaign-id <campaign-id>
gapforge v5-release-gate --project-id <project-id> --write-report
```

Human reviewers should reject campaigns with fake citations, unsupported high-confidence claims, obvious missed prior work, overclaimed novelty, poor source coverage hidden by report language, or experiment protocols lacking baselines/metrics/falsification.

### v0.5 Programmatic API

The same workflow is scriptable without shelling out:

```python
from gapforge import api

diagnostic = api.source_health("low false positive collusion", profile="ai_safety")
strategy = api.plan_search_strategy("low false positive collusion", "ai_safety")
record = api.run_real_literature_campaign("live_low_fpr_collusion")
gate = api.v5_release_gate()
```

API calls are thin wrappers over the same managers used by the CLI. Tests can pass mocked sources; live network is never required for CI.

## Project Memory Workflow

Use project memory when several runs belong to one research program:

```bash
gapforge init-project "monitoring collusion research"
gapforge run "low false positive collusion detection" --v3 --project-id monitoring-collusion-research --max-papers 20
gapforge sync-project-memory --project-id monitoring-collusion-research
gapforge project-status --project-id monitoring-collusion-research
gapforge project-report --project-id monitoring-collusion-research
```

Project memory deduplicates papers across runs, preserves rejected ideas and human decisions, and stores research directions that can mature over time. Prior project memory is context, not newly verified evidence.

## Hybrid Retrieval Workflow

Build and inspect a local hybrid lexical/semantic index:

```bash
gapforge build-index --run-id <run-id>
gapforge search-index --run-id <run-id> "low false positive evaluation benchmark" --top-k 20
gapforge explain-retrieval --run-id <run-id> "closest prior work low FPR"
```

For project memory:

```bash
gapforge build-index --project-id <project-id>
gapforge search-index --project-id <project-id> "monitor evasion limitation" --top-k 20
```

The default semantic path uses deterministic local hash embeddings. Live embedding APIs are not required.

## Optional LLM Workflow

LLM-backed skills are opt-in. Tests and default runs do not require live model calls.

```bash
export GAPFORGE_LLM_MODE=prompt-pack   # off|prompt-pack|fake|provider
gapforge prompt-pack --run-id <run-id> --skill deep-reading
gapforge read-llm --run-id <run-id> --tier 1 --dry-run-prompts
```

Fake mode is deterministic:

```bash
export GAPFORGE_LLM_MODE=fake
gapforge read-llm --run-id <run-id> --tier 1 --fake
gapforge mine-gaps-llm --run-id <run-id> --fake
gapforge novelty-check-llm --run-id <run-id> --all --fake
```

Provider mode is optional and must validate JSON before state is updated. Model outputs must cite paper IDs and EvidenceSpan locators when source-backed. Hidden chain-of-thought must not be requested or stored.

## Codex/GPT-5.4 Agent Run Modes

GapForge separates deterministic runs, fake-agent tests, task-pack handoff, and direct Codex execution:

```bash
gapforge run "topic" --v3 --mode deterministic
GAPFORGE_DISABLE_NETWORK=1 gapforge campaign-canary-run --profile fake_agent_campaign_regression
gapforge campaign-canary-run --profile single_task_codex_handoff --real
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge codex-run --task-id <task-id> --direct --dry-run
```

Deterministic mode is the default. Fake-agent mode is CI-safe and validates task-pack/schema plumbing. Task-pack handoff can count only after real Codex/GPT-5.4 output, validation, import, attestation, and human review. Direct mode can count only after valid output/import and human review.

## Deterministic Tests vs Actual Runs

GapForge separates automated validation from actual research-agent validation:

- **Level 0 deterministic tests**: no LLM, CI-safe, validates code, schemas, persistence, reports, and evals.
- **Level 1 offline smoke tests**: no LLM and no network, validates orchestration safety.
- **Level 2 fake LLM tests**: fake model only, validates JSON guards and evidence gates.
- **Level 3 prompt-pack/task-pack dry runs**: no live calls, validates Codex/GPT-5.4 prompts and schemas.
- **Level 4 Codex/GPT-5.4 canary runs**: real model/agent, private/manual, validates actual LLM-assisted research skills.
- **Level 5 human-reviewed acceptance**: human review of canary outputs and recorded decisions.

CI must not require Codex/GPT-5.4. Actual Codex/GPT-5.4 assisted runs are required before a release can claim real-run validation, but they are not part of normal automated tests. If Codex/GPT-5.4 is unavailable, actual-run validation has not passed. Never fake a canary pass.

For v0.4, the bar is higher: fake-agent tests and prompt-pack dry runs remain necessary but are not sufficient. v0.4 actual-run acceptance requires multiple real Codex/GPT-5.4 agentic campaigns with validated imports, campaign artifacts, strict-report checks, and human acceptance reviews. A task-pack handoff may support acceptance only after real Codex/GPT-5.4 outputs are imported, validated, attested, and reviewed.

See:

- `docs/CODEX_QUICKSTART.md`
- `docs/V0_3_REAL_RUN_ACCEPTANCE.md`
- `docs/V0_3_CANARY_RUNS.md`
- `docs/V0_4_ROADMAP.md`
- `docs/V0_4_ACCEPTANCE_CRITERIA.md`
- `docs/V0_4_REAL_RUN_ACCEPTANCE.md`
- `docs/V0_4_AGENTIC_CAMPAIGNS.md`
- `docs/CODEX_RESEARCH_AGENT.md`
- `docs/REAL_RUN_REVIEW_CHECKLIST.md`
- `docs/releases/v0.3.0-real-run-acceptance.md`
- `docs/releases/v0.4.0-real-run-acceptance.md`
- `docs/releases/v0.4.0.md`

Latest v0.4 validation status: deterministic checks, the fake-agent campaign canary, and the v0.4 actual-run release gate passed locally on May 6, 2026. The accepted real Codex/GPT-5.4 campaigns were workflow canaries with conservative/fixture-backed outputs; they validate the actual-run path, not exhaustive autonomous research quality.

## Manuscript Package Workflow

Legacy paper-package exports are starter kits, not finished papers:

```bash
gapforge create-direction --project-id <project-id> --gap-id <gap-id>
gapforge related-work-matrix --project-id <project-id> --direction-id <direction-id>
gapforge mature-direction --project-id <project-id> --direction-id <direction-id>
gapforge experiment-protocol --project-id <project-id> --direction-id <direction-id>
gapforge review-panel --project-id <project-id> --direction-id <direction-id>
gapforge export-paper-package --project-id <project-id> --direction-id <direction-id>
```

Exports include outlines, related-work matrix, protocol, limitations, reviewer objections, rebuttal plan, bibliography, claim ledger, and evidence index. They must not invent results.

v0.8 extends this into a first-class manuscript workflow:

```bash
gapforge manuscript-create --project-id <project-id> --direction-id <direction-id> --workspace-id <workspace-id> --title "Paper title"
gapforge bibliography-build --manuscript-id <manuscript-id>
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

Readiness terms are strict:

- **Manuscript-ready**: a durable draft exists and can be inspected, but blockers may remain.
- **Review-ready**: internal reviewer and artifact checks have run and remaining issues are visible.
- **Submission-ready**: the venue-aware checklist, traceability, citation validity, result artifacts, artifact evaluation package, anonymization if required, and unsupported-claim gates pass.
- **Camera-ready**: post-review/rebuttal blockers are addressed. It does not imply venue acceptance unless an external acceptance record exists.

Manuscript citations must resolve to known `Paper` records. Result claims must link execution/result artifacts. Reviewer rebuttals must cite evidence or request fixes; they must not invent answers.

## v2.1 Selected Idea Execution

v2.1 is the Selected Idea Execution release for the accepted v2.0 candidate:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`

The v2.1 path is benchmark-first. It should define and smoke-run a concrete research artifact before any stronger claim is allowed:

- benchmark specification
- threat model and observability assumptions
- honest-agent baseline distribution
- collusive-agent scenario distribution
- hard-negative benign scenarios
- sequential audit protocol
- low-FPR specificity metrics
- honest baseline monitors
- power and sample-size plan
- experiment workspace and runnable smoke manifest
- result artifacts, analysis, reviewer critique, and manuscript package update

v2.1 must distinguish smoke, pilot, and main benchmark levels. Smoke runs prove only that the benchmark path runs and writes artifacts. They do not prove real-world collusion benchmark validity, final scientific results, method superiority, or publication readiness.

Current maturity statement: v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`; v2.1 executes that selected idea as a benchmark artifact workflow. The synthetic smoke benchmark is not a final research result, low-FPR claims require power, and benchmark validity limitations remain open until pilot/main evidence and review exist.

Scriptable v2.1 path:

```python
from gapforge import api

selected_project = api.create_selected_idea_project("<accepted-idea-id>")
spec = api.create_selected_benchmark_spec(selected_project.project_id)
api.generate_traces(spec.id, count=100, split="smoke")
api.create_monitor_baselines(spec.id)
smoke = api.run_selected_benchmark_smoke(spec.id)
api.compute_sequential_metrics(smoke.dataset_id)
api.selected_benchmark_review(spec.id)
api.selected_benchmark_manuscript(spec.id)
api.v21_release_gate(write_report=True)
```

Next steps toward pilot/main benchmark: expand the honest null and collusive alternative distributions, preregister target alpha levels and sample sizes, run all required baselines, resolve reviewer blockers, and keep smoke versus pilot versus main status visible in dashboards and release notes.

Planning docs:

- [docs/V2_1_ROADMAP.md](docs/V2_1_ROADMAP.md)
- [docs/V2_1_SELECTED_IDEA.md](docs/V2_1_SELECTED_IDEA.md)
- [docs/V2_1_BENCHMARK_SPEC.md](docs/V2_1_BENCHMARK_SPEC.md)
- [docs/V2_1_ACCEPTANCE_CRITERIA.md](docs/V2_1_ACCEPTANCE_CRITERIA.md)

## v2.2 Pilot-Scale Benchmark Study

v2.2 is the pilot-scale release for the same locked selected idea. It must require a pilot run, not another smoke-only package:

- powered pilot sample-size plan
- expanded honest-agent null distribution
- expanded collusive-agent alternative distribution
- stronger hard-negative traces
- full baseline monitor suite
- locked pilot run manifest
- pilot result artifacts
- sequential low-FPR analysis with uncertainty
- prior-work recall and related-work matrix attachment
- reviewer blocker resolution or preservation
- pilot manuscript package
- no pilot/main overclaiming

v2.2 must keep smoke, pilot, and main benchmark maturity separate. A synthetic pilot can support only the low-FPR claims that its sample size, sequential correction, and uncertainty report support. It must not claim deployment validity, unsupported `alpha=0.001` operational specificity, real deployment evidence, main benchmark maturity, or publication readiness with unresolved prior-work, related-work, baseline, power, or reviewer gates.

Scriptable v2.2 path:

```python
from gapforge import api

api.create_pilot_power_plan("<benchmark-id>")
api.generate_honest_null("<benchmark-id>", count=300)
api.generate_collusive_alternatives("<benchmark-id>", count=150)
dataset = api.build_pilot_dataset("<benchmark-id>", negative_count=300, positive_count=150)
api.calibrate_pilot_baselines("<benchmark-id>", target_alpha=0.01)
execution = api.run_selected_pilot("<benchmark-id>", dataset_id=dataset.id)
api.analyze_selected_pilot(execution.id)
api.selected_pilot_review("<benchmark-id>")
api.selected_pilot_manuscript("<benchmark-id>")
api.v22_release_gate(write_report=True)
```

Inspectable dashboard:

```bash
gapforge dashboard --project-id <selected-project-id> --include-selected-pilot
```

v2.2 is not the end state. v2.3 remains responsible for main-scale evidence: larger honest/null counts for unsupported alpha targets, stronger external scenario review, more competitive baselines, reproducible main-run manifests, and publication-readiness only if prior-work, related-work, power, and reviewer gates all pass.

Planning docs:

- [docs/V2_2_ROADMAP.md](docs/V2_2_ROADMAP.md)
- [docs/V2_2_PILOT_BENCHMARK.md](docs/V2_2_PILOT_BENCHMARK.md)
- [docs/V2_2_ACCEPTANCE_CRITERIA.md](docs/V2_2_ACCEPTANCE_CRITERIA.md)
- [docs/V2_2_POWER_AND_SAMPLE_SIZE.md](docs/V2_2_POWER_AND_SAMPLE_SIZE.md)
- [docs/V2_2_REVIEWER_BLOCKERS.md](docs/V2_2_REVIEWER_BLOCKERS.md)

## v2.3 Main-Scale Benchmark and Publication-Readiness Upgrade

v2.3 is the main-scale upgrade for the same locked selected idea. It starts from the v2.2 pilot handoff: 300 negative, 150 positive, and 214 hard-negative synthetic traces; pilot-scale support for `alpha=0.01`; underpowered and blocked `alpha=0.001`; incomplete real prior-work records; weak scientific baseline coverage; and a manuscript package that is not publication-ready.

v2.3 must directly address those blockers:

- main-scale sample-size plan
- `alpha=0.001` powered or explicitly dropped
- real prior-work records for every required category
- completed related-work matrix
- stronger baseline suite
- main dataset generation or pilot-to-main expansion
- main benchmark run or explicit no-go
- publication-readiness reviewer panel
- manuscript package upgrade
- clear go/no-go recommendation

v2.3 must not claim deployment validity from synthetic evidence, must not claim `alpha=0.001` while underpowered, must not hide missing real prior work, and must not call the manuscript publication-ready while fatal reviewer blockers remain.

Scriptable v2.3 path:

```python
from gapforge import api

api.create_main_sample_size_plan("<benchmark-id>")
api.decide_alpha_target("<benchmark-id>", alpha=0.001)
api.complete_selected_related_work("<benchmark-id>")
api.complete_selected_related_work_matrix("<benchmark-id>")
api.register_main_baselines("<benchmark-id>")
dataset = api.build_main_dataset("<benchmark-id>")
manifest = api.create_selected_main_manifest("<benchmark-id>", dataset_id=dataset.id)
execution = api.run_selected_main_benchmark("<benchmark-id>", manifest_id=manifest.id)
api.analyze_selected_main_benchmark(execution.id)
api.selected_publication_readiness_review("<benchmark-id>")
api.selected_main_manuscript("<benchmark-id>")
api.v23_release_gate(write_report=True)
```

The API names above describe the intended v2.3 workflow surface. Equivalent CLI commands or implementation-specific wrappers must preserve the same evidence requirements.

Implemented main-power CLI:

```bash
gapforge selected-main-power-plan --benchmark-id <benchmark-id>
gapforge selected-main-alpha-decision --benchmark-id <benchmark-id> --alpha 0.001
gapforge selected-main-power-report --benchmark-id <benchmark-id>
gapforge selected-related-work-complete --benchmark-id <benchmark-id>
gapforge selected-related-work-next-searches --benchmark-id <benchmark-id>
gapforge selected-related-work-status --benchmark-id <benchmark-id>
gapforge selected-baseline-strength --benchmark-id <benchmark-id>
gapforge implement-required-baseline-task --benchmark-id <benchmark-id> --baseline <baseline-name>
gapforge selected-baseline-strength-report --benchmark-id <benchmark-id>
gapforge build-main-trace-dataset --benchmark-id <benchmark-id>
gapforge main-trace-dataset-report --dataset-id <main-dataset-id>
gapforge selected-main-manifest --benchmark-id <benchmark-id> --dataset-id <main-dataset-id>
gapforge selected-main-run --benchmark-id <benchmark-id> --manifest-id <main-manifest-id>
gapforge selected-main-status --execution-id <main-execution-id>
gapforge selected-main-analysis --execution-id <main-execution-id>
gapforge selected-publication-review --benchmark-id <benchmark-id>
gapforge selected-publication-fix-list --benchmark-id <benchmark-id>
gapforge selected-main-manuscript --benchmark-id <benchmark-id>
gapforge selected-main-paper-package --benchmark-id <benchmark-id>
gapforge selected-benchmark-go-no-go --benchmark-id <benchmark-id>
gapforge selected-go-no-go-report --benchmark-id <benchmark-id>
```

Planning docs:

- [docs/V2_3_ROADMAP.md](docs/V2_3_ROADMAP.md)
- [docs/V2_3_MAIN_BENCHMARK.md](docs/V2_3_MAIN_BENCHMARK.md)
- [docs/V2_3_RELATED_WORK_COMPLETION.md](docs/V2_3_RELATED_WORK_COMPLETION.md)
- [docs/V2_3_PUBLICATION_READINESS.md](docs/V2_3_PUBLICATION_READINESS.md)

## v2.4 Related Work Completion and Publication-Readiness Remediation

v2.4 is the remediation lane after the v2.3 main benchmark decision. The v2.3 synthetic main run completed with 2995 negative traces, 500 positive traces, 2139 hard-negative traces, 15 monitor runs, and 10 sequential metric results, but the final decision was `revise_benchmark`: publication readiness and manuscript status were `not_ready` because all required related-work categories lacked real attached paper records.

v2.4 is therefore centered on real related work, not on making the existing synthetic result sound stronger. It requires targeted search campaigns, traceable paper records for required categories, closest-prior-work and novelty-risk updates, benchmark positioning against prior protocols, manuscript revision, a publication-readiness reviewer rerun, and a new go/no-go decision.

The v2.3 synthetic main benchmark completed, but publication readiness remained blocked by real related-work absence. v2.4 makes that remediation visible and scriptable:

```bash
gapforge selected-related-work-search-plan --benchmark-id <benchmark-id>
gapforge selected-related-work-search-run --benchmark-id <benchmark-id>
gapforge attach-related-paper --benchmark-id <benchmark-id> --category "low-FPR detection/evaluation" --paper-id <paper-id>
gapforge read-selected-related-work --benchmark-id <benchmark-id>
gapforge selected-prior-work-refresh --benchmark-id <benchmark-id>
gapforge selected-positioning --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-v2 --benchmark-id <benchmark-id>
gapforge selected-publication-review --benchmark-id <benchmark-id> --after-related-work
gapforge selected-manuscript-related-work-revise --benchmark-id <benchmark-id>
gapforge selected-paper-package-v24 --benchmark-id <benchmark-id>
gapforge v24-release-gate --write-report --json
gapforge dashboard --project-id <selected-project-id> --include-selected-v24
```

The same path is available from `gapforge.api`: `plan_selected_related_work_search`, `run_selected_related_work_search`, `attach_related_paper`, `read_selected_related_work`, `refresh_selected_prior_work`, `position_selected_contribution`, `build_selected_related_work_matrix_v2`, `rerun_selected_publication_review`, `revise_selected_manuscript_related_work`, and `v24_release_gate`. Fallback-only records do not count, no fake citation is allowed, no publication-ready claim passes while blockers remain, and synthetic evidence is not deployment validity.

Planning docs:

- [docs/V2_4_ROADMAP.md](docs/V2_4_ROADMAP.md)
- [docs/V2_4_RELATED_WORK_COMPLETION.md](docs/V2_4_RELATED_WORK_COMPLETION.md)
- [docs/V2_4_PUBLICATION_REMEDIATION.md](docs/V2_4_PUBLICATION_REMEDIATION.md)
- [docs/V2_4_ACCEPTANCE_CRITERIA.md](docs/V2_4_ACCEPTANCE_CRITERIA.md)
- [docs/V2_3_ACCEPTANCE_CRITERIA.md](docs/V2_3_ACCEPTANCE_CRITERIA.md)

## v2.5 Real Benchmark Grounding, Venue-Style Paper, and OpenReview Reviewer Training

v2.5 is the next hardening lane after the v2.4 publication-candidate package for `Sequential specificity benchmark for low-FPR collusion audits`. It requires real benchmark grounding as a separate artifact from the synthetic benchmark scaffold, a venue-style manuscript package built from allowed structure/style analysis rather than copied prose, and an OpenReview-calibrated reviewer pass used for critique calibration rather than truth generation.

The minimum v2.5 release gate requires one accepted vetted benchmark adapter, one venue-style manuscript package, and one OpenReview-calibrated reviewer pass. Known datasets do not prove benchmark validity by themselves, reviewer models cannot fabricate citations or results, and harsh objections must remain visible in manuscript and rebuttal artifacts.

The intended v2.5 path is:

```bash
gapforge selected-benchmark-inventory --benchmark-id <benchmark-id>
gapforge selected-vetted-benchmark-adapter --benchmark-id <benchmark-id> --source-benchmark <source-id>
gapforge selected-protocol-adaptation-report --benchmark-id <benchmark-id>
gapforge selected-venue-style-source-audit --benchmark-id <benchmark-id> --venue <venue-id>
gapforge selected-venue-style-manuscript --benchmark-id <benchmark-id> --venue <venue-id>
gapforge openreview-review-dataset-build --benchmark-id <benchmark-id> --venue-family <venue-family>
gapforge openreview-reviewer-calibrate --benchmark-id <benchmark-id>
gapforge selected-openreview-review-pass --benchmark-id <benchmark-id>
gapforge selected-review-driven-revision --benchmark-id <benchmark-id>
gapforge selected-paper-package-v25 --benchmark-id <benchmark-id>
gapforge v25-release-gate --write-report --json
```

Planning docs:

- [docs/V2_5_ROADMAP.md](docs/V2_5_ROADMAP.md)
- [docs/V2_5_REAL_BENCHMARK_GROUNDING.md](docs/V2_5_REAL_BENCHMARK_GROUNDING.md)
- [docs/V2_5_VENUE_STYLE_MANUSCRIPT.md](docs/V2_5_VENUE_STYLE_MANUSCRIPT.md)
- [docs/V2_5_OPENREVIEW_REVIEWER_DATASET.md](docs/V2_5_OPENREVIEW_REVIEWER_DATASET.md)
- [docs/V2_5_ACCEPTANCE_CRITERIA.md](docs/V2_5_ACCEPTANCE_CRITERIA.md)

## Active v0.3 Loop

Use the active loop when GapForge should decide whether to search, parse, read, expand citations, check novelty, request human review, or stop:

```bash
gapforge run "low false positive collusion detection" --v3 --active --budget small --source-profile ai_safety
gapforge active-decisions --run-id <run-id>
```

Every decision is written to `active_decisions.md`.

## Common CLI

```bash
gapforge --help
gapforge init-topic "topic"
gapforge run "topic"
gapforge run "topic" --v2 --max-papers 20
gapforge run "topic" --v3 --project-id <project-id> --build-index --mature-directions
gapforge topic-portfolio --project-id <project-id>
gapforge idea-generate --project-id <project-id>
gapforge mutate-idea --idea-id <idea-id>
gapforge constructive-gaps --project-id <project-id>
gapforge transfer-ideas --project-id <project-id>
gapforge idea-novelty --idea-id <idea-id>
gapforge idea-tournament --project-id <project-id>
gapforge idea-feedback --idea-id <idea-id> --action accept
gapforge research-agenda --project-id <project-id>
gapforge idea-yield --project-id <project-id> --write-report
gapforge v2-release-gate --write-report --json
gapforge dashboard --run-id <run-id>
gapforge dashboard --project-id <project-id> --include-ideas
gapforge review-queue --run-id <run-id>
gapforge audit-artifacts --run-id <run-id>
```

The same v2 workflows are scriptable from Python through `gapforge.api`: `generate_topic_portfolio`, `create_idea_bank`, `generate_ideas`, `mutate_idea`, `generate_constructive_gaps`, `transfer_ideas`, `run_idea_novelty`, `run_idea_tournament`, `add_idea_feedback`, `generate_research_agenda`, `idea_yield`, and `v2_release_gate`.

## Architecture

Core layers:

- `src/gapforge/models.py`: typed run, project, evidence, retrieval, review, and export models
- `src/gapforge/state.py`: durable run persistence and validation
- `src/gapforge/project_memory.py`: multi-run project memory
- `src/gapforge/orchestrator.py`: v0.1/v0.2/v0.3 orchestration
- `src/gapforge/orchestration/`: active loop decisions and budgets
- `src/gapforge/sources/`: source connectors, coverage, ranking, and policies
- `src/gapforge/skills/`: deterministic and optional LLM-backed skills
- `src/gapforge/retrieval/`: local hybrid retrieval
- `src/gapforge/reporting.py`: conservative Markdown/JSON reports

See `docs/ARCHITECTURE.md`.

## Evaluation Philosophy

Evals are offline and fixture-driven. They measure behavior such as specificity, evidence linkage, duplicate rejection, source coverage transparency, retrieval relevance, direction maturity, and manuscript honesty. They do not prove real scientific usefulness.

```bash
make eval
gapforge eval --v2
gapforge eval --v3
gapforge eval --v4
gapforge eval --v5
gapforge eval --v6
gapforge eval --v7
gapforge eval --v8
```

## Limitations and Safety Notes

- GapForge does not perform exhaustive literature review.
- Offline fallback outputs are smoke tests.
- Semantic retrieval is a ranking aid, not proof of novelty.
- LLM outputs are untrusted until schema-valid and evidence-located.
- Fake-agent outputs validate plumbing only and never count as real Codex/GPT-5.4 research.
- Prompt-pack handoff counts as real only after Codex/GPT-5.4 outputs are validated, attested, and human-reviewed.
- Empirical claims are artifact-gated: no run record and result artifact means no supported result claim.
- Benchmark claims are stronger than fixture smoke claims and require benchmark records, real or benchmark-like data, consent where applicable, compute logs, result artifacts, analysis, replication packaging, and review.
- Manuscript submission-readiness requires traceable claims, known citations, artifact-backed results, artifact evaluation package status, blinding review when applicable, reviewer-objection handling, and human review.
- v0.9 external pilot success may be a defensible direction or an evidence-backed refusal; v1 readiness is a separate gate.
- v2 idea seeds are provisional; only accepted idea candidates have survived active search, novelty/counterevidence review, tournament comparison, and human review.
- v2 research agendas are honest fallback plans, not accepted ideas or paper-ready claims.
- PDFs, transcripts, and generated dashboards may be unsafe to commit.
- Human review is required before treating any direction as research-ready.

Use:

```bash
gapforge audit-artifacts --run-id <run-id>
gapforge export-safe-bundle --project-id <project-id>
```

## Roadmap

- v0.1: deterministic research OS foundation
- v0.2: full-text evidence and novelty dossier upgrade
- v0.3: semantic, optional LLM-assisted, multi-run project-memory upgrade
- v0.4: actual Codex/GPT-5.4 agentic campaign execution path, campaign recovery, multi-step canaries, v4 evals, and strict human-reviewed real-run acceptance gates
- v0.5: real-literature campaign quality with source diagnostics, search strategy, prior-work recall, quality review, v5 evals, and v5 release gate
- v0.6: experiment execution and empirical validation with run manifests, result artifacts, statistics, reproducibility checks, failed/negative result handling, and result claim ledger
- v0.7: real benchmark execution and replication with benchmark registry, dataset consent/cache, compute modes, jobs, sweeps, error/slice analysis, low-FPR power checks, benchmark comparison, and replication packages
- v0.8: manuscript, artifact evaluation, and reviewer-rebuttal workflow with manuscript projects, claim-to-paper traceability, citation/BibTeX management, venue templates, section drafting, figure/table generation, artifact evaluation packaging, blinding support, submission-readiness gates, and camera-ready checklists
- v0.9: external pilot and v1 readiness with one real end-to-end topic, live literature, direction/refusal decision, experiment protocol, artifact package, manuscript/rebuttal planning, migration audit, CLI/docs cleanup, artifact hygiene, external feedback, and explicit v1 gate
- Future: richer layout/OCR extraction, external reference-manager integration, larger distributed experiment runners, and collaborative review workflows
