# v0.6 Reproducibility Policy

v0.6 makes reproducibility status explicit for every executed experiment. A result that cannot be rerun may still be useful, but it must not be presented as fully reproducible.

## Required Reproducibility Metadata

Each executed experiment should record:

- run manifest
- command and working directory
- code revision or workspace hash
- environment summary
- dependency lock or environment export when available
- dataset versions and access notes
- random seeds
- configuration files
- metric definitions
- baseline versions
- output artifact paths
- expected rerun command

## Dataset Cards

Dataset cards should include:

- dataset ID and name
- source or generation method
- license/access notes
- version or checksum when available
- splits
- preprocessing
- known limitations
- leakage risks
- whether the dataset is fixture, synthetic, public, private, or placeholder

Placeholder or synthetic fixture data must be labeled clearly and cannot support real empirical claims.

## Baseline Registry

Baseline records should include:

- baseline ID and name
- source paper or implementation reference
- implementation availability
- code URL or local adapter path when available
- why the baseline is required
- risk if omitted
- expected command or module
- limitations

Missing strong baselines should block manuscript-ready status unless a human explicitly waives the issue with a recorded decision.

## Metric Registry

Metric records should include:

- metric ID and name
- definition
- directionality
- applicable task type
- units
- edge cases
- statistical analysis recommendation
- known failure modes

Low false-positive metrics should carry special warnings about confidence intervals, rare-event uncertainty, and denominator size.

## Reproducibility Check Status

Each run should have a reproducibility status:

- `complete`: run metadata, data, config, code, command, and artifacts are sufficient for rerun.
- `partial`: rerun is plausible but one or more pieces are missing or external.
- `not_reproducible`: critical rerun inputs are missing.
- `not_applicable`: planned protocol, scaffold, or smoke-only artifact with no empirical claim.

Reports must show this status near any empirical claim.

## Artifact Hygiene

Experiment workspaces may contain user data, generated outputs, model transcripts, or proprietary code. Default `.gitignore` policy should exclude generated workspaces and large result artifacts unless the user intentionally exports a safe bundle.

Safe bundles should include metadata, redacted summaries, selected plots/tables, and reproducibility notes. They should exclude private datasets, secrets, large raw outputs, and unsafe transcripts by default.

## Commands

```bash
gapforge reproducibility-check --workspace-id <workspace-id>
gapforge reproducibility-check --execution-id <execution-id>
gapforge export-paper-package-v2 --workspace-id <workspace-id>
gapforge audit-artifacts --project-id <project-id>
```

The checker is conservative. Missing dataset cards, missing baselines, missing metric definitions, missing run manifests, missing logs, missing result artifact hashes, or unlabeled fixture/synthetic data should block paper-ready claims even if the command itself ran successfully.

## Paper Package Boundary

Paper package v2 may summarize a result only to the level supported by reproducibility state:

- `pass`: result can be described with its artifacts and remaining limitations.
- `warning`: result can be described, but warnings must be visible next to the claim.
- `fail`: package must describe the run as incomplete, failed, or non-paper-ready.

Reproducibility status is not a positive result. It says whether the result can be audited and rerun, not whether the hypothesis is true.
