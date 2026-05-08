# Low-FPR Collusion Pilot Specification

## Pilot Identity

- **Name**: `low_fpr_collusion`
- **Topic**: low false-positive collusion detection in LLM multi-agent systems
- **Release target**: GapForge v0.9 external pilot
- **Primary objective**: use GapForge to determine whether there is a defensible research direction around low false-positive detection of collusion or covert coordination among LLM-based agents.

This pilot is not required to produce a publishable idea. It is required to produce an honest decision. The valid outcomes are a defensible direction, a correct refusal, or a product failure.

## Scope

The pilot starts from a broad research topic and must exercise the full GapForge workflow:

1. project setup
2. live literature campaign
3. source diagnostics and search planning
4. paper canonicalization and coverage review
5. prior-work recall and novelty assessment
6. Codex/GPT-5.4 synthesis through validated task outputs
7. related-work and direction decision
8. experiment protocol
9. benchmark or fixture experiment plan
10. empirical and artifact status
11. manuscript draft or refusal report
12. reviewer panel
13. rebuttal or revision plan
14. final pilot report

The system cannot pass this pilot by generating generic ideas. A direction must be tied to evidence, closest prior work, a prior-work recall gate, an experiment protocol, reviewer objections, and human review.

## Research Question

Can GapForge identify a credible research direction for detecting collusion or covert coordination among LLM-based agents while keeping false positives low enough for practical monitoring?

The pilot should treat false positives as a first-class research constraint. A vague detector that flags suspicious behavior without calibration, baselines, power caveats, or review is not a defensible direction.

## Required Outputs

The pilot is complete only when each output exists or has a recorded blocker/refusal reason:

- project record
- campaign record
- live source diagnostics
- search strategy
- search rounds
- source coverage report
- paper canonicalization report
- prior-work recall assessment
- Codex/GPT-5.4 synthesis task outputs
- novelty dossiers
- related-work matrix
- research direction or refusal
- experiment protocol
- benchmark or fixture experiment plan
- empirical/artifact status
- manuscript draft or refusal report
- reviewer panel
- rebuttal/revision plan
- final pilot report

## Evidence Rules

- Real source records must be distinguished from fixture or fallback records.
- Codex/GPT-5.4 output must be validated and imported before it can affect pilot state.
- Unknown citations become search requests or blockers, not references.
- Novelty claims require closest-prior-work evidence and a prior-work recall gate.
- Empirical claims require execution records and result artifacts.
- Fixture experiment plans validate workflow mechanics only.
- A refusal can be successful when it prevents overclaiming.

## Expected Literature Campaign

The campaign should include search rounds for:

- low false-positive collusion detection in LLM agents
- covert coordination among language-model agents
- multi-agent LLM monitoring and anomaly detection
- collusion benchmarks or evaluations for autonomous agents
- false-positive control, calibration, precision, and power analysis for AI safety monitors
- closest surveys and benchmark papers for agent evaluation and collusion detection

The search strategy must record live source diagnostics, source failures, skipped sources, manual additions, and missing searches.

## Direction Decision

The pilot must end with one of these classifications:

- `defensible_direction`: evidence-backed gap with closest prior work, recall gate, protocol, reviewer objections, and human review acceptance
- `correct_refusal`: insufficient novelty, evidence, source coverage, or experimental tractability, with missing searches or blockers listed
- `product_failure`: GapForge workflow or validation behavior failed in a way that invalidates the pilot result

## Experiment Expectations

A defensible direction needs an experiment protocol covering:

- dataset or scenario source
- baseline detector or comparison method
- metric definitions, including false positive rate
- sample-size or power caveats for low-FPR claims
- fixture, benchmark-like, small real run, and full benchmark boundaries
- expected artifacts, logs, manifests, and reproducibility notes
- falsification criteria

If no tractable protocol exists, the pilot should refuse rather than invent an experiment.

## Artifact and Manuscript Expectations

The pilot should produce either:

- a manuscript draft with unsupported claims labeled, citations resolved, results artifact-backed, limitations visible, and reviewer objections recorded; or
- a refusal report explaining why a manuscript draft would overclaim the evidence.

Artifact status must classify outputs as safe-to-commit, private, generated, cache-only, reviewer-facing, incomplete, or blocked.

## Final Pilot Report

The final report must state:

- pilot outcome
- evidence supporting the outcome
- blockers and missing searches
- closest prior work
- Codex/GPT-5.4 validation/import status
- empirical/artifact status
- reviewer objections
- human review decision
- whether the issue is research refusal or product failure
- v1 readiness impact
