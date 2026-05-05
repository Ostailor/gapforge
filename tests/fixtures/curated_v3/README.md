# GapForge v0.3 Curated Evaluation Fixtures

This directory contains small, offline v0.3 evaluation fixtures for realistic failure modes in research ideation workflows.

The fixtures are not a benchmark of real scientific quality. They use synthetic real-world-style metadata and short synthetic excerpts so tests can exercise retrieval, prior-work recall, related-work matrices, source coverage policy checks, direction maturity, protocol completeness, manuscript honesty, contradiction detection, and LLM output grounding without live network calls or copyrighted PDFs.

No full papers or downloaded PDFs should be committed here.

## Layout

- `topics/` contains topic-specific curated fixtures.
- `papers/` is reserved for shared safe metadata snippets.
- `annotations/` is reserved for cross-topic human annotation notes.

Each topic includes gold annotations for gaps, closest prior work, related-work relationships, reviewer objections, and not-ready reasons. These annotations are intentionally small and behavior-oriented.
