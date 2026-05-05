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
