# GapForge v2 Idea Discovery

v2 idea discovery is an active search process. It should generate, mutate, compare, and reject candidates before recommending one.

## Discovery Loop

The v2 loop is:

1. Build or update a topic portfolio.
2. Generate initial idea candidates.
3. Search for closest prior work and obvious counterevidence.
4. Mutate promising or ambiguous candidates.
5. Create constructive gaps by changing constraints, metrics, datasets, methods, or domains.
6. Expand cross-domain transfers.
7. Ask Codex/GPT-5.4 for bounded synthesis tasks when useful.
8. Run an idea tournament.
9. Capture human feedback.
10. Accept, reject, continue searching, or emit a research agenda fallback.

Every loop should have a stop reason. Search can stop because a candidate is accepted, budgets are exhausted, evidence is insufficient, human review rejects the portfolio, or the controller chooses agenda fallback.

## Candidate Statuses

Persisted idea maturity uses:

- `seed`: provisional idea produced by portfolio generation, mutation, constructive gap creation, transfer, or Codex import.
- `candidate`: specific enough to enter novelty, evidence, feasibility, and tournament checks.
- `rejected`: preserved negative search result with rejection reason.
- `agenda_item`: useful blocker or next step, but not an accepted idea.
- `experiment_ready`: accepted candidate with an executable experiment path.
- `manuscript_ready`: later-stage state after empirical/manuscript gates, not an idea-discovery shortcut.

Search reports may also use workflow labels such as `needs_search`, `needs_mutation`, `human_review_required`, or `blocked`, but these labels must not replace persisted maturity. Do not use `paper_ready`, `proven`, or `novel` as candidate statuses.

## Accepted Idea Standard

An accepted idea is not just a good-sounding title. It must have:

- a specific contribution type such as benchmark, measurement, method, theory, negative result, replication, dataset, survey, system, evaluation protocol, tooling, or hybrid
- a clear core claim and proposed experiment or artifact path
- expected baselines and metrics when empirical
- closest-prior-work and counterevidence review
- no fake citations, fabricated results, or unsupported strong novelty claims
- tournament comparison against other surviving candidates
- human review or feedback action accepting the candidate for a stated scope

A seed is allowed to be speculative. An accepted idea is not. A research agenda is the honest fallback when no candidate reaches this standard.

## Candidate Record

Each candidate should record:

```text
Candidate ID:
Portfolio ID:
Origin:
Parent candidate IDs:
Problem statement:
Proposed contribution:
Target audience or venue family:
Known prior work:
Closest-prior-work hypotheses:
Evidence needed:
Experiment path:
Mutation history:
Transfer source:
Counterevidence:
Human feedback:
Tournament score:
Status:
Stop reason:
```

## Mutation Types

Recommended mutation types:

- `scope_narrowing`
- `metric_tightening`
- `dataset_shift`
- `baseline_reframe`
- `failure_mode_reframe`
- `negative_result_reframe`
- `measurement_study_reframe`
- `artifact_first_reframe`
- `domain_transfer`
- `threat_model_shift`

Mutation should make a candidate more specific, more testable, more novel, or more honestly rejectable. Mutation should not add vagueness.

## Constructive Gap Creation

Constructive gap creation asks what would make a real contribution possible:

- a stricter reliability or safety requirement
- a newly available artifact
- a domain-specific failure mode
- a metric that exposes a missed weakness
- a benchmark slice that prior work did not isolate
- a deployment constraint that changes the problem
- a replication or negative-result opportunity

Constructive gaps must be checked against prior work before acceptance.

## Cross-Domain Transfer

A transfer expansion should search for analogies from:

- adjacent ML subfields
- security and abuse detection
- software engineering evaluation
- human-computer interaction
- economics or mechanism design
- statistics and measurement
- systems reliability

Each transfer should say what is being transferred and what must change before it fits the target domain.

## Codex/GPT-5.4 Synthesis Tasks

Codex/GPT-5.4 may help with:

- generating candidate variants from a portfolio
- proposing mutation routes
- summarizing counterevidence
- identifying transfer domains
- drafting tournament critiques
- converting failed candidates into agenda items

Codex/GPT-5.4 must receive allowed paper IDs, evidence locators, candidate IDs, and output schemas. Unknown citations become search requests. Unsupported novelty becomes risk language.

Expected task-pack outputs are validation patches, not direct state mutations:

- `idea_candidates_patch.json`
- `idea_mutations_patch.json`
- `constructive_gaps_patch.json`
- `transfer_candidates_patch.json`
- `idea_reviews_patch.json`
- `agenda_patch.json`

Imports must reject fake citations, fake results, generic ideas, unresolved evidence links, and strong novelty without prior-work gates.

## Controller Decisions

The active search controller should record:

- current portfolio state
- candidate counts by status
- available budget
- evidence gaps
- human feedback
- selected next action
- rejected next actions, if useful
- stop reason

Controller choices are auditable decisions, not hidden agent intuition.

## Research Agenda Fallback

When no candidate is accepted, produce an agenda with:

- top rejected candidates and rejection reasons
- promising but under-evidenced mutations
- missing searches
- transfer domains worth revisiting
- evidence that would change the decision
- recommended next release lane

The fallback should help future work without pretending an idea passed.

## Scriptable Workflow

CLI:

```bash
gapforge topic-portfolio --project-id <project-id>
gapforge idea-generate --project-id <project-id> --max-candidates 50
gapforge mutate-rejected-ideas --project-id <project-id>
gapforge constructive-gaps --project-id <project-id>
gapforge transfer-ideas --project-id <project-id>
gapforge idea-search --project-id <project-id> --max-iterations 5
gapforge idea-novelty --project-id <project-id> --top-k 10
gapforge idea-tournament --project-id <project-id>
gapforge idea-feedback --idea-id <idea-id> --action accept
gapforge idea-yield --project-id <project-id> --write-report
```

Python:

```python
from gapforge import api

api.generate_topic_portfolio(project_id=project_id)
api.generate_ideas(project_id=project_id)
api.run_idea_novelty(project_id=project_id)
api.run_idea_tournament(project_id)
api.add_idea_feedback(idea_id, "accept")
```
