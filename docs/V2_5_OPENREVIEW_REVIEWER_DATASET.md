# GapForge v2.5 OpenReview Reviewer Dataset

v2.5 creates an OpenReview-style review dataset and reviewer-calibration workflow. The purpose is critique calibration: making simulated reviews harsher, more specific, and more realistic. It is not truth generation and does not predict acceptance.

## Dataset Scope

The review dataset may use public review records only when use is allowed by source availability, license, venue policy, and privacy expectations. Records should be treated as public critique examples, not as a source of private reviewer identity or hidden ground truth.

Each dataset record must include:

- `review_record_id`
- source URL or stable identifier
- venue or venue family, if public
- year, if public
- paper decision status, if public and allowed
- review text fields available
- score fields available
- confidence fields available
- license or use-policy note
- retrieval date
- redaction status
- inclusion reason
- exclusion reason, if rejected

## Privacy and Use Constraints

The dataset must not:

- infer reviewer identity
- deanonymize authors or reviewers
- scrape private reviews
- include unavailable or access-controlled content
- copy reviews into public artifacts when license or policy disallows redistribution
- use review text to fabricate paper-specific facts

When redistribution is unclear, store metadata and derived labels only, and require local retrieval by the user.

## Review Schema

The normalized schema should capture review shape:

- summary
- strengths
- weaknesses
- questions
- novelty concerns
- soundness concerns
- empirical-validity concerns
- benchmark-validity concerns
- reproducibility concerns
- clarity concerns
- ethics or broader-impact concerns
- missing-related-work concerns
- rebuttal-sensitive objections
- score and confidence, when public and allowed
- final recommendation, when public and allowed

Free-form text may be stored only when allowed. Derived labels must remain traceable to the source record.

## Calibration Targets

The reviewer calibration workflow should learn or configure:

- severity distribution
- objection specificity
- score-confidence coupling
- novelty-risk language
- benchmark-validity critique
- empirical-design critique
- missing-baseline critique
- reproducibility critique
- rebuttal pressure points
- area-chair style synthesis

Calibration should make reviews more realistic and stricter. It must not train the reviewer to invent external facts.

## Reviewer Outputs

A calibrated reviewer pass on the selected manuscript must produce:

- review summary
- strengths
- major weaknesses
- minor weaknesses
- questions for authors
- novelty assessment
- soundness assessment
- empirical and benchmark validity assessment
- reproducibility assessment
- score and confidence, if the selected rubric uses them
- objection evidence class: `evidence_backed`, `plausible_concern`, or `speculative`
- required manuscript changes
- rebuttal-critical objections
- final accept/reject-style recommendation, labeled as simulated

The output must distinguish known evidence from plausible reviewer concern. A reviewer may be harsh without fabricating facts.

## Training and Evaluation

v2.5 may use a trained model, tuned prompt, rubric, retrieval-augmented critic, or hybrid process. The chosen method must be evaluated against held-out or manually inspected review records where possible.

Evaluation should report:

- dataset size and source mix
- train/eval split or rubric validation method
- severity calibration
- hallucinated citation rate
- unsupported result-reference rate
- objection specificity
- coverage of benchmark, novelty, empirical, reproducibility, and clarity concerns
- human spot-check outcome

If no model training is feasible, a rubric-calibrated reviewer can pass only when the rubric is source-grounded, evaluated, and produces the required harsh reviewer pass.

## Anti-Fabrication Rules

Reviewer models and rubrics must not:

- invent citations, venues, baselines, datasets, metrics, or results
- claim a paper failed a benchmark that was not run
- cite unattached prior work as fact
- state reviewer consensus as real
- produce fake OpenReview records
- hide severe objections to improve readiness status
- turn simulated scores into acceptance predictions

Unknown comparisons must become search requests or plausible concerns.

## Manuscript and Rebuttal Linkage

The calibrated reviewer pass must feed:

- objection-to-change matrix
- manuscript revision plan
- rebuttal response plan
- unresolved objection list
- claim narrowing or removal
- extra adapter or experiment requirements
- final release decision

Every major objection must be classified as:

- `resolved_with_evidence`
- `resolved_with_manuscript_edit`
- `accepted_with_narrowed_claim`
- `accepted_as_limitation`
- `requires_new_experiment`
- `fatal`

Fatal objections cannot be hidden or softened.

## Completion Output

The OpenReview reviewer workflow ends with one status:

- `calibrated_review_pass_complete`: dataset, calibration, evaluation, and selected-paper review pass exist.
- `calibrated_review_pass_complete_with_warnings`: artifacts exist, but dataset or evaluation limits remain visible.
- `rubric_only_pass`: no model training occurred, but a validated rubric produced the required critique.
- `blocked_dataset_policy`: review records cannot be used safely.
- `blocked_hallucination`: reviewer model fabricates citations, results, or external facts.
- `blocked_review_quality`: reviews are too generic, too soft, or not actionable.

Only the first three statuses can satisfy v2.5, and only if objections remain visible in the manuscript/rebuttal package.

## Scriptable and Visible Surface

CLI:

```bash
gapforge review-dataset-create --name openreview_like
gapforge review-dataset-ingest-fixture
gapforge review-dataset-report --dataset-id <dataset-id>
gapforge review-labels-generate --dataset-id <dataset-id>
gapforge review-taxonomy-report --dataset-id <dataset-id>
gapforge reviewer-train --dataset-id <dataset-id> --mode heuristic
gapforge reviewer-evaluate --dataset-id <dataset-id>
gapforge reviewer-calibration-report --dataset-id <dataset-id>
gapforge drastic-review --manuscript-id <manuscript-id>
gapforge drastic-revision-plan --manuscript-id <manuscript-id>
gapforge dashboard --project-id <selected-project-id> --include-selected-v25
```

API:

- `create_review_dataset(...)`
- `train_reviewer(...)`
- `evaluate_reviewer(...)`
- `run_drastic_review(...)`
- `create_drastic_revision_plan(...)`

Dashboard:

- `openreview_dataset.html`
- `review_taxonomy.html`
- `reviewer_calibration.html`
- `drastic_review.html`
- `drastic_revision.html`
- `v25_release_gate.html`

These surfaces make critique calibration auditable. They must not be used to create fake OpenReview data, fake reviews, fake citations, fake results, or acceptance predictions.
