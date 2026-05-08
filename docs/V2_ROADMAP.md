# GapForge v2 Roadmap

v2 is the Idea Discovery Engine release.

v1.0 is a stable evidence-gated research OS. It can evaluate research directions, run literature campaigns, use Codex/GPT-5.4 task workflows, check novelty, design experiments, run benchmark workflows, produce manuscript packages, and refuse weak directions. v2 changes the default posture from evaluating the first plausible idea to actively searching across a portfolio of possible ideas.

The core v2 principle is:

> GapForge should try much harder to find a good idea, but it must not force a bad one.

v2 is successful only when it improves idea search pressure while preserving the v1 evidence gates. A refusal, fallback research agenda, or release failure remains valid when no candidate survives.

## Goals

1. Build topic portfolios instead of single-topic runs.
2. Generate multiple idea candidates per portfolio.
3. Mutate, combine, and stress-test candidates before ranking them.
4. Create constructive gaps by changing assumptions, datasets, methods, metrics, domains, or deployment constraints.
5. Expand cross-domain transfer search before deciding a field is exhausted.
6. Use Codex/GPT-5.4 for bounded idea synthesis tasks with strict output contracts.
7. Add an active idea search controller that chooses the next search, mutation, or rejection step.
8. Run novelty and counterevidence loops on candidates, not only on final directions.
9. Hold idea tournaments that compare candidates under shared evidence standards.
10. Capture human preference feedback and use it to steer future search.
11. Produce a research agenda fallback when no idea is accepted.
12. Track idea yield metrics so release notes report search productivity honestly.
13. Make the v2 release gate fail unless at least one idea candidate is accepted or the release explicitly records idea-discovery failure and plans v2.0.1 or v2.1.

## How v2 Differs From v1

v1 asks: given this research direction, is it defensible enough to continue?

v2 asks: across a bounded topic portfolio, can GapForge discover at least one defensible candidate, and can it explain why the other candidates failed?

The difference is search behavior, not weaker acceptance. v2 adds more attempts, more variants, more transfer routes, more counterevidence checks, more human preference data, and more yield reporting. It does not relax novelty, citation, empirical, manuscript, artifact, or human-review gates.

## Must-Have Workstreams

### Topic Portfolios

The v2 unit of search is a portfolio, not a single seed. A portfolio should include:

- topic family and subtopics
- target communities or venues
- excluded areas
- source profiles
- risk appetite and feasibility constraints
- known prior work and blocked directions
- human preferences and dispreferences

The portfolio should preserve negative results. Failed subtopics are part of the search evidence.

### Idea Candidates

An idea candidate is a structured object that can be debated and rejected before it becomes a research direction. It should include:

- candidate ID
- originating topic, gap, mutation, or transfer source
- problem statement
- proposed insight or intervention
- closest-prior-work hypotheses
- expected evidence requirements
- feasibility assumptions
- risk flags
- current status
- human preference signal, if any

Candidates are not paper-ready. They are search artifacts until accepted.

### Idea Mutation

v2 should create variants through controlled mutation:

- narrower population or setting
- stricter metric or evaluation constraint
- alternate dataset, benchmark, or environment
- changed failure mode or threat model
- simpler method or baseline-first framing
- stronger falsification criterion
- negative-result or measurement-study reframing

Mutations must record their parent candidate and why the mutation may improve novelty, feasibility, or evidence quality.

### Constructive Gap Creation

v2 should not only mine obvious gaps. It should construct defensible gaps by asking what changes make a problem newly answerable or newly important:

- new deployment constraint
- new safety or reliability requirement
- new measurement protocol
- new cross-domain analogy
- new artifact availability
- new evaluation standard
- new failure analysis angle

Constructive gaps still require prior-work checks. A creative gap is not accepted until evidence survives.

### Cross-Domain Transfer Expansion

v2 should search neighboring fields for methods, metrics, threat models, datasets, and failure analyses that can transfer into the target portfolio.

Transfer candidates should record:

- source domain
- target domain
- transferred concept
- adaptation required
- likely closest prior work in both domains
- reason transfer may create a defensible contribution

Transfer is a search tactic, not novelty proof.

### Codex/GPT-5.4 Idea Synthesis Tasks

Codex/GPT-5.4 may synthesize candidates, mutations, tournament critiques, and search requests from recorded state. It must use task packs with schema validation and known evidence IDs. It must not invent citations, results, datasets, or paper-ready novelty claims.

### Active Idea Search Controller

The controller should choose among:

- expand portfolio
- retrieve more literature
- create candidate
- mutate candidate
- run cross-domain transfer
- search closest prior work
- gather counterevidence
- run tournament
- ask for human preference feedback
- accept candidate
- reject candidate
- produce research agenda fallback

Controller decisions must record inputs, stop reason, and next action.

### Novelty and Counterevidence Loop

Every serious candidate should face closest-prior-work search and counterevidence before acceptance. Counterevidence can include:

- prior work already solves the problem
- missing source coverage
- weak or impossible empirical protocol
- unclear contribution over baselines
- infeasible data access
- human rejection
- likely negative or unpublishable framing

Counterevidence should improve future search rather than disappear.

### Idea Tournament

Candidates should compete under common criteria:

- novelty risk
- evidence availability
- feasibility
- falsifiability
- expected contribution
- artifact path
- human preference
- downside risk

Tournament winners are not automatically accepted. They move to the accepted-candidate gate only after evidence review.

### Human Preference Feedback

v2 must capture human preferences without letting taste override evidence. Feedback should guide search breadth, topic priority, risk appetite, and acceptable tradeoffs. It cannot make an unsupported candidate pass.

### Research Agenda Fallback

If no idea is accepted, v2 should emit a research agenda rather than fake success. The agenda should list best rejected candidates, missing evidence, recommended searches, likely pivots, and conditions that would justify reopening the search.

### Idea Yield Metrics

v2 must report search productivity:

- portfolio count
- candidate count
- mutation count
- transfer count
- rejection reasons
- tournament results
- accepted-candidate rate
- human-feedback impact
- search cost and stop reasons
- agenda fallback status

## Non-Goals

- Do not weaken evidence gates.
- Do not invent citations.
- Do not invent results.
- Do not force a generic idea to pass.
- Do not treat speculative seeds as paper-ready.
- Do not remove correct refusal as a possible outcome.
- Do not bypass human review.
- Do not treat high candidate volume as research quality.
- Do not present idea tournament ranking as novelty proof.

## Milestones

1. v2 documentation and acceptance criteria.
2. Topic portfolio schema and reports.
3. Idea candidate schema, statuses, and rejection records.
4. Mutation and constructive-gap generators.
5. Cross-domain transfer expansion records.
6. Codex/GPT-5.4 task-pack contracts for idea synthesis.
7. Active idea search controller with decision logs.
8. Novelty/counterevidence loop for candidates.
9. Idea tournament and human-feedback records.
10. Research agenda fallback export.
11. Idea yield metrics and v2 release gate.

## Implemented Surfaces

v2 workflows are available through both CLI commands and Python API wrappers. The CLI is intentionally thin; implementation lives in `src/gapforge/ideas/`, `src/gapforge/release_gate/v2.py`, and shared managers.

Core CLI:

```bash
gapforge topic-portfolio --project-id <project-id>
gapforge idea-generate --project-id <project-id>
gapforge mutate-idea --idea-id <idea-id>
gapforge constructive-gaps --project-id <project-id>
gapforge transfer-ideas --project-id <project-id>
gapforge idea-codex-task --project-id <project-id> --type idea_seed_expansion
gapforge idea-codex-import --task-id <task-id>
gapforge idea-search --project-id <project-id>
gapforge idea-novelty --idea-id <idea-id>
gapforge idea-tournament --project-id <project-id>
gapforge idea-feedback --idea-id <idea-id> --action accept
gapforge research-agenda --project-id <project-id>
gapforge idea-yield --project-id <project-id> --write-report
gapforge dashboard --project-id <project-id> --include-ideas
gapforge v2-release-gate --write-report --json
```

Python API:

```python
from gapforge import api

portfolio = api.generate_topic_portfolio(project_id=project_id)
ideas = api.generate_ideas(project_id=project_id)
tournament = api.run_idea_tournament(project_id)
feedback = api.add_idea_feedback(tournament.selected_candidate_id, "accept")
gate = api.v2_release_gate(write_report=True)
```

The release claim still depends on the accepted-candidate standard. Seeds, mutations, transfer search requests, constructive gaps, Codex suggestions, and tournament winners are not accepted ideas until they pass evidence and human-review gates.

## Release Claim

The strongest allowed v2 release claim is:

`v2 actively searches across topic portfolios and reports whether at least one idea candidate survived the evidence gates.`

If no candidate is accepted, v2 can still be honest, but the release gate must record explicit idea-discovery failure and route the work to v2.0.1 or v2.1 planning rather than claiming success.
