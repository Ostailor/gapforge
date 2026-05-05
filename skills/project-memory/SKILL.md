---
name: project-memory
description: Use when carrying papers, claims, rejected ideas, human decisions, and research directions across multiple GapForge runs in one project.
---

# Project Memory

## Purpose
Maintain durable project-level memory across runs without treating old conclusions as newly verified evidence.

## When To Use
- When several topics belong to one research program.
- When rejected ideas or human decisions must survive new runs.
- CLI: `gapforge init-project`, `gapforge attach-run`, `gapforge sync-project-memory`, `gapforge project-report`.

## Inputs
- one or more `ResearchRunState` objects
- papers, claims, gaps, rejected ideas, human reviews, novelty dossiers, experiments
- optional project notes and tags

## Outputs
- `ResearchProgramState`
- `project.json`
- `topics.json`
- `corpus_papers.json`
- `memory_records.json`
- `research_directions.json`
- `project_report.md`

## Required Artifacts
- `projects/<project-id>/project.json`
- attached run pointers under `projects/<project-id>/runs/`
- synced memory JSON files

## Procedure
1. Create or load the project.
2. Attach run IDs explicitly.
3. Deduplicate papers by DOI, arXiv ID, exact/high-similarity title, and source IDs.
4. Sync claims, gaps, rejected ideas, experiments, reviewer objections, and human decisions into memory records.
5. Preserve provenance and linked run/object IDs.
6. Create or update research directions from gaps without losing maturity state.
7. Write project report.

## Citation and Evidence Rules
- Project memory does not create new evidence.
- Carry paper IDs, evidence span IDs, claim IDs, and run IDs forward.
- Do not merge claims when meaning differs materially.
- Do not resurrect rejected ideas as active without explicit human revision.

## Uncertainty Rules
- Mark stale, contested, or unsupported memory as such.
- Treat cross-run duplicates as linked records unless confident enough to merge.

## Validation Checklist
- [ ] Project files exist.
- [ ] Attached run IDs are preserved.
- [ ] Corpus papers are deduplicated.
- [ ] Rejected ideas and human decisions persist.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Treating project memory as fresh evidence.
- Dropping provenance during deduplication.
- Losing human locks/rejections.
- Over-merging near-duplicate claims.

## Examples
```bash
gapforge init-project "monitoring collusion research"
gapforge run "low false positive collusion detection" --v3 --project-id monitoring-collusion-research
gapforge sync-project-memory --project-id monitoring-collusion-research
gapforge project-report --project-id monitoring-collusion-research
```
