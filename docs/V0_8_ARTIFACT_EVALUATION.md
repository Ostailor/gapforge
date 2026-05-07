# GapForge v0.8 Artifact Evaluation

v0.8 artifact evaluation packages should be generated from recorded replication and workspace state. They are reviewer-facing bundles that explain how to inspect, run, and validate artifacts without relying on hidden context or invented claims.

## Package Boundary

An artifact evaluation package is not a substitute for experiments or replication. It packages what exists:

- experiment workspaces
- benchmark workspaces
- replication packages
- dataset cards
- benchmark cards
- environment records
- run manifests
- result artifacts
- result hashes
- analysis scripts
- known failures
- reproducibility checks

If these inputs are incomplete, the package must say so.

## Required Inputs

- manuscript project ID
- experiment workspace IDs
- benchmark workspace IDs
- replication package paths
- dataset cards and access notes
- environment/dependency records
- run manifests and commands
- result artifact manifests and hashes
- expected output manifests
- reproducibility check status
- artifact safety audit
- anonymity/blinding profile when needed

## Required Outputs

Each package should include:

- `ARTIFACT_EVALUATION.md`
- `REPRODUCE.md`
- `MANIFEST.json`
- `ENVIRONMENT.md`
- `DATA.md`
- `EXPECTED_OUTPUTS.json`
- `RESULT_ARTIFACTS.json`
- `KNOWN_FAILURES.md`
- `REVIEWER_CHECKLIST.md`
- anonymized or redacted links when double-blind mode is enabled

## Artifact Evaluation Report

`ARTIFACT_EVALUATION.md` should include:

- paper/manuscript identifier
- artifact availability status
- claimed badges or artifact goals, if the venue uses them
- hardware and software expectations
- expected runtime classes
- data access requirements
- commands to verify core claims
- mapping from paper figures/tables to artifacts
- known nondeterminism
- failed or negative experiment notes
- reproduction status
- reviewer checklist

Do not claim a badge, reproducibility level, or artifact availability state unless the required package evidence exists.

## Data and License Handling

Artifact packages must preserve v0.7 data policies:

- no large auto-downloads without explicit approval metadata
- cache paths and checksums or version IDs are recorded
- redistribution limits are visible
- private data is excluded or represented by access instructions
- fixture or synthetic data is labeled clearly
- unsafe raw artifacts are excluded from public bundles by default

## Reproduction Commands

`REPRODUCE.md` should be generated from run manifests and replication packages. It should include:

- setup steps
- environment notes
- dataset preparation
- command sequence
- expected outputs
- tolerance rules where appropriate
- result parser instructions
- troubleshooting and known-failure notes

Do not invent a command that has no matching manifest, script, or user-provided instruction.

## Figure and Table Mapping

Every paper figure or table should map to:

- manuscript location
- source result artifact IDs
- generation command or script
- benchmark or experiment run IDs
- hash or version metadata
- expected output file
- limitations or caveats

If a figure or table is conceptual rather than result-backed, it must be labeled conceptual and must not imply empirical support.

## Blinding and Public Release

For double-blind submissions, the package should check:

- author names in metadata
- repository names and URLs
- filesystem paths
- acknowledgments
- self-citation phrasing
- commit history exposure
- organization-specific environment paths

Blinding warnings should block submission-ready status when they create material deanonymization risk.

## Suggested Command Surface

```bash
gapforge artifact-eval-package --manuscript-id <manuscript-id>
gapforge artifact-eval-check --package-id <package-id>
gapforge artifact-badges --package-id <package-id>
gapforge artifact-eval-smoke --package-id <package-id>
```

Normal CI should use fixture packages only. It must not require live downloads, LaTeX, GPUs, clusters, or network access.

## Implemented Package Contents

The exporter writes `artifact_evaluation/<package-id>/` under the manuscript root. The package records:

- manuscript and workspace IDs
- replication package ID when available
- copied safe replication files
- install and run instructions
- expected outputs and hashes
- hardware/time estimates
- conservative expected badges
- blockers when replication state is missing or unsafe

Badge assessment is evidence-based. `available`, `functional`, `reusable`, and `reproducible` must remain ineligible when package evidence is absent. Restricted data is excluded by default; reviewers get access instructions rather than private files.

Artifact evaluation supports manuscript readiness only when it is linked back to replication/workspace state. It cannot turn fixture smoke output into a real benchmark or main-result claim.
