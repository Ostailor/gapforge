---
name: venue-style-analysis
description: Use when applying v2.5 venue profiles, style-corpus analysis, or venue-aware manuscript rewriting.
---

# Venue Style Analysis

## Purpose

Shape a v2.5 manuscript toward a venue profile using structural and rhetorical patterns, without copying source-paper expression or weakening evidence gates.

## Command Path

```bash
gapforge venue-profile-list
gapforge manuscript-set-venue-profile --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge style-corpus-add-tex --path <allowed-fixture.tex> --venue generic_ml_conference
gapforge venue-style-analyze --venue generic_ml_conference
gapforge venue-style-recommend --manuscript-id <manuscript-id>
gapforge manuscript-rewrite-for-venue --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge manuscript-style-report --manuscript-id <manuscript-id>
```

## API Path

```python
from gapforge import api

api.select_venue_profile(manuscript_id, "generic_ml_conference")
api.ingest_style_corpus(tex_path, venue="generic_ml_conference")
profile = api.analyze_venue_style("generic_ml_conference")
rewrite = api.rewrite_manuscript_for_venue(manuscript_id, "generic_ml_conference")
```

## Discipline Rules

- Use TeX/source only when allowed, and extract structure/style features only.
- Do not copy prose, captions, equations, distinctive macros, or reviewer-response phrasing.
- Venue profile guides structure and reviewer expectations; it never implies acceptance.
- Do not add unsupported claims or remove limitations.
- Evidence discipline applies: copied prose, missing required sections, no fake citation, fake result, fake review, and traceability blockers remain blockers.
