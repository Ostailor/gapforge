---
name: figure-table-generation
description: Use when generating GapForge v0.8 manuscript figures or tables from result artifacts.
---

# Figure Table Generation

## Purpose
Generate manuscript assets from recorded result artifacts without inventing values.

## Inputs
- Manuscript ID, workspace execution records, result artifacts, parsed result summaries, run manifests, failed-run records.

## Outputs
- `figures/*.json`, `figures/*.svg`, `figures/*.md`
- `tables/*.json`, `tables/*.md`

## Procedure
1. Run `gapforge manuscript-table --manuscript-id MANUSCRIPT --type result_table` or `baseline_comparison`.
2. Run `gapforge manuscript-figure --manuscript-id MANUSCRIPT --type metric_plot`.
3. Inspect captions for run type and limitations.
4. Use `gapforge manuscript-assets --manuscript-id MANUSCRIPT` to list generated assets.
5. Regenerate assets after result artifacts change.

## Asset Rules
- No result artifact means no result table or metric plot.
- Captions must include run type labels and limitations.
- Smoke/pilot rows are descriptive only.
- Failed runs may appear in appendix/failure tables.
- Custom assets must be labeled and reviewed separately.

## Validation Checklist
- [ ] Source result/artifact IDs are recorded.
- [ ] Captions are conservative.
- [ ] Failed and negative runs are not hidden.
- [ ] No value appears without artifact source.

## Never Do
Do not invent table rows, plot values, confidence intervals, baselines, or benchmark scores.
