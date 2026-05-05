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

## v0.2 Skill Behavior

v0.2 keeps deterministic skills as the default but gives them richer state:

- Deep Reading automatically uses `PaperSection` objects when available and falls back to abstract-only notes when not.
- Gap Mining uses `PaperNote`, `EvidenceSpan`, claim ledger, field map, and coverage signals to build `GapEvidenceMatrix` artifacts.
- Cross-Domain Analogy separates query-only analogies from evidence-backed transfer candidates.
- Novelty Gate can run in deep mode and produce closest-prior-work dossiers.
- Experiment Designer skips rejected or human-rejected gaps by default.
- Reviewer Simulation treats unsupported novelty and missing baselines as blocking issues.

Common v0.2 commands:

```bash
gapforge run "topic" --v2 --max-papers 20
gapforge read --run-id <run-id> --fulltext-only
gapforge mine-gaps --run-id <run-id> --min-confidence medium
gapforge analogies --run-id <run-id> --search --promote-evidence-only
gapforge novelty-check --run-id <run-id> --deep
gapforge novelty-dossier --run-id <run-id> --gap-id <gap-id>
gapforge report --run-id <run-id> --strict
```

The skill contract remains the same: do not convert weak coverage into confident claims. If no full-text evidence is available, outputs should say so.

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
