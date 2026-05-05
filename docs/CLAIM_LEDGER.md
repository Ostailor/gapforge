# Claim Ledger

The claim ledger is GapForge's belief accounting system. It records what the system believes, why it believes it, what contradicts it, and what still needs verification.

## Philosophy

Research ideation fails when summaries blur claims, evidence, hypotheses, and speculation. GapForge keeps those separate:

- a paper claim is not automatically a demonstrated result
- an abstract-only note is not full-text evidence
- a gap is not novelty
- a model suggestion is not a citation
- a project-memory record is not newly verified evidence

Every nontrivial statement should be traceable to papers, evidence spans, human decisions, or explicit uncertainty.

## Claim Fields

Claims include:

- `id`
- `text`
- `type`: background, method, novelty, gap, result, limitation, analogy
- `status`: unsupported, supported, contested, uncertain, falsified
- `confidence`: low, medium, high
- supporting evidence
- counterevidence
- source paper IDs
- creating skill
- verification flag
- notes
- provenance

## Evidence

Evidence can be metadata, abstract snippets, full-text `EvidenceSpan` locators, manual evidence, or human review notes. Full-text evidence should include page, section, character offset, and locator when available.

Supported claims require evidence. High-confidence full-text claims should use EvidenceSpan-backed evidence.

## Counterevidence

Counterevidence is first-class. A claim can be supported and contested at the same time when different papers disagree. v0.3 project claim graphs preserve contradictions across runs rather than hiding them.

Commands:

```bash
gapforge annotate-claim --run-id <run-id> --claim-id <claim-id> --note "..."
gapforge mark-claim --run-id <run-id> --claim-id <claim-id> --status contested
gapforge add-evidence --run-id <run-id> --claim-id <claim-id> --paper-id <paper-id> --quote "..." --locator "p5"
gapforge build-claim-graph --project-id <project-id>
gapforge contradictions --project-id <project-id>
```

## Public Reasoning Summaries

Persisted provenance may include concise public reasoning summaries such as "identified repeated limitation across two notes." It must not include hidden chain-of-thought or private scratchpad reasoning.

## Validation Rules

Validation catches:

- supported claims without evidence
- high-confidence full-text claims without evidence spans
- novelty claims without closest prior work
- paper notes without paper IDs
- evidence spans linked to unknown papers/sections
- gaps without supporting papers or explicit indirect-evidence reasons
- experiments without hypotheses or novelty assessment
- human-rejected objects reused without override

Run:

```bash
gapforge validate-state
```

## Project Claim Graph

v0.3 syncs run-level claims into a project-level claim graph:

- duplicate claims can merge
- claims can support, contradict, refine, supersede, or depend on one another
- unresolved contradictions appear in project reports
- human resolutions are auditable

Project graph outputs do not override source evidence; they help researchers see cumulative beliefs and conflicts across runs.
