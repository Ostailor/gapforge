# GapForge v2.3 Roadmap

v2.3 is the Main-Scale Benchmark and Publication-Readiness Upgrade for the locked v2 idea:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`

v2.2 completed an artifact-backed synthetic pilot with 300 negative, 150 positive, and 214 hard-negative traces. The pilot supported `alpha=0.01` at pilot scale, blocked `alpha=0.001` as underpowered, ran metrics and baselines, preserved reviewer blockers, and generated a pilot manuscript package that is not publication-ready.

v2.3 must directly address those blockers. It is not allowed to make the v2.2 pilot look stronger by changing language. It must either produce main-scale readiness with sufficient artifacts or issue an explicit no-go recommendation.

The release claim is limited to:

`v2.3 defines and gates the main-scale benchmark and publication-readiness upgrade for the selected v2 idea.`

## Maturity Boundary

- **Pilot complete**: v2.2 synthetic pilot artifacts exist and support only pilot-scale claims.
- **Main-scale ready**: v2.3 has a locked main manifest, sufficient sample-size plan, completed related-work records, stronger baselines, and a go decision for the main run.
- **Main benchmark complete**: v2.3 has generated or expanded the main dataset, executed the main run, parsed result artifacts, compared baselines, and produced a replication package.
- **Publication-ready**: all fatal reviewer blockers are resolved or accepted by human review with narrowed claims; prior-work, result, baseline, manuscript, and artifact gates pass.
- **No-go**: v2.3 explicitly declines main or publication claims because power, data, baselines, related work, or reviewer blockers remain fatal.

Synthetic evidence alone must not be described as deployment validity.

## Workstreams

### 1. Main-Scale Sample-Size Plan

The main-scale plan must be written before inspecting main-run outcomes. It must define:

- target alpha levels and required negative counts
- effective sample size after sequential-window correction
- hard-negative sample-size target
- sensitivity comparison power for the baseline suite
- confidence interval method and maximum acceptable upper bound
- correlated-window handling
- stop rules for underpowered or infeasible targets

The v2.2 handoff recorded `alpha=0.001` as underpowered with 300 observed negatives and 2995 required negatives. v2.3 must use that as a minimum decision point, not as a claim.

### 2. Alpha 0.001 Decision

v2.3 must make one of two decisions before the main run:

- `power_alpha_0_001`: collect enough honest/null evidence, after correction, to support the target.
- `drop_alpha_0_001`: remove the target from v2.3 claims and release notes, while preserving the v2.2 blocker history.

If `alpha=0.001` remains underpowered, the release must say so plainly and must not imply operational specificity at that level.

### 3. Real Prior-Work Records

v2.2 structurally attached related-work categories but did not attach real paper records. v2.3 must attach real records for every required category:

- low-FPR detection and evaluation
- multi-agent collusion or covert coordination
- monitor evasion or adversarial auditing
- sequential testing or change-point detection
- benchmark and evaluation protocol design
- anomaly detection specificity
- medical screening specificity analogies, if used
- cartel or covert-channel analogies, if used

Fake citations, placeholder records, and category names without paper metadata are blockers.

### 4. Related-Work Matrix Completion

The related-work matrix must map each real record to:

- category
- claimed relationship to the benchmark
- dataset or evaluation protocol relevance
- low-FPR or specificity relevance
- sequential-analysis relevance
- baseline relevance
- threat-model relevance
- novelty risk
- manuscript section target

If a category is intentionally dropped, the manuscript must remove any argument that depends on it.

### 5. Stronger Baseline Suite

v2.3 must strengthen the v2.2 pilot baselines before making strong benchmark or contribution claims:

- preserve weak pilot baselines for continuity
- add prior-work-grounded baselines where real records justify them
- include calibrated non-oracle monitors with locked thresholds
- include sequential and non-sequential comparisons
- include abstain or insufficient-evidence behavior
- report missing or infeasible baselines as blockers

Monitor-superiority claims require comparison power and credible baselines. Otherwise, the manuscript may discuss failure modes only.

### 6. Main Dataset Generation or Pilot-to-Main Expansion

v2.3 must either generate a main-scale dataset or explicitly decline the main run. A valid expansion must record:

- lineage from v2.2 pilot families
- new honest/null, collusive, and hard-negative counts
- seed and generator versions
- deduplication and leakage checks
- family-level coverage
- external or human scenario review where practical
- synthetic-data limitation labels

The main dataset can remain synthetic only if every report keeps that limitation visible and avoids deployment-validity claims.

### 7. Main Benchmark Run

A valid main run requires:

- locked main manifest with `run_type: main`
- frozen thresholds and metrics before result inspection
- full baseline execution or explicit missing-baseline blockers
- raw outputs, metrics, predictions, logs, and failure records
- sequential low-FPR analysis with uncertainty
- hard-negative slice analysis
- comparison report
- replication package
- go/no-go report

Generated prose without these artifacts is not a main benchmark.

### 8. Publication-Readiness Reviewer Panel

The reviewer panel must be stricter than v2.2 and must include at least:

- statistics and low-FPR reviewer
- benchmark validity reviewer
- baseline and prior-work reviewer
- manuscript and artifact reviewer
- area-chair style final assessor

Each reviewer must classify blockers as `resolved`, `accepted_with_narrowed_claim`, or `fatal`.

### 9. Manuscript Package Upgrade

The manuscript package must be upgraded from pilot manuscript to main-study manuscript only if the gates pass. It must include:

- completed related-work matrix
- claim ledger links
- main-run result tables and figures
- baseline comparison tables
- hard-negative error analysis
- power and alpha decision statement
- artifact and replication package summary
- reviewer blocker table
- go/no-go recommendation

If any fatal blocker remains, the package is `manuscript_with_fatal_blockers`, not publication-ready.

### 10. Clear Go/No-Go Recommendation

v2.3 must end with one of:

- `go_main_benchmark_publication_ready`: main evidence and manuscript gates pass.
- `go_main_benchmark_not_publication_ready`: main benchmark passed, but publication blockers remain.
- `no_go_underpowered`: sample size or alpha target remains inadequate.
- `no_go_related_work`: required real prior-work records or related-work matrix remain incomplete.
- `no_go_baselines`: baselines are too weak or missing for claimed contribution.
- `no_go_synthetic_validity`: synthetic-only evidence is inadequate for the intended claim.
- `no_go_reviewer_blockers`: fatal reviewer blockers remain.

No release language may imply publication readiness unless the recommendation is publication-ready and blocker-gated.

## Milestones

1. Freeze v2.2 blocker handoff.
2. Write the main-scale sample-size plan.
3. Decide whether `alpha=0.001` is powered or dropped.
4. Complete real prior-work records for all required categories.
5. Complete the related-work matrix.
6. Register stronger baselines and lock threshold rules.
7. Generate or expand the main dataset, or record no-go.
8. Lock and execute the main benchmark manifest.
9. Analyze results, power, hard negatives, and baseline comparisons.
10. Export replication and manuscript packages.
11. Run the publication-readiness reviewer panel.
12. Issue the go/no-go recommendation.

## Release Claim Boundary

Allowed v2.3 claims:

- GapForge has a main-scale benchmark and publication-readiness gate for the selected idea.
- v2.3 either runs a main-scale benchmark or records an explicit no-go.
- Publication-readiness claims are allowed only when blocker gates pass.

Forbidden v2.3 claims unless separately proven:

- deployment validity from synthetic evidence
- `alpha=0.001` support while underpowered
- complete prior-work coverage without real paper records
- publication readiness while fatal reviewer blockers remain
- main benchmark maturity from pilot artifacts alone

## Scriptable Workflow Surface

v2.3 is visible through the static dashboard and through the Python API. Generate the dashboard with:

```bash
gapforge dashboard --project-id <project-id> --include-selected-main
```

The v2.3 pages are:

- `main_power.html`
- `related_work_completion.html`
- `baseline_strength.html`
- `main_dataset.html`
- `main_results.html`
- `go_no_go.html`
- `publication_review.html`
- `main_manuscript.html`
- `v23_release_gate.html`

The matching API helpers are:

- `create_main_power_plan(...)`
- `complete_related_work(...)`
- `assess_baseline_strength(...)`
- `build_main_dataset(...)`
- `run_selected_main(...)`
- `analyze_selected_main(...)`
- `selected_go_no_go(...)`
- `selected_publication_review(...)`
- `selected_main_manuscript(...)`
- `v23_release_gate(...)`

These helpers expose the same blocker-gated workflow as the CLI. They must not be used to bypass alpha, related-work, baseline, synthetic-validity, reviewer, or manuscript gates.
