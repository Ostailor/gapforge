# Low-FPR Collusion Pilot Acceptance Criteria

This pilot accepts three distinct outcomes: defensible direction, correct refusal, and product failure. Only the first two can count as successful v0.9 pilot outcomes.

## Universal Criteria

The pilot has a clear scope when:

- the project record names `low_fpr_collusion`
- the topic is `low false-positive collusion detection in LLM multi-agent systems`
- the objective is to test whether a defensible research direction exists
- required outputs are present or explicitly blocked
- live source, fixture, Codex, empirical, artifact, manuscript, and review states are separated

The system cannot pass the pilot by generating generic ideas. Any proposed direction must link to:

- evidence-backed gap
- closest prior work
- prior-work recall gate
- experiment protocol
- reviewer objections
- human review acceptance

## Outcome A: Defensible Direction

Accept as `defensible_direction` only if all conditions hold:

- an evidence-backed gap exists
- closest prior work is identified and cited from known paper records
- prior-work recall gate has run and does not block the direction
- novelty is stated conservatively
- source coverage report exposes missing searches and does not hide weak coverage
- paper canonicalization report exists
- Codex/GPT-5.4 synthesis outputs are validated and imported
- novelty dossiers exist for the candidate direction
- related-work matrix includes closest prior work and differentiating claims
- experiment protocol exists with datasets/scenarios, baselines, metrics, low-FPR caveats, and falsification criteria
- benchmark or fixture experiment plan exists and is clearly labeled
- empirical/artifact status distinguishes fixture mechanics from real empirical evidence
- manuscript draft labels unsupported claims, missing citations, missing results, and limitations
- reviewer panel raises novelty, metric, baseline, false-positive, artifact, and tractability objections
- rebuttal/revision plan maps objections to evidence, edits, experiments, or concessions
- no fake citation slips through
- no fake result slips through
- human review accepts the direction for continued research

## Outcome B: Correct Refusal

Accept as `correct_refusal` only if the refusal:

- explains insufficient novelty, evidence, source coverage, or experimental tractability
- identifies closest prior work or explains why closest prior work could not be established
- lists missing searches or source blockers
- records source diagnostics and campaign state
- preserves Codex/GPT-5.4 validation/import status
- records why a benchmark, fixture plan, manuscript draft, or rebuttal plan would overclaim
- does not invent a direction
- does not invent citations, results, datasets, or reviewers
- gives concrete next evidence that would change the decision
- receives human review acceptance as a correct refusal

Correct refusal is a successful pilot outcome when it protects GapForge from overclaiming.

## Outcome C: Product Failure

Classify as `product_failure` when any of these happen:

- workflow breaks before the pilot can reach a decision
- Codex/GPT-5.4 output cannot be validated or imported and the repair path fails
- report language overclaims novelty, evidence, empirical success, or readiness
- fake citation slips through validation
- fake result slips through validation
- source coverage gate behaves incorrectly
- novelty gate behaves incorrectly
- prior-work recall gate fails to block a weak direction
- product docs or CLI make fixture evidence look like real empirical evidence
- pilot status cannot explain missing project or missing artifacts

Product failure does not count as a successful pilot. It should become a v0.9.1 or later fix depending on severity.

## Required Output Checklist

- [ ] Project record
- [ ] Campaign record
- [ ] Live source diagnostics
- [ ] Search strategy
- [ ] Search rounds
- [ ] Source coverage report
- [ ] Paper canonicalization report
- [ ] Prior-work recall assessment
- [ ] Codex/GPT-5.4 synthesis task outputs
- [ ] Novelty dossiers
- [ ] Related-work matrix
- [ ] Research direction or refusal
- [ ] Experiment protocol
- [ ] Benchmark or fixture experiment plan
- [ ] Empirical/artifact status
- [ ] Manuscript draft or refusal report
- [ ] Reviewer panel
- [ ] Rebuttal/revision plan
- [ ] Final pilot report

## Pass/Fail Summary

- `defensible_direction`: pass
- `correct_refusal`: pass
- `product_failure`: fail

The final pilot report must state which outcome occurred and why the other two outcomes were rejected.
