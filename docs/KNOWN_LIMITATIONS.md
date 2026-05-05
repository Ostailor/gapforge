# Known Limitations

This document records what GapForge does not yet do. Keeping limitations explicit is part of the project contract: reports should help researchers decide what to investigate, not pretend that smoke-test artifacts are literature conclusions.

## v0.1 Limitations

- GapForge v0.1 is deterministic and heuristic.
- Most source records are metadata/abstract-heavy.
- Full-text PDF ingestion is not integrated into the normal workflow.
- Paper notes can mark abstract-only status, but they do not yet use section-level evidence spans.
- The novelty gate is conservative but still mostly lexical and current-run based.
- Cross-domain analogies are generated from deterministic mapping tables, not from adjacent-field evidence searches.
- Source connectors degrade gracefully and may emit deterministic fallback metadata in offline mode.
- Offline/example runs are smoke tests of the system, not real research reviews.
- Evaluation fixtures test useful failure modes, but they are not a benchmark of real research usefulness.
- Reports include uncertainty, but the quality of the recommendation depends on the quality and coverage of the run artifacts.

## What Users Should Not Infer

- Do not infer that GapForge has performed an exhaustive literature review.
- Do not infer that a `pursue` novelty verdict means an idea is definitely novel.
- Do not infer that a generated experiment is paper-ready without manual source review.
- Do not cite fallback fixture papers as real papers.
- Do not treat abstract-only results as full-text evidence.

## v0.2 Limitations

v0.2 reduces some v0.1 risks, but it is still not an exhaustive research system:

- Full-text parsing depends on available PDFs and extractable text.
- PDF downloads can fail because of network access, publisher access rules, malformed files, or missing URLs.
- Section detection is heuristic and may misclassify headings.
- Evidence spans are only as reliable as the parsed text and deterministic extraction rules.
- Citation graph and related-work expansion use available metadata; missing references are not fabricated.
- Novelty dossiers are deterministic and lexical/structured-field based. They are stronger than v0.1 checks but not a substitute for expert prior-work review.
- Cross-domain transfer candidates require evidence to be promoted, but adjacent-field search coverage can still be weak.
- Strict report mode is intentionally conservative and may refuse to recommend useful directions when coverage is incomplete.
- Human review commands preserve corrections, but they do not automatically make unsupported claims true.
- v0.2 eval fixtures are synthetic and useful for regression testing, not proof of real research quality.

## Operational Guidance

- Treat offline v0.2 runs as smoke tests.
- Use `gapforge coverage` before interpreting a report.
- Use `gapforge report --strict` when deciding whether a direction is ready to pursue.
- Add known PDFs manually with `gapforge add-pdf --parse` when source downloads are incomplete.
- Read `novelty_dossiers.md` before treating any idea as novel.
