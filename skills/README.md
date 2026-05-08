# GapForge Codex Skills

This directory contains Codex-readable skills for GapForge research workflows. Each package is a `SKILL.md` file that future agents can load when performing a specific research ability.

v0.1/v0.2 skills:

- `literature-cartographer`
- `paper-triage`
- `deep-reading`
- `gap-mining`
- `cross-domain-analogy`
- `novelty-gate`
- `experiment-designer`
- `reviewer-simulation`

v0.3 skills:

- `project-memory`
- `hybrid-retrieval`
- `related-work-matrix`
- `research-direction-maturation`
- `manuscript-export`

v0.4 campaign skills:

- `campaign-controller`
- `codex-campaign-task`
- `agent-output-validator`
- `novelty-research-loop`
- `experiment-code-task`
- `campaign-reviewer-panel`
- `real-run-acceptance`

v2.1 selected benchmark skills:

- `selected-idea-project`
- `sequential-specificity-benchmark`
- `trace-generator`
- `sequential-audit-metrics`
- `monitor-baselines`
- `selected-benchmark-review`

Shared rules:

- Do not hallucinate citations, results, venues, datasets, metrics, quotes, or bibliography entries.
- Separate abstract-only notes from full-text notes.
- Use EvidenceSpan locators for full-text evidence.
- Use the claim ledger for nontrivial claims.
- Store concise public reasoning summaries only; never store hidden chain-of-thought.
- Mark uncertainty explicitly.
- Find closest prior work before claiming novelty.
- Preserve rejected ideas and human decisions.
- Prefer decisive experiments over vague ideas.
- Attack ideas before recommending them.
- Distinguish deterministic, fake-agent, task-pack/manual-handoff, and direct Codex modes.
- Never count fake-agent outputs as actual Codex/GPT-5.4 acceptance.
- Never import agent output before validation.
- For v2.1, remember: synthetic smoke benchmark is not a final research result; low-FPR claims require power; every result claim must be artifact-backed; no fake results.
