# GapForge v2.3 Related-Work Completion Plan

v2.2 attached related-work structures but did not attach real paper records for the required categories. v2.3 must complete the related-work matrix before publication-readiness claims are allowed.

This document defines completion. It does not supply placeholder citations and must not be treated as evidence that the categories are already covered.

## Core Rule

A related-work category is complete only when it has real, inspectable paper records and the matrix explains how those records affect the benchmark claim. Category names, search intents, or generated citation-looking text do not count.

## Required Categories

| Category | Required v2.3 Treatment |
| --- | --- |
| Low-FPR detection and evaluation | Attach real records about evaluating detectors under low false-positive constraints. |
| Multi-agent collusion or covert coordination | Attach real records about collusion, coordination, or cooperative misuse relevant to multi-agent settings. |
| Monitor evasion or adversarial auditing | Attach real records about evasion of monitors, auditors, classifiers, or safety systems. |
| Sequential testing or change-point detection | Attach real records that justify repeated-look correction, sequential thresholds, or change-point baselines. |
| Benchmark and evaluation protocol design | Attach real records about benchmark construction, validity, contamination, or evaluation methodology. |
| Anomaly detection specificity | Attach real records about specificity, calibration, false alarms, or anomaly detector evaluation. |
| Medical screening specificity analogies, if used | Attach real records only if the manuscript uses screening-test analogies. Otherwise drop the analogy. |
| Cartel or covert-channel analogies, if used | Attach real records only if the manuscript uses cartel or covert-channel analogies. Otherwise drop the analogy. |

If an optional analogy category is not used, it must be marked `dropped_not_used` and removed from manuscript arguments.

## Real Paper Record Requirements

Every paper record must include:

- stable title
- author list or source-provided author string
- year
- venue, preprint server, or publisher source when available
- DOI, arXiv ID, URL, or other stable source identifier
- source used to retrieve the record
- retrieval date
- abstract or summary source, when available
- category assignments
- relevance note
- novelty-risk note
- baseline or method implication, if any

Records with missing identifiers may be accepted only when a reviewer marks them as real and traceable. Fabricated DOIs, arXiv IDs, venues, or BibTeX keys are fatal blockers.

## Search and Recall Requirements

The v2.3 related-work run must record:

- search queries per category
- source connectors used
- inclusion and exclusion rules
- deduplication method
- closest-prior-work candidates
- missed-search list
- unavailable or paywalled records
- reviewer decisions
- unresolved coverage risks

At least one targeted search must be run per required category. A broad general search cannot satisfy every category unless the report shows category-specific recall.

Implemented campaign commands:

```bash
gapforge selected-related-work-complete --benchmark-id <benchmark-id>
gapforge selected-related-work-next-searches --benchmark-id <benchmark-id>
gapforge selected-related-work-status --benchmark-id <benchmark-id>
```

## Matrix Fields

The related-work matrix must include one row per record with:

- `record_id`
- `category`
- `claim_supported_or_challenged`
- `benchmark_relevance`
- `specificity_or_low_fpr_relevance`
- `sequential_relevance`
- `baseline_relevance`
- `threat_model_relevance`
- `dataset_or_protocol_relevance`
- `closest_prior_work_status`
- `novelty_risk`
- `manuscript_section`
- `review_status`

The matrix must also include category-level status:

- `complete`
- `complete_with_warning`
- `dropped_not_used`
- `incomplete_blocker`

## Closest-Prior-Work Gate

v2.3 must identify closest-prior-work candidates for the benchmark contribution. The gate passes only when:

- closest candidates are attached as real records
- the manuscript explains the benchmark difference without overstating novelty
- competing evaluation protocols are compared
- monitor baselines derived from prior work are considered or rejected with reasons
- novelty risk is classified as low, medium, high, or unresolved

If no closest prior work is found, the report must say `closest_prior_work_not_found_after_recorded_search`, not `none exists`.

## Baseline Linkage

Related-work completion must feed the baseline suite. For each category, the matrix must say whether it creates:

- an implementable baseline
- a calibration or thresholding method
- a metric or statistical correction
- a threat-model constraint
- a manuscript limitation
- no implementation implication

If implementable prior-work baselines exist but are not run, the main benchmark cannot claim strong comparison completeness.

## Publication Linkage

The manuscript package may claim related-work readiness only when:

- every required category is `complete` or `complete_with_warning`
- optional analogy categories are either complete or dropped from the manuscript
- closest-prior-work candidates are attached
- fake-citation checks pass
- citation and BibTeX records resolve to real metadata or reviewed user-supplied records
- reviewer blockers for prior-work coverage are resolved or explicitly accepted with narrowed claims

If any category is `incomplete_blocker`, publication readiness is blocked.

## Anti-Overclaim Rules

v2.3 must not:

- hide missing categories by renaming them
- turn search queries into citations
- invent BibTeX metadata
- describe coverage as exhaustive
- claim novelty from absence of attached records
- keep manuscript arguments that depend on dropped analogy categories
- weaken the v2.2 prior-work blocker to pass publication readiness

## Completion Output

The related-work completion report must end with one of:

- `related_work_complete`: real records and matrix support the claimed scope.
- `related_work_complete_with_warnings`: coverage supports narrowed claims, with visible warnings.
- `related_work_incomplete_no_go`: missing real records or matrix entries block publication readiness.

Only the first two outcomes may feed a publication-readiness pass, and only if the reviewer panel accepts the residual risk.
