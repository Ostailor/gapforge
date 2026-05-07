# GapForge

GapForge is a Codex-powered Research Ideation OS. It turns a broad topic into auditable research state: papers, notes, claims, evidence, gaps, novelty dossiers, experiment plans, reviewer objections, and reports.

GapForge v0.4 adds campaign-level Codex/GPT-5.4 actual-run workflows on top of the v0.3 semantic, project-memory-aware, optionally LLM-assisted research system. v0.5 extends that path toward live-literature campaign quality: source health, planned search rounds, canonicalization, closest-prior-work recall, human research-quality review, and a v5 release gate. v0.6 adds experiment execution and empirical validation: moving from experiment-ready directions to executed, logged, statistically analyzed, reproducible experiment packages. v0.7 adds real benchmark execution and replication plumbing: benchmark records, explicit dataset consent/cache handling, compute/job abstractions, result aggregation, error analysis, comparison reports, low-FPR power checks, and replication packages. v0.8 adds the manuscript, artifact evaluation, and reviewer-rebuttal release layer: manuscript projects, claim-to-paper traceability, citations/BibTeX, venue templates, section drafting, artifact packages, rebuttal planning, blinding, and submission-readiness gates. GapForge is still not an exhaustive autonomous literature reviewer, and it must not fabricate citations, experimental results, venue acceptance, or novelty claims. Deterministic and offline-safe paths remain the default.

## Version Lineage

- **v0.1**: deterministic research OS foundation with run state, source connectors, skill orchestration, claim ledger, novelty gate, evals, and reports.
- **v0.2**: full-text evidence and novelty dossier upgrade with PDF artifacts, sections, evidence spans, source coverage, citation graph, gap evidence matrices, human review, and strict reports.
- **v0.3**: semantic plus LLM-assisted plus multi-run project-memory upgrade with hybrid retrieval, source policy profiles, active loop decisions, related-work matrices, direction maturation, protocols, review queues, dashboard, and paper packages.
- **v0.4**: actual Codex/GPT-5.4 agentic campaign release path with campaign-level state, task packs, direct/handoff runner support, strict validated import, repair/rollback, campaign dashboards/reports, v4 evals, and release gates. Fake-agent success still does not count as real-run acceptance.
- **v0.5**: real literature campaign quality layer. v0.5 validates multi-step live-literature campaigns, source coverage quality, closest-prior-work recall, real-paper citation grounding, expert review, experiment protocol quality, and correct rejection behavior when novelty is weak.
- **v0.6**: experiment execution and empirical validation layer. v0.6 distinguishes protocols, scaffolds, smoke runs, pilot/main runs, failed/negative experiments, statistical analyses, reproducibility checks, and artifact-backed empirical claims.
- **v0.7**: real benchmark execution and replication layer. v0.7 distinguishes fixture smoke, local benchmark, full benchmark, failed jobs, underpowered runs, benchmark comparison, replication packages, and real/local public benchmark validation.
- **v0.8**: manuscript, artifact evaluation, and reviewer-rebuttal layer. v0.8 distinguishes manuscript-ready, submission-ready, and camera-ready while requiring claim, citation, result, artifact, blinding, and human-review traceability.

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
gapforge dashboard --run-id <run-id>
gapforge review-queue --run-id <run-id>
gapforge audit-artifacts --run-id <run-id>
```

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
- Future: richer layout/OCR extraction, external reference-manager integration, larger distributed experiment runners, and collaborative review workflows
