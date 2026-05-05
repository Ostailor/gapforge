# GapForge Codex Skills

This directory contains Codex-readable skill packages for GapForge research workflows. Each skill mirrors a Python implementation under `src/gapforge/skills/` and provides operational instructions for agents working with the repository.

Available skills:

- `literature-cartographer`: map papers into clusters, methods, assumptions, and underexplored areas.
- `paper-triage`: rank papers into reading-depth tiers.
- `deep-reading`: create grounded paper notes and source-linked claims.
- `gap-mining`: identify evidence-backed research gaps.
- `cross-domain-analogy`: generate skeptical adjacent-field analogies and search queries.
- `novelty-gate`: check closest prior work before claiming novelty.
- `experiment-designer`: create falsifiable experiment plans.
- `reviewer-simulation`: attack experiments before recommending them.

Shared rules:

- Do not hallucinate citations, results, venues, datasets, or metrics.
- Separate abstract-only notes from full-text notes.
- Use the claim ledger for nontrivial claims.
- Store concise public reasoning summaries, not hidden chain-of-thought.
- Mark uncertainty explicitly.
- Find closest prior work before claiming novelty.
- Prefer decisive experiments over vague ideas.
- Attack ideas before recommending them.
