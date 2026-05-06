# GapForge v0.5 Roadmap

v0.5 is the real literature campaign quality release. v0.4.1 proved that Codex/GPT-5.4 can move through GapForge's actual-run mechanics: task packs, direct runner, validated import, attestation, human review, and release gate. v0.5 must prove that the system can run useful multi-step campaigns over live literature without exaggerating novelty or hiding weak coverage.

GapForge remains a research ideation aid, not an exhaustive autonomous literature reviewer.

## Why v0.5 Exists

The v0.4.1 accepted real canaries are workflow canaries. They validate that Codex outputs can be produced, checked, imported, attested, and reviewed. They do not prove:

- source connectors are reliable enough for live campaigns
- closest-prior-work recall is strong enough for research recommendations
- generated gaps are meaningful to domain experts
- experiment protocols are ready for implementation
- strict reports refuse weak novelty under realistic source coverage

v0.5 closes that gap by requiring accepted live-literature campaigns and expert review of research quality.

## Must-Have

- Live source reliability checks for arXiv/OpenReview/Semantic Scholar/CrossRef and available field-specific sources.
- Multi-step campaigns that search, triage, download/parse full text where available, build retrieval, read, mine gaps, run novelty loops, build related-work matrices, design protocols, and stop for explicit reasons.
- Source coverage quality scoring against field profiles.
- Closest-prior-work recall proxy measured against human-curated expected prior work.
- Real-paper citation grounding with paper IDs, DOI/arXiv/URL metadata, and EvidenceSpan locators where full text is available.
- Human expert review of campaign reports, novelty dossiers, related-work matrices, and experiment protocols.
- Rejection behavior when novelty is weak, coverage is poor, or closest prior work appears to solve the proposed gap.
- Campaign quality dashboards and release notes that distinguish workflow pass from research-quality pass.
- No unsupported high-confidence claims, fake citations, invented benchmarks, invented results, or exaggerated novelty.

## Should-Have

- Source connector health dashboard with rate-limit/failure classification.
- Query diversification planner that adapts to source policy gaps.
- Improved full-text extraction for references/tables/captions when PDFs are available.
- Better benchmark/baseline extraction from tables and related-work matrices.
- Human review rubrics by field, starting with AI safety, ML, medicine, and economics.
- Per-campaign "missed prior work" postmortem when reviewers identify an obvious omission.
- Campaign replay bundles that exclude PDFs and secrets but preserve auditable metadata.

## Future v0.6

- Multiple expert reviewers per campaign.
- Field-specific source plugins beyond the generic connector set.
- Quantitative comparison against external literature-review baselines.
- Larger multi-agent campaign scheduling.
- Experiment implementation and result ingestion from real benchmark runs.

## Non-Goals

- Do not claim exhaustive literature review.
- Do not require live sources in CI.
- Do not weaken validation to make real runs pass.
- Do not count fixture-only canaries as real literature quality.
- Do not present model-generated novelty as fact without closest prior work.
- Do not treat human attestation as evidence that a research claim is true.

## Deliverables

- v0.5 live-literature campaign profiles.
- v0.5 quality gate evaluator.
- v0.5 live source policy checks.
- v0.5 curated expected-prior-work and expert-review fixtures.
- Release docs that explicitly state whether live-literature campaign quality passed.

## Implemented Workflow Surface

v0.5 work should expose these user-facing paths:

- `gapforge real-campaign-dry-run --profile live_low_fpr_collusion` to preview cost, steps, blockers, and acceptance requirements before spending live-source or Codex budget.
- `gapforge source-health` and `gapforge live-source-diagnostic` to check source reachability and field-policy coverage.
- `gapforge plan-search-strategy`, `execute-search-strategy`, and `search-rounds` to record intentional search rounds.
- `gapforge canonicalize-papers` and `paper-merge-report` to reduce duplicate paper records before novelty comparison.
- `gapforge prior-work-recall` to block strong novelty when required prior-work searches are missing or duplicate prior work is likely.
- `gapforge real-literature-review` and `real-literature-acceptance` to separate workflow acceptance from research-quality acceptance.
- `gapforge v5-release-gate` to enforce live-literature quality requirements.

Programmatic equivalents should live in `src/gapforge/api.py` so notebooks and future UI layers do not shell out to the CLI.
