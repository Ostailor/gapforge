# v2 Low-FPR Collusion Idea Pilot

This pilot checks whether GapForge v2 behaves like an Idea Discovery Engine on:

> low false-positive collusion detection in LLM multi-agent systems

The pilot is intentionally stricter than v0.9. A refusal is not enough unless GapForge first performs active idea discovery, mutation, constructive gap creation, cross-domain transfer, Codex/GPT-5.4 task-pack generation, novelty checking, and tournament selection.

## Commands

```bash
gapforge v2-pilot-run --name low_fpr_collusion
gapforge v2-pilot-status --name low_fpr_collusion
gapforge v2-pilot-report --name low_fpr_collusion
```

## Workflow

The runner must create and persist:

1. topic portfolio
2. idea bank
3. mutation report from weak or rejected ideas
4. constructive gap report
5. cross-domain transfer report
6. Codex/GPT-5.4 idea synthesis task packs
7. idea novelty and counterevidence report
8. idea tournament report
9. selected candidate or research agenda
10. human review acceptance for the selected candidate or agenda

## Outcome Policy

Passing outcomes are:

- `defensible_direction`: one specific idea candidate is human-accepted as a candidate after evidence and novelty gates remain visible.
- `correct_refusal`: no idea survives active search and tournament, so a research agenda is human-accepted as an honest blocker.

For the v2 release, the preferred outcome is an accepted candidate idea. If only an agenda is accepted, release notes must not claim v2 achieved idea discovery; they should document blockers and plan v2.0.1 or v2.1.

## Non-Claims

The pilot does not claim manuscript readiness, empirical results, or publication novelty. It only tests whether v2 actively searches for a defensible idea and refuses honestly when it cannot find one.
