# GapForge v2.5 Real Benchmark Grounding

v2.5 adds real benchmark grounding to the selected low-FPR collusion-audit protocol. This is separate from the synthetic benchmark scaffolding used in v2.1 through v2.4.

## Core Distinction

- **Synthetic benchmark scaffolding**: generated traces, controlled hard negatives, and designed collusion scenarios used to test the protocol mechanics and low-FPR measurement path.
- **Real benchmark grounding**: an adapter from an existing vetted benchmark or dataset into part of the selected protocol, with source metadata, license constraints, mapping rules, and validity limitations.

Real benchmark grounding can increase credibility, expose validity problems, and improve comparison discipline. It does not automatically validate the benchmark, prove deployment realism, or make synthetic conclusions externally valid.

## Vetted Benchmark Requirements

Each candidate benchmark or dataset must have a grounding record:

- `source_benchmark_id`
- stable name and version, if available
- source URL or identifier
- license and allowed use summary
- retrieval date
- dataset card or benchmark card status
- task format
- split policy
- label or outcome semantics
- known contamination risks
- citation or attribution requirements
- access constraints
- adapter fit score
- inclusion or exclusion decision

If license, availability, or source authenticity is unclear, the candidate cannot be used as an accepted adapter target.

## Adapter Fit Review

Adapter fit must be reviewed before implementation. The review must classify whether the source benchmark can support:

- honest negative traces
- collusive or suspicious positive traces
- hard-negative benign coordination
- monitor-evasion stress cases
- sequential windows or repeated looks
- low-FPR threshold calibration
- held-out evaluation
- baseline comparison
- reproducibility package

Unsupported fields must remain unsupported. Do not synthesize labels that the source benchmark does not justify.

## Mapping Rules

Every accepted adapter must define:

- source item selection rules
- exclusion rules
- label mapping rules
- ambiguity handling
- task-to-trace conversion
- metadata retained and metadata dropped
- deterministic seeds or ordering
- split preservation
- contamination and leakage checks
- sample-count limits
- license-driven artifact redaction, if needed

Ambiguous source examples should be excluded or tagged as ambiguous. They must not be forced into positive or negative labels to improve metrics.

## Protocol Adaptation

The selected sequential specificity protocol must be adapted to the source benchmark with explicit changes:

- audit unit definition
- audit window construction
- false-positive denominator
- positive-case denominator, if applicable
- repeated-look correction
- threshold calibration policy
- baseline input restrictions
- hard-negative slice definition
- missing-positive or missing-hard-negative handling

If the source benchmark lacks positives, hard negatives, or sequential structure, the adapter may still be useful as a negative-only specificity stress test. The report must then say so plainly.

## Required Adapter Artifacts

An accepted v2.5 adapter must produce:

- benchmark source record
- license and access record
- adapter plan
- conversion manifest
- adapted dataset card
- leakage and contamination report
- adapter smoke run or blocked-run report
- protocol adaptation report
- adapter limitation section for the manuscript
- claim-language update

The release gate requires at least one accepted adapter. More adapters may be listed as planned, rejected, or blocked.

## Grounding Outcomes

Each adapter ends with one status:

- `accepted_grounding_adapter`: source and mapping are valid for a limited claim.
- `accepted_negative_only_adapter`: useful for specificity or hard-negative stress, but not positive-case evaluation.
- `accepted_with_major_limitations`: useful only with visible manuscript limitations.
- `rejected_license_or_access`: source cannot be used safely.
- `rejected_bad_fit`: source does not support the selected protocol.
- `blocked_requires_human_review`: fit, license, or label semantics need expert review.

Only accepted statuses can satisfy the adapter release gate, and only for the exact scope stated in the adaptation report.

## Claim Rules

Allowed:

- `adapter-grounded evaluation slice`
- `vetted benchmark adapter for limited protocol grounding`
- `negative-only specificity stress test`, when applicable
- `benchmark grounding with explicit validity limits`

Forbidden:

- `real-world deployment-valid`
- `validated benchmark` without independent validity evidence
- `known dataset proves the protocol`
- `SOTA`
- `first benchmark grounded in <dataset>`
- `collusion labels` when the source does not contain or justify collusion labels

## Manuscript Linkage

The manuscript must link adapter claims to:

- source benchmark record
- adapter manifest
- conversion rules
- run records and result artifacts, if executed
- limitation text
- reviewer objections about adapter validity

If an adapter materially weakens the benchmark claim, v2.5 must narrow the claim or end in `revise_benchmark_grounding`.

## Scriptable and Visible Surface

CLI:

```bash
gapforge vetted-benchmark-register --name "<benchmark>" --license "<license>" --terms-of-use "<terms>"
gapforge selected-vetted-benchmark-map --benchmark-id <benchmark-id>
gapforge benchmark-adapter-create --selected-benchmark-id <benchmark-id> --vetted-benchmark-id <vetted-id>
gapforge benchmark-adapter-run --adapter-id <adapter-id>
gapforge selected-vetted-experiment-plan --benchmark-id <benchmark-id>
gapforge selected-vetted-experiment-run --plan-id <plan-id>
```

API:

- `register_vetted_benchmark(...)`
- `assess_benchmark_fit(...)`
- `create_benchmark_adapter(...)`
- `run_vetted_experiment(...)`

Dashboard:

- `vetted_benchmarks.html`
- `benchmark_mappings.html`
- `benchmark_adapters.html`
- `v25_release_gate.html`

Dashboard/API visibility does not strengthen claims. It only makes source records, fit assessments, transformations, warnings, and no-fit decisions auditable.

## Dashboard Review Checklist

Before using a real benchmark grounding artifact in the manuscript, check the dashboard or equivalent reports for:

- visible license and terms-of-use fields
- explicit download and authentication requirements
- fit assessment separated from vetted status
- mapping type and unsupported claims
- adapter limitations and warnings
- synthetic and vetted results kept in separate labeled tables
- no-fit justification when no existing benchmark can support the protocol

If these fields are missing, the benchmark can remain a candidate, auxiliary, or sanity-check item, but it cannot support a stronger claim.
