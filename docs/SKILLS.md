# Skills

GapForge skills exist in two forms:

- Python implementations under `src/gapforge/skills/`
- Codex-readable skill packages under `skills/*/SKILL.md`

The Python implementations transform `ResearchRunState`. The local skill packages tell Codex how to perform the same research ability safely and consistently.

## Built-In Skills

| Skill | Python module | Codex package | CLI |
| --- | --- | --- | --- |
| Literature Cartographer | `gapforge.skills.literature_cartographer` | `skills/literature-cartographer/` | `gapforge map` |
| Paper Triage | `gapforge.skills.paper_triage` | `skills/paper-triage/` | `gapforge triage` |
| Deep Reading | `gapforge.skills.deep_reading` | `skills/deep-reading/` | `gapforge read` |
| Gap Mining | `gapforge.skills.gap_mining` | `skills/gap-mining/` | `gapforge mine-gaps` |
| Cross-Domain Analogy | `gapforge.skills.cross_domain_analogy` | `skills/cross-domain-analogy/` | `gapforge analogies` |
| Novelty Gate | `gapforge.skills.novelty_gate` | `skills/novelty-gate/` | `gapforge novelty-check` |
| Experiment Designer | `gapforge.skills.experiment_designer` | `skills/experiment-designer/` | `gapforge design-experiments` |
| Reviewer Simulation | `gapforge.skills.reviewer_simulation` | `skills/reviewer-simulation/` | `gapforge review` |

## Shared Rules

- Do not hallucinate citations, results, venues, datasets, or metrics.
- Separate abstract-only notes from full-text notes.
- Use the claim ledger for nontrivial claims.
- Store concise public reasoning summaries, not hidden chain-of-thought.
- Mark uncertainty explicitly.
- Find closest prior work before claiming novelty.
- Prefer decisive experiments over vague ideas.
- Attack ideas before recommending them.

## Skill Package Requirements

Every `skills/*/SKILL.md` must include:

- YAML frontmatter with `name` and `description`
- skill purpose
- when to use it
- inputs and outputs
- required artifacts
- procedure
- quality bar
- failure modes
- validation checklist
- examples with relevant GapForge CLI commands

The orchestrator may run skills more than once during a recursive research loop. Python skills should therefore be idempotent or replace/update their own artifacts by stable IDs.
