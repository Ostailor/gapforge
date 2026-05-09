# GapForge v2.3 Go/No-Go Decisions

v2.3 ends with a decision, not necessarily a success claim. Honest `revise`, `run_more_experiments`, and `no_go` outcomes are valid release outcomes when the evidence is labeled correctly.

## Decision Models

`SelectedBenchmarkGoNoGo.decision` may be:

| Decision | Meaning | Allowed Claim |
| --- | --- | --- |
| `go_publication_candidate` | Powered alpha target, related work, baselines, reviewer status, and manuscript traceability all pass for the stated scope. | Publication-candidate package for the bounded benchmark scope. |
| `revise_benchmark` | Benchmark, data, related work, baselines, or manuscript package are insufficient but the idea is not rejected. | v2.3 found concrete revisions; no publication-candidate claim. |
| `run_more_experiments` | Power, dataset size, or baseline execution is insufficient but feasible to improve. | More main-scale work is required before publication claims. |
| `no_go` | The idea or claim fails due to baselines, novelty, validity, or fatal blockers. | No-go is the result; preserve the evidence and reason. |

`PublicationReadinessReview.readiness` may be:

| Readiness | Meaning |
| --- | --- |
| `not_ready` | Missing or failed gates remain. |
| `workshop_candidate` | Pilot or limited main evidence can be discussed with strong caveats. |
| `conference_candidate` | Main evidence and gates support the bounded claim. |
| `no_go` | Fatal publication blockers make the package unsuitable. |

`v23_release_gate` may pass with these honest outcomes:

| Gate Outcome | Meaning |
| --- | --- |
| `publication_candidate` | Complete evidence is consistently labeled as candidate-level. |
| `workshop_candidate` | Limited evidence is consistently labeled with caveats. |
| `revise_benchmark` | The release records the needed revision path. |
| `no_go` | The release records an honest negative decision. |

The gate must fail if evidence is mislabeled, even when artifacts exist.

## Blocking Overclaims

The go/no-go path must block:

- synthetic evidence described as deployment validity
- `alpha=0.001` claimed without a powered `MainPowerDecision`
- fallback-only related work counted as real coverage
- missing required baselines hidden from the baseline assessment
- pilot-only results labeled as main results
- publication readiness while fatal reviewer blockers remain

## Commands

```bash
gapforge selected-main-analysis --execution-id <main-execution-id>
gapforge selected-benchmark-go-no-go --benchmark-id <benchmark-id>
gapforge selected-go-no-go-report --benchmark-id <benchmark-id>
gapforge selected-publication-review --benchmark-id <benchmark-id>
gapforge selected-main-paper-package --benchmark-id <benchmark-id>
gapforge v23-release-gate --write-report --json
```

## Dashboard and API

Dashboard:

```bash
gapforge dashboard --project-id <project-id> --include-selected-main
```

Relevant pages:

- `go_no_go.html`
- `publication_review.html`
- `main_manuscript.html`
- `v23_release_gate.html`

API:

```python
from gapforge import api

analysis = api.analyze_selected_main(execution_id)
decision = api.selected_go_no_go(benchmark_id)
review = api.selected_publication_review(benchmark_id)
package = api.selected_main_manuscript(benchmark_id)
gate = api.v23_release_gate(write_report=True)
```

No API helper is allowed to upgrade the decision beyond the evidence maturity recorded in the persisted artifacts.
