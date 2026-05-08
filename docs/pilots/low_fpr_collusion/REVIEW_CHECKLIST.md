# Low-FPR Collusion Pilot Review Checklist

Use this checklist for human review of the v0.9 low-FPR collusion pilot.

## Reviewer Metadata

- Reviewer:
- Role:
- Date:
- Artifacts reviewed:
- Relationship to project:

## Scope Review

- [ ] The pilot topic is clearly scoped to low false-positive collusion or covert coordination detection in LLM multi-agent systems.
- [ ] The objective is decision quality, not forced idea generation.
- [ ] Success, refusal, and product failure are distinct.
- [ ] Fixture, live-source, Codex, empirical, artifact, manuscript, and review evidence are labeled separately.

## Literature and Novelty Review

- [ ] Live source diagnostics exist.
- [ ] Search strategy covers direct, adjacent, benchmark, survey, and false-positive-control searches.
- [ ] Search rounds are recorded.
- [ ] Source coverage report lists missing searches and source failures.
- [ ] Paper canonicalization report exists.
- [ ] Prior-work recall assessment exists.
- [ ] Closest prior work is identified or the refusal explains why it could not be established.
- [ ] Novelty dossiers do not overclaim.
- [ ] No fake citation is present.

## Direction or Refusal Review

- [ ] If a direction is proposed, it is tied to an evidence-backed gap.
- [ ] If a direction is proposed, it has closest prior work and differentiating claims.
- [ ] If refused, the refusal explains novelty, evidence, coverage, or tractability blockers.
- [ ] The pilot does not pass with generic ideas.
- [ ] The decision includes concrete next evidence or work.

## Codex/GPT-5.4 Output Review

- [ ] Codex/GPT-5.4 synthesis task outputs exist or are marked blocked.
- [ ] Outputs were validated before import.
- [ ] Invalid outputs were repaired or classified as product failure.
- [ ] Codex did not invent citations, results, datasets, or reviewer feedback.
- [ ] Codex uncertainty is preserved as blockers, search requests, or refusal reasons.

## Experiment and Artifact Review

- [ ] Experiment protocol exists or refusal explains why it would overclaim.
- [ ] Protocol includes datasets/scenarios, baselines, metrics, low-FPR caveats, and falsification criteria.
- [ ] Benchmark or fixture experiment plan is clearly labeled.
- [ ] Empirical/artifact status distinguishes workflow mechanics from real empirical evidence.
- [ ] No fake result is present.
- [ ] Failed, negative, skipped, or underpowered status remains visible.
- [ ] Artifact hygiene separates safe-to-commit, private, generated, cache-only, and reviewer-facing artifacts.

## Manuscript and Rebuttal Review

- [ ] Manuscript draft or refusal report exists.
- [ ] Unsupported claims are labeled or removed.
- [ ] Result claims link to artifacts or are marked unsupported.
- [ ] Reviewer panel exists.
- [ ] Reviewer objections address novelty, baselines, metrics, low-FPR power, artifact state, and tractability.
- [ ] Rebuttal/revision plan maps objections to evidence, edits, experiments, or concessions.
- [ ] Rebuttal does not invent new evidence.

## Outcome Decision

Choose exactly one:

- [ ] `defensible_direction`: accept for continued research
- [ ] `correct_refusal`: accept refusal as the correct pilot outcome
- [ ] `product_failure`: reject pilot as product/workflow failure

## Required Notes

Decision rationale:

Blocking issues:

Required fixes:

Accepted risks:

v1 readiness impact:
