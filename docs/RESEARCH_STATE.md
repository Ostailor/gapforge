# Research State

`ResearchRunState` is the central state object for a run.

It contains:

- `topic`: canonical topic text, slug, and creation time
- `papers`: normalized search results
- `paper_notes`: reading notes and evidence snippets
- `paper_triage`: tiered reading-priority decisions
- `field_map`: structured map of clusters, methods, datasets, metrics, saturation signals, underexplored areas, contradictions, adjacent fields, and initial gap candidates
- `claims`: auditable assertions
- `gaps`: candidate research gaps
- `hypotheses`: generated directions
- `cross_domain_analogies`: skeptical source-field mappings and adjacent-field search queries
- `novelty_assessments`: closest-prior-work checks with reject/revise/pursue/unknown verdicts
- `experiments`: experiment-ready plans
- `reviewer_objections`: simulated critique
- `reviewer_summaries`: readiness scores, blocking issues, required fixes, and final recommendations
- `orchestrator_plan`: resumable step plan with status for each stage
- `orchestrator_result`: current run status, completed/failed/skipped steps, and artifacts
- `run_log`: timestamped orchestration events and recoverable warnings
- `completed_skills`: executed skill names

State is persisted to `state.json` in each run directory. User-facing artifacts are written beside it:

- `topic.md`
- `config.json`
- `papers.json`
- `paper_notes.json`
- `paper_notes.md`
- `paper_triage.json`
- `paper_triage.md`
- `field_map.json`
- `field_map.md`
- `gaps.json`
- `gaps.md`
- `claims.json`
- `hypotheses.json`
- `cross_domain_analogies.json`
- `cross_domain_analogies.md`
- `novelty_gate.json`
- `novelty_gate.md`
- `experiments.json`
- `experiments.md`
- `implementation_tasks.md`
- `reviewer_objections.json`
- `reviewer_summaries.json`
- `reviewer_simulation.md`
- `revised_experiment_recommendations.md`
- `orchestrator_plan.json`
- `orchestrator_result.json`
- `run_log.json`
- `rejected_ideas.json`
- `provenance.json`
- `run_report.md`
- `final_report.md`
- `final_report.json` when requested with `gapforge report --format json`

The contract is append-friendly: new skills should add fields deliberately, preserve existing artifacts when possible, and keep generated records linked by IDs.

`run_report.md` is the operational run report produced by the state manager. It is useful for debugging orchestration status and artifact counts.

`final_report.md` is the researcher-facing synthesis produced by `gapforge report` and by the orchestrator's final-report step. It includes the required final sections, cites paper IDs where available, separates evidence-backed claims from hypotheses, includes rejected ideas, and recommends one strongest direction with explicit uncertainty.
