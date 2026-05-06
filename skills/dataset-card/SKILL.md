---
name: dataset-card
description: Use when registering, validating, or documenting datasets for GapForge v0.6 experiment workspaces.
---

# Dataset Card

## Purpose
Make experiment data explicit, licensed, labeled, and auditable before any empirical claim uses it.

## When To Use
- Registering a dataset for an experiment workspace.
- Validating CSV/JSON fixture data.
- Reviewing whether fixture/synthetic/real data is labeled correctly.

## Inputs
- Workspace ID.
- Dataset name, path, type, source, URL, version, license, intended use, limitations, and safety notes.

## Outputs
- `DatasetRecord`
- `DatasetCard`
- `DatasetValidationResult`

## Required Artifacts
- `data/dataset-*.record.json`
- `data/cards/dataset-*.card.md`
- `data/validations/*.validation.md`
- `data/dataset_registry.md`

## Procedure
1. Register with `gapforge dataset-register`.
2. Label type as `real`, `synthetic`, `fixture`, `benchmark`, `generated`, or `unknown`.
3. Render/inspect the dataset card.
4. Validate row/column structure and split integrity.
5. Propagate leakage, privacy, license, and fixture warnings into readiness.

## Validation Checklist
- [ ] Dataset type is explicit.
- [ ] Unknown license creates a warning.
- [ ] Fixture/synthetic/generated data is labeled.
- [ ] Validation records row/column counts and split warnings.
- [ ] Real data is not committed by default.

## Failure Modes
- Treating fixture data as real evidence.
- Hiding unknown license or privacy risk.
- Missing dataset card before execution.

## Examples
```bash
gapforge dataset-register --workspace-id WORKSPACE --name "fixture examples" --path data/fixture.csv --dataset-type fixture --license MIT
gapforge dataset-validate --dataset-id DATASET
gapforge dataset-card --dataset-id DATASET
```

## Evidence Rules
Dataset records describe inputs. They are not result evidence. Empirical claims still require execution and result artifacts.

## Uncertainty Rules
If source, license, version, or leakage status is unknown, keep the warning visible.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not invent dataset provenance, licenses, labels, benchmarks, or performance results.
