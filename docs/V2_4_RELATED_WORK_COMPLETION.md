# GapForge v2.4 Related-Work Completion

v2.4 exists because v2.3 completed the synthetic main benchmark but failed the publication path on real related work. The v2.3 fatal blocker was simple: no required related-work category had real attached paper records.

This document defines how v2.4 completes that blocker. It does not itself attach papers, cite papers, or claim that a category is complete.

## Core Rule

A category is complete only when real, inspectable paper records are attached and reviewed. Fallback records, fixture records, search queries, generated citation text, and uncited prose do not count.

Publication readiness is blocked while any required category is fallback-only or `incomplete_blocker`.

## Required Categories

| Category | Required v2.4 Treatment |
| --- | --- |
| Low-FPR detection and evaluation | Attach real records about detector evaluation under low false-positive or high-specificity constraints. |
| Multi-agent collusion or covert coordination | Attach real records about collusion, covert coordination, cooperative misuse, or multi-agent coordination threats. |
| Monitor evasion | Attach real records about evading monitors, auditors, classifiers, filters, or safety systems. |
| Sequential testing or change-point detection | Attach real records about repeated looks, alpha spending, sequential testing, change-point detection, or online monitoring. |
| Benchmark or evaluation protocol papers | Attach real records about benchmark construction, evaluation validity, contamination, protocol design, or artifact reporting. |
| Anomaly detection specificity | Attach real records about specificity, false-alarm control, calibration, anomaly detector evaluation, or rare-event evaluation. |
| Medical screening specificity analogies, if used | Attach real records only if the manuscript uses screening-test analogies. Otherwise mark `dropped_not_used`. |
| Cartel or covert-channel analogies, if used | Attach real records only if the manuscript uses cartel or covert-channel analogies. Otherwise mark `dropped_not_used`. |

Optional analogy categories cannot remain half-used. They must be complete with records or removed from manuscript arguments.

## Paper Record Requirements

Each real paper record must include:

- `record_id`
- stable title
- author list or source-provided author string
- year
- venue, publisher, preprint server, or source when available
- DOI, arXiv ID, ACL Anthology ID, PubMed ID, URL, or other stable identifier
- source used to retrieve the record
- retrieval date
- abstract, summary source, or full-text availability status when available
- assigned categories
- inclusion reason
- exclusion reason if rejected
- relevance note
- novelty-risk note
- benchmark or baseline implication
- manuscript section target
- reviewer status

Records with missing stable identifiers may be accepted only if a reviewer marks them traceable from a reputable source. Fabricated metadata is a fatal blocker.

## Search Campaign Requirements

Each required category must have a recorded search campaign with:

- category name
- search date
- source connectors or databases used
- exact queries
- filters and date limits
- result counts when available
- included records
- excluded records with reasons
- deduplication method
- unavailable, paywalled, or failed retrievals
- missed-search risks
- reviewer notes
- next-search recommendations

At least one targeted query set is required per category. Broad searches may supplement but cannot replace category-specific recall.

## Category Status Values

Every category must end with one status:

- `complete`: sufficient real records and reviewer acceptance for the current manuscript scope.
- `complete_with_warning`: real records attached, but coverage or relevance remains limited and claims are narrowed.
- `dropped_not_used`: optional analogy is removed from the manuscript and does not support any claim.
- `incomplete_blocker`: real records are missing, fake, fallback-only, inaccessible without review, or too weak for the claim.
- `impossible_after_recorded_search`: targeted searches were recorded, but no usable records could be attached; publication readiness remains blocked unless the manuscript drops the dependent claim.

`impossible_after_recorded_search` is not a publication-readiness pass. It is an honest no-go or revise input.

## Related-Work Matrix Fields

The v2.4 matrix must include one row per attached paper record:

- `record_id`
- `category`
- `source_identifier`
- `claim_supported_or_challenged`
- `benchmark_relevance`
- `low_fpr_or_specificity_relevance`
- `sequential_relevance`
- `baseline_relevance`
- `monitor_evasion_relevance`
- `threat_model_relevance`
- `dataset_or_protocol_relevance`
- `closest_prior_work_status`
- `novelty_risk`
- `contribution_claim_effect`
- `manuscript_section`
- `review_status`

The matrix must also expose category-level status, missing-search risks, and any claim-language changes.

## Closest-Prior-Work Dossier

v2.4 must refresh the closest-prior-work dossier after records are attached. The dossier must rank candidate prior work by threat to the contribution claim:

- `direct_prior`: appears to cover the same benchmark, protocol, or claim.
- `near_prior`: covers a related protocol, metric, dataset, or threat model.
- `component_prior`: covers one important component, such as sequential testing, specificity, monitor evasion, or baseline design.
- `analogy_prior`: useful analogy but not direct technical prior work.
- `not_prior`: reviewed and found not relevant enough to threaten the claim.

For every `direct_prior`, `near_prior`, or `component_prior`, the dossier must state whether the manuscript response is:

- cite and position against it
- soften contribution claim
- add or justify baseline
- add limitation
- revise benchmark protocol
- no-go novelty claim

## Benchmark Positioning Linkage

Each category must say whether it affects benchmark positioning:

- benchmark design precedent
- evaluation protocol precedent
- low-FPR metric precedent
- specificity or false-alarm precedent
- sequential correction precedent
- collusion or covert-coordination threat precedent
- monitor-evasion threat precedent
- no benchmark-positioning implication

The manuscript must not present the v2.3 synthetic benchmark as uniquely novel without comparing against attached prior benchmarks or protocols.

## Anti-Fabrication Rules

v2.4 must not:

- invent citations, DOIs, arXiv IDs, venues, author lists, or BibTeX keys
- convert search queries into citations
- count fallback or fixture records as real coverage
- hide closest prior work that weakens novelty
- claim exhaustive search
- use optional analogies without attached records
- mark a category complete because no paper was found
- let publication readiness pass with unresolved fake-citation findings

## Completion Output

The related-work completion report must end with one of:

- `related_work_complete`: required categories have accepted real records and matrix implications.
- `related_work_complete_with_warnings`: real records exist, but claims are visibly narrowed.
- `related_work_incomplete_revise`: records or implications are incomplete, but the benchmark may be revised.
- `related_work_incomplete_no_go`: missing, fake, fallback-only, or novelty-breaking records block publication claims.

Only the first two outcomes may feed a publication-readiness pass, and only if novelty, manuscript, citation, and reviewer gates also pass.
