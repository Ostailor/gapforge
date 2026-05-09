# GapForge v2.3 Acceptance Criteria

v2.3 acceptance is about main-scale benchmark readiness and publication-readiness honesty. It must directly address the v2.2 blockers and end with either main-scale readiness or an explicit no-go.

## Definitions

- **Main-scale sample-size plan**: a locked pre-outcome plan that states required negative counts, correction assumptions, confidence intervals, and alpha decisions.
- **Main benchmark**: a locked `run_type: main` benchmark execution with sufficient artifacts, baselines, metrics, uncertainty, error analysis, and replication package.
- **Real prior-work record**: traceable paper metadata from a source, not generated placeholder text.
- **Related-work matrix completion**: every required category has real records and manuscript-relevant matrix entries, or optional categories are dropped from claims.
- **Publication-readiness gate**: a reviewer-panel and artifact gate that can mark a manuscript publication-ready only when no fatal blockers remain.
- **No-go**: an explicit release outcome that declines main-scale or publication claims because blockers remain.

## Required Documentation Criteria

1. v2.3 roadmap names the selected idea and preserves the v2.0/v2.1/v2.2 lineage.
2. v2.3 docs directly list the v2.2 blockers.
3. v2.3 main benchmark spec defines sample-size, alpha, dataset, baseline, manifest, artifact, and metric requirements.
4. v2.3 related-work plan requires real paper records for every required category.
5. v2.3 publication-readiness doc makes publication claims blocker-gated.
6. v2.3 acceptance criteria require main-scale readiness or explicit no-go.
7. v2.3 docs prohibit deployment-validity claims from synthetic evidence.
8. v2.3 docs prohibit `alpha=0.001` claims while underpowered.
9. v2.3 docs prohibit hiding missing real prior work.
10. v2.3 docs preserve v2.2 reviewer blockers unless resolved with artifacts.

## Required Main-Scale Criteria

The v2.3 release gate must fail unless all are true:

1. v2.2 blocker handoff is attached.
2. Main-scale sample-size plan is locked before main outcomes.
3. Every requested alpha target is classified as supported, dropped, blocked, or not requested.
4. `alpha=0.001` is powered or explicitly dropped before release claims.
5. Main dataset is generated or pilot data is expanded with lineage, counts, seeds, leakage checks, and synthetic-data labels.
6. If no main dataset is generated, a no-go recommendation is issued.
7. Main manifest exists with `run_type: main`, or the release explicitly records no-go.
8. Baseline suite includes v2.2 continuity baselines and stronger prior-work-grounded baselines where feasible.
9. Missing baselines have explicit blockers and claim-language consequences.
10. Main execution artifacts are persisted and parsed before analysis.
11. Sequential low-FPR metrics include uncertainty and repeated-look correction.
12. Hard-negative false positives are reported as an honest-negative slice.
13. Baseline comparisons include uncertainty and underpowered-comparison warnings.
14. Replication package exists for any completed main run.
15. Main benchmark report ends with a clear go/no-go status.

## Required Related-Work Criteria

The v2.3 release gate must fail publication-readiness claims unless all are true:

1. Required related-work categories are enumerated.
2. Every required category has at least one real traceable paper record, or the category is optional and dropped from manuscript claims.
3. Real records include source identifiers and retrieval metadata.
4. Closest-prior-work candidates are attached or a recorded search explains why none were found.
5. Related-work matrix maps records to benchmark, low-FPR, sequential, baseline, threat-model, and novelty implications.
6. Fake-citation checks pass.
7. Missing categories are reported as blockers, not hidden.
8. Prior-work-derived baselines are implemented, rejected with reasons, or marked as blockers.

## Required Publication-Readiness Criteria

Publication readiness may be claimed only when:

1. Main benchmark is complete or claims are explicitly narrowed to the completed evidence.
2. Related-work matrix completion passes for the stated scope.
3. Citation and BibTeX audit passes.
4. Manuscript claims link to claim ledger entries, result artifacts, related-work records, or explicit limitations.
5. Figures and tables link to main-run artifacts or are labeled conceptual placeholders.
6. Publication-readiness reviewer panel is complete.
7. Every reviewer blocker is classified as `resolved`, `accepted_with_narrowed_claim`, or `fatal`.
8. No fatal blocker remains.
9. Human review accepts residual risks for the stated scope.
10. Release notes use only the approved claim language.

If any item is missing, the manuscript package may exist only as `blocked_manuscript` or `main_study_manuscript_with_warnings`.

## Pass Outcomes

### Pass With Main Benchmark and Publication Readiness

Allowed only when:

- main run artifacts exist
- requested alpha claims are supported or dropped
- related work is complete for the stated scope
- baseline suite supports the contribution claims
- reviewer panel has no fatal blockers
- manuscript package passes publication-readiness gates

Allowed release statement:

`v2.3 main benchmark and publication-readiness gate passed for the stated scope.`

### Pass With Main Benchmark and Blocked Publication

Allowed when:

- main benchmark artifacts exist
- low-FPR claims are correctly bounded
- publication blockers remain visible
- go/no-go recommendation says publication is not ready

Allowed release statement:

`v2.3 main benchmark passed with publication blockers; manuscript is not publication-ready.`

### Pass With Explicit No-Go

Allowed when:

- v2.3 records a complete blocker analysis
- the release explicitly declines main-scale or publication claims
- v2.2 blockers are preserved or updated with evidence
- next requirements are clear

Allowed release statement:

`v2.3 main-scale benchmark upgrade ended in explicit no-go; release claims remain blocked.`

## Fail Conditions

v2.3 fails when:

- v2.2 blockers are omitted or softened
- pilot evidence is presented as main evidence
- main sample-size plan is missing
- `alpha=0.001` is still requested but underpowered and not marked blocked
- synthetic evidence is used for deployment-validity claims
- missing prior-work categories are hidden
- related-work records are fake, placeholder, or citation-looking text without traceable metadata
- baseline suite remains pilot-grade while strong contribution claims are made
- main-run artifacts are missing but main benchmark completion is claimed
- hard negatives are omitted, relabeled, or excluded from false-positive reporting
- publication readiness is claimed with fatal reviewer blockers
- release notes avoid the go/no-go recommendation

## Release Statement

Release notes must use one of:

- `v2.3 main benchmark and publication-readiness gate passed for the stated scope`
- `v2.3 main benchmark passed with publication blockers; manuscript is not publication-ready`
- `v2.3 main-scale benchmark upgrade ended in explicit no-go; release claims remain blocked`
- `v2.3 blocked; main-scale benchmark and no-go evidence are incomplete`

## v2.4 Handoff Criteria

If v2.3 ends with no-go or blocked publication, the handoff must include:

- unresolved alpha targets and required counts
- missing or weak baseline list
- missing prior-work records or matrix categories
- synthetic-validity limitations
- reviewer fatal blockers
- artifact gaps
- exact claim language that remains forbidden

If these are missing, v2.3 has not produced a useful handoff.
