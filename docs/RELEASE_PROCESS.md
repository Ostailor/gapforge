# Release Process

GapForge releases should be conservative. A release should document what the system can do, what it cannot do, and which checks passed.

## Pre-Release Checklist

1. Confirm the version in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Update `docs/KNOWN_LIMITATIONS.md`.
4. Confirm README quickstart commands still match the CLI.
5. Run:

```bash
make lint
make test
make eval
make example
```

6. Inspect the example `final_report.md` and confirm it does not present fallback/offline results as real literature conclusions.
7. Commit with a message that records constraints, rejected alternatives if useful, confidence, scope risk, tested commands, and known gaps.
8. Tag the release only after the checks pass.

## Tagging

Use semantic version tags:

```bash
git tag v0.2.0
git push origin main --tags
```

## Release Notes

Release notes should include:

- headline capability changes
- migration notes, if any
- validation commands and results
- known limitations
- whether the default path requires network access or API keys
- whether example outputs are smoke-test artifacts or source-backed conclusions

## Release Boundaries

- Do not tag a release with failing tests, lint, or evals unless the release notes explicitly identify the failure and the release is marked pre-release.
- Do not describe planned features as implemented features.
- Do not claim exhaustive literature review capability.
- Do not publish generated `runs/`, caches, or local environment artifacts as source.
