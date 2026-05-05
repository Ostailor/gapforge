# GapForge Architecture

GapForge is a skills-based research ideation OS, not a rigid one-pass pipeline.

The current foundation has four layers:

1. **Orchestrator** in `src/gapforge/orchestrator.py`
   - Coordinates research as a resumable loop rather than a single pipeline.
   - Persists an `OrchestratorPlan`, per-step statuses, an `OrchestratorResult`, and a run log after every stage.
   - Supports `gapforge run`, `gapforge resume`, and `gapforge status`.
   - Source failures are logged and isolated so one connector failure does not kill the run.
   - Analogy-generated search queries can add papers, then refresh mapping, triage, reading, and gap mining before novelty checks.

2. **Sources** in `src/gapforge/sources/`
   - Implement a common `ResearchSource.search(query, *, max_results, sort, date_from, date_to)` interface.
   - Networked connectors use cached HTTP with timeouts, retries, and graceful degradation.
   - See `docs/SOURCES.md` for the current connector contract and extension guide.

3. **Skills** in `src/gapforge/skills/`
   - Each skill receives and returns `ResearchRunState`.
   - Skills are composable and registered in `SkillRegistry`.
   - The initial order is literature mapping, triage, deep reading, gap mining, analogy, novelty gate, experiment design, and reviewer simulation.
   - The literature cartographer is deterministic today: it uses keyword/metadata heuristics and writes uncertainty-aware claims. A future LLM implementation should keep the same `FieldMap` interface.
   - The novelty gate is deliberately adversarial: it searches the current paper store first, records closest-prior-work comparisons, rejects duplicate ideas, and leaves missing searches explicit instead of upgrading uncertain ideas.
   - The experiment designer consumes novelty assessments and skips rejected ideas by default. Its output is scoped around falsifiable experiments, baseline strength, implementation steps, and reviewer-facing decisive results.
   - The reviewer simulation attacks experiments from technical, novelty, empirical-rigor, and area-chair perspectives, then converts objections into blocking issues, required fixes, and submission readiness recommendations.

4. **Persistent state** in `runs/<timestamp-topic>/`
   - Every run writes JSON artifacts and a Markdown report.
   - State remains inspectable and testable outside the CLI process.
   - The state manager writes `run_report.md` for operational status. The reporting layer writes `final_report.md` or `final_report.json` for researcher-facing synthesis.

5. **Evaluation harness** in `src/gapforge/evals/`
   - Provides a small benchmark API and metrics model.
   - Future evaluators should test provenance coverage, novelty quality, and experiment readiness.

The CLI in `src/gapforge/cli.py` is intentionally thin. It delegates behavior to `Orchestrator`, which keeps command handling separate from research logic.

## Final Reporting

`src/gapforge/reporting.py` builds a structured report dictionary and renders Markdown or JSON from the same data. The report ranks a single strongest direction from gaps, novelty assessments, experiments, and reviewer objections. It deliberately uses conservative language: `pursue` is not proof of novelty, missing searches remain visible, and rejected ideas are included instead of silently discarded.
