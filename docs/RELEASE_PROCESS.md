# Release Process

GapForge releases should be conservative. A release should document what the system can do, what it cannot do, and which checks passed.

## Pre-Release Checklist

1. Confirm the version in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. Update `docs/KNOWN_LIMITATIONS.md`.
4. Confirm README quickstart commands still match the CLI.
5. Run automated validation:

```bash
make ci
```

6. Run or review offline smoke validation:

```bash
GAPFORGE_DISABLE_NETWORK=1 gapforge run "low false positive collusion detection" --v3 --max-papers 8 --build-index
GAPFORGE_DISABLE_NETWORK=1 gapforge report --strict
```

7. Inspect `final_report.md` and confirm it does not present fallback/offline results as real literature conclusions.
8. For v0.3 releases, write `docs/releases/v0.3.0-real-run-acceptance.md` with machine-readable release-gate front matter.
9. For v0.3 releases that claim actual-run validation, complete the real-run canary process in `docs/V0_3_REAL_RUN_ACCEPTANCE.md` and `docs/V0_3_CANARY_RUNS.md`.
10. Confirm at least one actual Codex/GPT-5.4 canary has an accepted canary record before using the phrase "actual-run acceptance passed."
11. Record human review using `docs/REAL_RUN_REVIEW_CHECKLIST.md`.
12. Commit with a message that records constraints, rejected alternatives if useful, confidence, scope risk, tested commands, and known gaps.
13. Tag the release only after the checks pass.

## v0.3 Validation Levels

- Level 0: deterministic unit tests, no LLM, CI.
- Level 1: offline smoke tests, no LLM, no network.
- Level 2: fake LLM tests for JSON guards and evidence gates.
- Level 3: prompt-pack dry runs for Codex/GPT-5.4 prompt readiness.
- Level 4: actual Codex/GPT-5.4 canary runs, manual/private.
- Level 5: human-reviewed acceptance with recorded review decisions.

CI must not require Codex/GPT-5.4. Actual-run validation is required for a v0.3 release to claim actual-run readiness, but it is not part of normal automated tests.

If Codex/GPT-5.4 is unavailable, the release cannot claim actual-run validation passed. Never fake a canary pass.

For v0.3, actual-run validation requires an accepted canary record. A failed, rejected, planned, prompt-pack-only, or fake-agent canary is not sufficient.

For future v0.4 releases, require multiple accepted agentic campaigns, not a single skill-level canary. Those campaigns should cover literature search/reading, novelty, experiment planning, reviewer/rebuttal planning, and manuscript package review.

## Tagging

Use semantic version tags:

```bash
git tag v0.3.0
git push origin main --tags
```

## Release Notes

Release notes should include:

- headline capability changes
- migration notes, if any
- validation commands and results
- validation level status, including whether Level 4 and Level 5 passed, failed, or were not run
- known limitations
- whether the default path requires network access or API keys
- whether example outputs are smoke-test artifacts or source-backed conclusions

## Release Boundaries

- Do not tag a release with failing tests, lint, or evals unless the release notes explicitly identify the failure and the release is marked pre-release.
- Do not describe planned features as implemented features.
- Do not claim exhaustive literature review capability.
- Do not claim actual Codex/GPT-5.4 canary validation unless the canary ran and human review was recorded.
- Do not claim actual-run acceptance unless the release-gate front matter says `actual_run_acceptance_passed: true` and at least one real canary is accepted.
- Do not publish generated `runs/`, caches, or local environment artifacts as source.
