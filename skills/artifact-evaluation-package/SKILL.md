---
name: artifact-evaluation-package
description: Use when exporting or checking GapForge v0.8 artifact evaluation packages and badge eligibility.
---

# Artifact Evaluation Package

## Purpose
Prepare reviewer-facing artifact packages from replication and workspace state, with conservative badge claims.

## Inputs
- Manuscript ID, workspace ID, replication package, run manifests, expected outputs, hashes, hardware/time notes, dataset restrictions.

## Outputs
- `artifact_evaluation/<package-id>/artifact_evaluation_package.json`
- artifact evaluation README/instructions
- checklist, badge assessments, smoke dry-run record.

## Procedure
1. Export with `gapforge artifact-eval-package --manuscript-id MANUSCRIPT`.
2. Check with `gapforge artifact-eval-check --package-id PACKAGE`.
3. Assess badges with `gapforge artifact-badges --package-id PACKAGE`.
4. Dry-run commands with `gapforge artifact-eval-smoke --package-id PACKAGE`.
5. Keep package blockers visible in manuscript checklist and dashboard.

## Safety Rules
- Include replication package references and safe files.
- Include install/run instructions, expected outputs, hashes, hardware, and time estimates.
- Exclude restricted/private data by default.
- Badge eligibility must be evidence-based.

## Validation Checklist
- [ ] Replication package ID exists or blocker is explicit.
- [ ] Expected outputs and hashes are present.
- [ ] Restricted data is excluded.
- [ ] Badge blockers are conservative.

## Never Do
Do not claim available, functional, reusable, or reproducible badges without package evidence. Do not include private data by accident.
