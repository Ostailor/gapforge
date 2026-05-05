# Codex/GPT-5.4 Research Agent Contract

For real GapForge v0.3 runs, Codex using GPT-5.4 is the intended LLM research agent. This document defines how it may assist without weakening GapForge's evidence discipline.

## Role

Codex/GPT-5.4 may assist with:

- full-text-aware paper reading
- gap synthesis
- closest-prior-work comparison
- reviewer simulation
- report critique
- direction maturation review

It must not become an unverified source of citations, results, or novelty claims.

## Required Inputs

Prompts or task context should include:

- topic
- relevant paper IDs and metadata
- parsed sections or excerpted text
- EvidenceSpan locators
- current claims/gaps/novelty dossiers
- source coverage and missing searches
- output schema
- citation/evidence rules
- uncertainty rules

## Output Rules

Codex/GPT-5.4 outputs must:

- use JSON when a schema is required
- cite known paper IDs for source-backed statements
- cite EvidenceSpan locators when using full text
- mark unsupported items as unknown, uncertain, or proposed
- include concise public reasoning summaries only
- avoid hidden chain-of-thought
- preserve missing searches and coverage warnings

## Prohibited Behavior

Codex/GPT-5.4 must not:

- invent citations, DOIs, arXiv IDs, venues, datasets, metrics, quotes, or results
- mark novelty strong without closest prior work
- convert abstract claims into demonstrated results
- hide poor coverage
- remove rejected ideas or human decisions
- store hidden chain-of-thought in GapForge artifacts

## Acceptance Implications

Level 4 canary validation requires actual Codex/GPT-5.4 use. Fake LLM and prompt-pack modes are useful but do not count as actual-run validation.

If Codex/GPT-5.4 is unavailable:

- CI may still pass.
- Level 0 through Level 3 validation may still pass.
- v0.3 cannot claim actual-run validation passed.

## Review Standard

Human reviewers should judge Codex/GPT-5.4 outputs by:

- evidence grounding
- citation honesty
- novelty caution
- usefulness of gaps/directions
- clarity of uncertainty
- quality of reviewer objections
- absence of fabricated results

The model's confidence is not an acceptance criterion. Evidence is.
