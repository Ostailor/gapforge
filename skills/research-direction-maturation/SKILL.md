---
name: research-direction-maturation
description: Use when promoting, evaluating, blocking, or rejecting GapForge research directions across evidence, novelty, protocol, reviewer, and human-review gates.
---

# Research Direction Maturation

## Purpose
Turn ideas into trackable research assets. A direction should mature only when evidence, novelty, coverage, protocols, reviewer checks, and human decisions support it.

## When To Use
- After gap mining and novelty dossiers.
- After project memory sync.
- Before paper package export.
- CLI: `gapforge create-direction`, `gapforge mature-direction`, `gapforge direction-card`.

## Inputs
- project memory
- gaps and hypotheses
- gap evidence matrices
- novelty dossiers
- related-work matrices
- experiment plans/protocols
- reviewer panels
- claim graph and human reviews

## Outputs
- `ResearchDirection`
- `research_directions.json`
- direction cards
- `direction_maturity_report.md`

## Required Artifacts
- project memory files
- linked gap/novelty/experiment artifacts
- `research_directions.json`

## Procedure
1. Create seed directions from gaps or human notes.
2. Candidate requires linked gap, supporting papers, and fake-gap risk.
3. Validated gap requires evidence matrix, counterevidence search, and adequate or human-waived coverage.
4. Experiment-ready requires non-rejected novelty dossier, experiment plan, baselines, metrics, and falsification.
5. Manuscript-ready requires no fatal reviewer issues, related-work matrix, no fatal unresolved claim contradictions, and human approval.
6. Reject directions for duplicates, human rejection, fatal reviewer issue, or supersession.
7. Write/update direction card.

## Citation and Evidence Rules
- Maturity claims must link underlying artifacts.
- Human approval can waive coverage but cannot fabricate support.
- Do not hide counterevidence or rejected status.

## Uncertainty Rules
- Missing evidence lowers maturity.
- Unknown novelty blocks experiment-ready.
- Weak coverage should produce next actions, not recommendation.

## Validation Checklist
- [ ] Direction has maturity, readiness score, blockers, and next actions.
- [ ] Gate failures block maturity.
- [ ] Rejections persist.
- [ ] Direction card cites evidence/paper IDs.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Promoting promising ideas without novelty checks.
- Human approval treated as evidence.
- Manuscript-ready without reviewer/human gates.

## Examples
```bash
gapforge create-direction --project-id PROJECT --gap-id GAP_ID
gapforge mature-direction --project-id PROJECT --direction-id DIRECTION
gapforge direction-card --project-id PROJECT --direction-id DIRECTION
```
