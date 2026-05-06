---
name: paper-package-v2
description: Use when exporting or reviewing GapForge v0.6 empirical paper packages from experiment workspaces or directions.
---

# Paper Package V2

## Purpose
Export an honest empirical writing package that separates planned work, smoke/pilot/main results, failed runs, negative results, and hypothetical expected results.

## When To Use
- After an experiment workspace has protocol, registries, execution records, analysis, reproducibility check, and empirical review.
- When a direction needs a planned-only package with missing requirements visible.

## Inputs
- Workspace ID or direction ID.
- Research direction, literature basis, novelty dossier, protocol, datasets, baselines, metrics, execution records, result summaries, analysis, reproducibility, reviewer panel.

## Outputs
- `PaperPackage`
- `paper_package_v2/` Markdown and JSON files

## Required Artifacts
- `paper_package_v2/README.md`
- `result_summary.md`
- `statistical_analysis.md`
- `reproducibility_check.md`
- `negative_results.md`
- `reviewer_panel.md`
- `paper_package.json`

## Procedure
1. Export with `gapforge export-paper-package-v2`.
2. Confirm package labels planned, smoke, pilot, main, failed, negative, and hypothetical sections.
3. Confirm empirical claims appear only when result artifacts exist.
4. Confirm failed/negative runs and limitations are visible.
5. Block paper-ready claims when reproducibility or empirical review fails.

## Validation Checklist
- [ ] Expected results are labeled hypothetical.
- [ ] Smoke outputs are labeled smoke.
- [ ] Failed/negative runs are included.
- [ ] Result claims link to metric artifacts.
- [ ] Missing requirements are listed.

## Failure Modes
- Planned-only package reads like observed results.
- Smoke result is described as empirical success.
- Failed run omitted from limitations.
- Fake result appears in results section.

## Examples
```bash
gapforge export-paper-package-v2 --workspace-id WORKSPACE
gapforge export-paper-package-v2 --direction-id DIRECTION
```

## Evidence Rules
Paper package result claims require execution IDs, result artifact IDs, metric result IDs, and analysis/reproducibility context.

## Uncertainty Rules
If evidence is incomplete, mark planned, incomplete, failed, negative, or hypothetical.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not write fake observed results, tables, plots, p-values, citations, or rebuttal evidence.
