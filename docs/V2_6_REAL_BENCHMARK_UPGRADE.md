# GapForge v2.6 Real Benchmark Upgrade

v2.6 must attempt to move beyond the v2.5 synthetic local fixture by evaluating real external/public benchmark fit for the selected low-FPR collusion-audit protocol.

The attempt can end in an accepted adapter, an auxiliary adapter, or a no-fit report. It must not convert synthetic fixture plumbing into real collusion benchmark validity.

## Core Distinction

- **Synthetic v2.5 fixture**: useful for adapter plumbing, deterministic tests, trace conversion, and workflow verification.
- **External/public benchmark candidate**: a source outside the local fixture path with stable access, source metadata, license/terms, task definition, labels or outcomes, and inspectable splits.
- **Real collusion benchmark grounding**: allowed only when the source labels, task, mapping, and limitations support collusion or covert-coordination claims.
- **Benchmark no-fit**: an honest outcome when no public source supports the selected protocol without overclaiming.

The synthetic fixture remains synthetic even if registered as a vetted benchmark record. It cannot support real collusion benchmark validity or deployment validity.

## Candidate Inventory Requirements

Each external/public candidate must have:

- `source_benchmark_id`
- stable name and version, if available
- source URL, DOI, repository, dataset hub ID, or other stable identifier
- access route and retrieval date
- license and terms-of-use summary
- citation or attribution requirements
- task format
- label or outcome semantics
- split policy
- data modality and unit of analysis
- known contamination and leakage risks
- privacy, safety, or redistribution constraints
- fit assessment
- inclusion, exclusion, auxiliary, or no-fit decision

If license, terms, access, source authenticity, or label meaning is unclear, the candidate cannot become an accepted grounding adapter.

## Fit Dimensions

Fit review must score or classify whether the candidate supports:

- benign negative traces
- suspicious or collusive positive traces
- hard-negative benign coordination
- monitor-evasion stress cases
- sequential windows or repeated looks
- low-FPR threshold calibration
- false-positive denominator
- positive-case denominator
- baseline comparison
- held-out evaluation
- leakage and contamination checks
- artifact redistribution or reproducible access

Unsupported dimensions must stay unsupported. Do not infer collusion labels from unrelated suspiciousness, anomaly, toxicity, fraud, malware, or coordination labels unless the source and mapping justify it.

## Adapter Attempt Requirements

An adapter attempt must produce:

- source record
- license and access record
- fit assessment
- mapping plan
- inclusion and exclusion rules
- ambiguity policy
- split preservation policy
- deterministic conversion manifest, if conversion is attempted
- leakage and contamination report
- adapter limitations
- smoke run or blocked-run report
- manuscript claim-language update

If implementation is blocked by license, access, missing labels, unsafe data, or bad protocol fit, the blocked status is valid evidence.

## Adapter Status Values

Each candidate ends with one status:

- `accepted_grounding_adapter`: source and mapping support a bounded selected-protocol claim.
- `accepted_negative_only_adapter`: source supports specificity or hard-negative stress but not positive collusion evaluation.
- `accepted_auxiliary_adapter`: source supports a supporting check but not main benchmark grounding.
- `blocked_license_or_access`: source cannot be retrieved or used safely.
- `blocked_requires_human_review`: label semantics, safety, or legal constraints need expert review.
- `rejected_bad_fit`: source does not support the selected protocol.
- `rejected_no_collusion_validity`: source may be useful for other tasks but cannot support collusion validity claims.
- `no_fit_after_inventory`: no candidate fits the required claim scope.

Only accepted statuses can support benchmark-grounding claims, and only for the exact scope stated in the adapter report.

## Benchmark No-Fit Report

If no source receives an accepted status, v2.6 must produce a benchmark no-fit report with:

- inventory summary
- candidate-by-candidate exclusion reasons
- labels or task properties missing from each candidate
- access, license, or safety blockers
- protocol dimensions unsupported by public sources
- claims that must be dropped, narrowed, or labeled synthetic-only
- future data or benchmark requirements

## Scriptable Benchmark Attempt Path

API:

```python
from gapforge import api

search = api.search_real_benchmark_candidates(benchmark_id)
assessment = api.assess_real_benchmark_adapter(benchmark_id, candidate_id)
attempts = api.run_real_benchmark_experiment(benchmark_id)
```

CLI:

```bash
gapforge selected-real-benchmark-search --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-adapter-assess --benchmark-id <benchmark-id> --candidate-id <candidate-id>
gapforge selected-real-benchmark-experiment-run --benchmark-id <benchmark-id>
```

Dashboard pages:

- `real_benchmark_search.html`
- `real_benchmark_adapter.html`
- `real_benchmark_experiment.html`

The dashboard and API must label auxiliary and sanity-check evidence as such. A sanity-check adapter cannot support primary benchmark validity, and a no-fit report is acceptable only when it explains why public candidates do not map.
- manuscript limitation text

The release gate may return `benchmark_no_fit` when the no-fit report is complete and claims are narrowed accordingly. That outcome is allowed because it is honest; it is not proof of publication readiness.

## Claim Rules

Allowed:

- `public benchmark adapter attempt`
- `accepted negative-only specificity adapter`, when true
- `auxiliary public benchmark grounding`, when true
- `benchmark no-fit after recorded inventory`
- `synthetic fixture retained for adapter plumbing`

Forbidden:

- `real collusion benchmark validity` unless source labels and mapping support it
- `deployment-valid collusion audit`
- `real-world benchmark proven`
- `known dataset validates the selected protocol`
- `public benchmark grounding` from the synthetic fixture alone
- `SOTA`, `first`, or superiority claims without separate evidence

## Manuscript Linkage

The manuscript must separate:

- synthetic fixture results
- public benchmark adapter results, if any
- negative-only or auxiliary adapter results
- no-fit conclusions
- deployment and external-validity limitations

Any result table mixing these sources must label evidence type, source, mapping status, and unsupported claims.

## Completion Output

The real benchmark upgrade report must include:

- candidate inventory
- fit matrix
- adapter attempt records
- accepted, rejected, and blocked statuses
- no-fit report, if applicable
- claim-language changes
- manuscript limitations
- release-gate contribution
