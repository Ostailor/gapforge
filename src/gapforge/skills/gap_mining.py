"""Mine research gaps from repeated literature patterns."""

from __future__ import annotations

import re
from collections import Counter

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import (
    Claim,
    Evidence,
    EvidenceSpan,
    Gap,
    GapEvidenceMatrix,
    GapEvidenceRow,
    PaperNote,
    PaperSection,
    Provenance,
    ResearchRunState,
)
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.review.audit import locked_object_ids
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso

GAP_TYPES = {
    "benchmark gap",
    "evaluation gap",
    "assumption gap",
    "theory gap",
    "deployment gap",
    "negative-result gap",
    "cross-domain gap",
    "measurement gap",
    "reproducibility gap",
    "scalability gap",
}


class GapMining(Skill):
    name = "gap-mining"

    def run(self, state: ResearchRunState, *, force: bool = False) -> ResearchRunState:
        gaps = self.mine_gaps(state)
        matrices = self.build_evidence_matrices(state, gaps)
        _apply_matrix_confidence(state, gaps, matrices)
        if not force:
            gaps, matrices = _preserve_locked_gaps(state, gaps, matrices)
        state.gaps = gaps
        state.gap_evidence_matrices = matrices
        state.claims = self._add_gap_claims(state, gaps).claims
        self.mark_complete(state)
        return state

    def run_filtered(
        self,
        state: ResearchRunState,
        *,
        min_confidence: str = "low",
        include_low_confidence: bool = True,
        force: bool = False,
    ) -> ResearchRunState:
        self.run(state, force=force)
        threshold = "low" if include_low_confidence else min_confidence
        allowed = _filter_by_confidence(state.gaps, threshold)
        allowed_ids = {gap.id for gap in allowed}
        if not force:
            locked_ids = locked_object_ids(state, "gap")
            locked = [gap for gap in state.gaps if gap.id in locked_ids and gap.id not in allowed_ids]
            allowed.extend(locked)
            allowed_ids |= {gap.id for gap in locked}
        state.gaps = allowed
        state.gap_evidence_matrices = [matrix for matrix in state.gap_evidence_matrices if matrix.gap_id in allowed_ids]
        return state

    def mine_gaps(self, state: ResearchRunState) -> list[Gap]:
        notes = state.paper_notes
        claims = state.claims
        field_map = state.field_map
        gaps: list[Gap] = []

        gaps.extend(self._repeated_limitation_gaps(state, notes, claims))
        gaps.extend(self._missing_metric_gaps(state, notes, claims))
        gaps.extend(self._missing_dataset_gaps(state, notes, claims))
        gaps.extend(self._assumption_gaps(state, notes, claims))
        gaps.extend(self._full_text_evidence_gaps(state, notes, claims))
        gaps.extend(self._contradiction_gaps(state, claims))
        gaps.extend(self._cross_domain_gaps(state, claims))

        if field_map is not None and _adjacent_field_sources_searched(state):
            for candidate in field_map.initial_gap_candidates[:3]:
                gaps.append(
                    self._make_gap(
                        state=state,
                        gap_type="cross-domain gap",
                        title=f"Field-map candidate: {candidate}",
                        description=f"The field map suggests a possible imported-method or adjacent-field gap: {candidate}",
                        notes=notes[:3],
                        claims=claims,
                        reason="This is indirect evidence from field-map structure, not direct paper proof.",
                        risk="The field-map heuristic may be missing papers where this direction has already been tried.",
                        confidence="low",
                        novelty_status="unchecked",
                    )
                )

        return _dedupe_gaps(gaps)

    def build_evidence_matrices(self, state: ResearchRunState, gaps: list[Gap]) -> list[GapEvidenceMatrix]:
        return [_build_gap_evidence_matrix(state, gap) for gap in gaps]

    def _repeated_limitation_gaps(self, state: ResearchRunState, notes: list[PaperNote], claims: list[Claim]) -> list[Gap]:
        buckets = {
            "deployment gap": ["deployment", "shift", "real-world", "real world", "external validity"],
            "scalability gap": ["scalability", "scale", "large-scale", "latency"],
            "reproducibility gap": ["reproduc", "code", "replication", "implementation"],
            "negative-result gap": ["negative result", "failure", "fails", "did not", "cannot"],
        }
        gaps = []
        for gap_type, terms in buckets.items():
            matched = _notes_matching(notes, terms, include_unstated=True)
            if len(matched) >= 2:
                gaps.append(
                    self._make_gap(
                        state=state,
                        gap_type=gap_type,
                        title=f"Repeated {gap_type.replace(' gap', '')} limitations",
                        description=f"Multiple notes mention {gap_type.replace(' gap', '')} limitations or unresolved conditions.",
                        notes=matched,
                        claims=_claims_matching(claims, terms),
                        reason="Existing papers surface the concern but do not jointly resolve it across the mapped evidence.",
                        risk="The gap may be fake if a specialized subliterature outside the current run already resolves it.",
                        confidence="medium" if len(matched) >= 3 else "low",
                        novelty_status="unchecked",
                    )
                )
        return gaps

    def _missing_metric_gaps(self, state: ResearchRunState, notes: list[PaperNote], claims: list[Claim]) -> list[Gap]:
        gaps = []
        false_positive_missing = [note for note in notes if not _has_any(note.metrics, ["false positive", "false-positive", "specificity"])]
        if len(false_positive_missing) >= max(2, len(notes) // 2):
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="measurement gap",
                    title="False-positive measurement is missing or inconsistent",
                    description="Many selected papers do not expose false-positive-specific metrics in the available notes.",
                    notes=false_positive_missing,
                    claims=_claims_matching(claims, ["false positive", "metric", "measurement"]),
                    reason=(
                        "Without explicit false-positive metrics, existing work cannot fully answer low-false-positive research questions."
                    ),
                    risk="The full text may contain these metrics even when abstracts or structured notes do not.",
                    confidence="medium" if len(false_positive_missing) >= 3 else "low",
                    novelty_status="weak",
                )
            )
        metric_sparse = [note for note in notes if not note.metrics]
        if len(metric_sparse) >= 2:
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="evaluation gap",
                    title="Evaluation metrics are underspecified",
                    description="Several notes lack visible metric definitions, making evaluation comparisons hard to audit.",
                    notes=metric_sparse,
                    claims=_claims_matching(claims, ["evaluation", "metric"]),
                    reason="Existing work cannot be reliably compared without explicit metrics.",
                    risk="The available notes may be abstract-only and therefore omit metrics present in full text.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        return gaps

    def _missing_dataset_gaps(self, state: ResearchRunState, notes: list[PaperNote], claims: list[Claim]) -> list[Gap]:
        gaps = []
        dataset_sparse = [note for note in notes if not note.datasets]
        synthetic_only = [note for note in notes if note.datasets and all("synthetic" in item for item in note.datasets)]
        if len(dataset_sparse) >= 2:
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="benchmark gap",
                    title="Benchmark and dataset evidence is incomplete",
                    description="Several notes do not identify concrete datasets or benchmark conditions.",
                    notes=dataset_sparse,
                    claims=_claims_matching(claims, ["dataset", "benchmark"]),
                    reason="Existing work cannot establish benchmark realism if datasets are absent or unspecified.",
                    risk="Dataset details may exist in full text or appendices not available to the deterministic reader.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        if len(synthetic_only) >= 2:
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="deployment gap",
                    title="Synthetic benchmarks may not represent deployment settings",
                    description="Multiple notes indicate synthetic-only dataset evidence.",
                    notes=synthetic_only,
                    claims=_claims_matching(claims, ["synthetic", "deployment", "real-world"]),
                    reason="Synthetic settings do not by themselves solve deployment transfer or realism.",
                    risk="The papers may include real-world validation outside the currently extracted note fields.",
                    confidence="medium" if len(synthetic_only) >= 3 else "low",
                    novelty_status="weak",
                )
            )
        return gaps

    def _assumption_gaps(self, state: ResearchRunState, notes: list[PaperNote], claims: list[Claim]) -> list[Gap]:
        assumption_counts = Counter(assumption for note in notes for assumption in note.assumptions)
        gaps = []
        for assumption, count in assumption_counts.items():
            if count < 2:
                continue
            matched = [note for note in notes if assumption in note.assumptions]
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="assumption gap",
                    title=f"Shared assumption: {assumption[:70]}",
                    description=f"{count} notes share an assumption that may not hold across the user topic.",
                    notes=matched,
                    claims=_claims_matching(claims, [assumption[:25]]),
                    reason="Existing work may depend on the assumption without testing its boundary conditions.",
                    risk="The assumption may be reasonable or tested in full text that was not available.",
                    confidence="medium" if count >= 3 else "low",
                    novelty_status="unchecked",
                )
            )
        return gaps

    def _full_text_evidence_gaps(self, state: ResearchRunState, notes: list[PaperNote], claims: list[Claim]) -> list[Gap]:
        gaps = []
        span_paper_ids = {span.paper_id for span in state.evidence_spans}
        full_text_paper_ids = {section.paper_id for section in state.paper_sections if section.text.strip()}
        claimed_results_without_spans = [
            note
            for note in notes
            if (note.main_results or note.metrics) and note.paper_id in full_text_paper_ids and note.paper_id not in span_paper_ids
        ]
        if len(claimed_results_without_spans) >= 2:
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="reproducibility gap",
                    title="Claimed metrics or results lack locator-backed evidence",
                    description=(
                        "Several full-text-aware notes mention metrics or results, but no page or section-level evidence span "
                        "anchors those claims."
                    ),
                    notes=claimed_results_without_spans,
                    claims=_claims_matching(claims, ["result", "metric", "evidence"]),
                    reason="Existing notes cannot support audit-ready comparison without evidence spans for the claimed metrics/results.",
                    risk="The evidence may exist in the paper text but the parser or reader did not capture the relevant span.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        missing_full_text = [
            note for note in notes if note.source_basis != "full text" and (note.metrics or note.main_results or note.stated_limitations)
        ]
        if len(missing_full_text) >= 2:
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="reproducibility gap",
                    title="Abstract-only evidence limits gap certainty",
                    description="Several candidate signals rely on abstract-only notes rather than parsed full text.",
                    notes=missing_full_text,
                    claims=_claims_matching(claims, ["abstract", "full text", "evidence"]),
                    reason="A gap should not be treated as settled until full-text sections confirm the metric, result, or limitation.",
                    risk="Full text may contain the missing evaluation details and dissolve the apparent gap.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        return gaps

    def _contradiction_gaps(self, state: ResearchRunState, claims: list[Claim]) -> list[Gap]:
        contradictions = state.field_map.contradictions if state.field_map else []
        return [
            self._make_gap(
                state=state,
                gap_type="theory gap",
                title=f"Contradiction: {contradiction[:80]}",
                description=f"The field map reports a contradiction: {contradiction}",
                notes=state.paper_notes[:3],
                claims=_claims_matching(claims, ["contradiction", "accuracy", "synthetic", "deployment"]),
                reason="Contradictory framing suggests the field lacks a settled explanatory account.",
                risk="The contradiction may be an artifact of coarse heuristic mapping.",
                confidence="low",
                novelty_status="unchecked",
            )
            for contradiction in contradictions[:3]
        ]

    def _cross_domain_gaps(self, state: ResearchRunState, claims: list[Claim]) -> list[Gap]:
        if not _adjacent_field_sources_searched(state):
            return []
        adjacent_fields = state.field_map.adjacent_fields if state.field_map else []
        dominant_methods = state.field_map.dominant_methods if state.field_map else []
        gaps = []
        for adjacent in adjacent_fields[:3]:
            if any(adjacent.lower() in " ".join(note.possible_connections).lower() for note in state.paper_notes):
                continue
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="cross-domain gap",
                    title=f"Untested transfer from {adjacent}",
                    description=f"The field map sees {adjacent} nearby, but notes do not show a direct application to the topic.",
                    notes=state.paper_notes[:3],
                    claims=_claims_matching(claims, [adjacent]),
                    reason=f"Imported methods from {adjacent} have not been clearly applied in the selected notes.",
                    risk="The transfer may already exist in papers not retrieved by the current source set.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        if "calibration" in dominant_methods and not any("calibration" in " ".join(note.method).lower() for note in state.paper_notes):
            gaps.append(
                self._make_gap(
                    state=state,
                    gap_type="cross-domain gap",
                    title="Calibration appears adjacent but not operationalized",
                    description=(
                        "The field map identifies calibration as relevant, while paper notes do not show a concrete calibration method."
                    ),
                    notes=state.paper_notes[:3],
                    claims=_claims_matching(claims, ["calibration"]),
                    reason="An imported calibration method could be relevant but is not visible in selected paper notes.",
                    risk="This may be an extraction miss if full text contains calibration details.",
                    confidence="low",
                    novelty_status="unchecked",
                )
            )
        return gaps

    def _make_gap(
        self,
        *,
        state: ResearchRunState,
        gap_type: str,
        title: str,
        description: str,
        notes: list[PaperNote],
        claims: list[Claim],
        reason: str,
        risk: str,
        confidence: str,
        novelty_status: str,
    ) -> Gap:
        supporting_paper_ids = _dedupe([note.paper_id for note in notes if note.paper_id])
        supporting_claim_ids = _dedupe([claim.id for claim in claims if claim.type in {"limitation", "gap", "method", "background"}])
        counter_claim_ids = _dedupe([claim.id for claim in claims if claim.type == "novelty" or claim.counter_evidence])
        explicit_reason = "" if supporting_paper_ids else "Evidence is indirect from field-map or claim patterns."
        return Gap(
            id=f"gap-{abs(hash((gap_type, title))) % 100000}",
            title=title,
            type=gap_type if gap_type in GAP_TYPES else "evaluation gap",
            description=description,
            supporting_paper_ids=supporting_paper_ids,
            supporting_claim_ids=supporting_claim_ids,
            counterevidence_claim_ids=counter_claim_ids,
            why_existing_work_does_not_solve_it=reason,
            why_it_matters=_why_it_matters(gap_type, state.topic.text),
            possible_research_questions=_questions_for_gap(gap_type, state.topic.text),
            minimum_experiment_needed=_minimum_experiment(gap_type, state.topic.text),
            risk_that_gap_is_fake=risk,
            confidence=confidence if supporting_paper_ids or supporting_claim_ids else "low",
            novelty_status=novelty_status,
            closest_prior_work=supporting_paper_ids[:3],
            linked_paper_ids=supporting_paper_ids,
            explicit_reason=explicit_reason,
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=supporting_paper_ids + supporting_claim_ids,
                timestamp=utc_now_iso(),
                reasoning_summary="Gap mined from repeated notes, field-map signals, and claim-ledger patterns.",
            ),
        )

    def _add_gap_claims(self, state: ResearchRunState, gaps: list[Gap]) -> ClaimLedger:
        ledger = ClaimLedger(state.claims)
        by_paper = {paper.id: paper for paper in state.papers}
        for gap in gaps:
            claim = ledger.add_claim(
                f"Candidate {gap.type}: {gap.title}",
                "gap",
                created_by_skill=self.name,
                confidence=gap.confidence,
                source_paper_ids=gap.supporting_paper_ids,
                needs_verification=True,
                notes=f"Novelty status: {gap.novelty_status}. Risk: {gap.risk_that_gap_is_fake}",
                reasoning_summary="Candidate gap claim created from pattern-supported gap mining.",
            )
            for paper_id in gap.supporting_paper_ids[:3]:
                paper = by_paper.get(paper_id)
                quote = paper.abstract if paper and paper.abstract else gap.description
                ledger.add_evidence(
                    claim.id,
                    Evidence(
                        source_id=paper_id,
                        source_paper_id=paper_id,
                        quote=quote[:500],
                        locator=paper.url if paper and paper.url else paper_id,
                        confidence="medium" if paper and paper.abstract else "low",
                        notes=gap.why_existing_work_does_not_solve_it,
                    ),
                )
            if gap.confidence == "medium":
                ledger.mark_uncertain(claim.id, confidence="medium")
            else:
                ledger.mark_uncertain(claim.id, confidence="low")
        return ledger


def _notes_matching(notes: list[PaperNote], terms: list[str], *, include_unstated: bool) -> list[PaperNote]:
    matched = []
    for note in notes:
        values = note.stated_limitations + note.what_it_cannot_answer
        if include_unstated:
            values += note.unstated_limitations + note.assumptions
        text = " ".join(values).lower()
        if any(term in text for term in terms):
            matched.append(note)
    return matched


def _claims_matching(claims: list[Claim], terms: list[str]) -> list[Claim]:
    lowered = [term.lower() for term in terms if term]
    return [claim for claim in claims if any(term in (claim.text + " " + claim.notes).lower() for term in lowered)]


def _build_gap_evidence_matrix(state: ResearchRunState, gap: Gap) -> GapEvidenceMatrix:
    note_by_paper = {note.paper_id: note for note in state.paper_notes}
    section_by_id = {section.id: section for section in state.paper_sections}
    gap_terms = _gap_terms(gap)
    rows: list[GapEvidenceRow] = []
    for paper_id in gap.supporting_paper_ids or gap.linked_paper_ids:
        note = note_by_paper.get(paper_id)
        if note is not None:
            rows.extend(_support_rows_from_note(note, gap, gap_terms, state.evidence_spans, section_by_id))
    rows.extend(_span_rows_for_gap(gap, gap_terms, state.evidence_spans, section_by_id))
    rows.extend(_claim_rows_for_gap(gap, state.claims))
    rows.extend(_counter_rows_for_gap(gap, state.paper_notes, state.evidence_spans, section_by_id))
    rows.extend(_retrieval_counter_rows_for_gap(state, gap))
    rows = _dedupe_rows(rows)
    support_papers = _dedupe([row.paper_id for row in rows if row.supports_or_counters == "supports"])
    counter_papers = _dedupe([row.paper_id for row in rows if row.supports_or_counters == "counters"])
    repeated_limitation_count = len(
        {row.paper_id for row in rows if row.supports_or_counters == "supports" and row.evidence_type in {"limitation", "negative-result"}}
    )
    missing_metric_count = len(
        {row.paper_id for row in rows if row.supports_or_counters == "supports" and row.evidence_type == "missing-metric"}
    )
    missing_dataset_count = len(
        {row.paper_id for row in rows if row.supports_or_counters == "supports" and row.evidence_type == "missing-dataset"}
    )
    assumption_pattern_count = len(
        {row.paper_id for row in rows if row.supports_or_counters == "supports" and row.evidence_type == "assumption"}
    )
    confidence = _matrix_confidence(state, rows, support_papers, counter_papers)
    return GapEvidenceMatrix(
        gap_id=gap.id,
        evidence_rows=rows,
        papers_supporting=support_papers,
        papers_countering=counter_papers,
        repeated_limitation_count=repeated_limitation_count,
        missing_metric_count=missing_metric_count,
        missing_dataset_count=missing_dataset_count,
        assumption_pattern_count=assumption_pattern_count,
        confidence=confidence,
        provenance=Provenance(
            created_by_skill=GapMining.name,
            source_ids=support_papers + counter_papers,
            timestamp=utc_now_iso(),
            reasoning_summary="Built evidence matrix from paper notes, evidence spans, claims, and counterevidence heuristics.",
        ),
    )


def _retrieval_counter_rows_for_gap(state: ResearchRunState, gap: Gap) -> list[GapEvidenceRow]:
    query = f"prior work already solves addresses {gap.title or gap.description} {gap.minimum_experiment_needed}"
    try:
        results, _paper_ids = retrieval_candidates_for_state(state, query, top_k=8)
    except (FileNotFoundError, ValueError, OSError, RuntimeError):
        return []
    support_ids = set(gap.supporting_paper_ids or gap.linked_paper_ids)
    rows: list[GapEvidenceRow] = []
    for result in results:
        if not result.paper_id or result.paper_id in support_ids:
            continue
        if result.object_type not in {"evidence_span", "paper_section", "paper_note", "claim", "novelty_dossier"}:
            continue
        if not _retrieval_result_is_counterevidence(result):
            continue
        rows.append(
            GapEvidenceRow(
                paper_id=result.paper_id,
                claim_or_note_id=f"retrieval:{result.object_id}",
                evidence_span_id=result.object_id if result.object_type == "evidence_span" else "",
                evidence_type="counterevidence",
                text=result.text_snippet,
                supports_or_counters="counters",
                section_type=str(result.metadata.get("section_type", "")),
                locator=result.locator or result.document_id,
            )
        )
    return rows[:3]


def _retrieval_result_is_counterevidence(result: object) -> bool:
    metadata = getattr(result, "metadata", {})
    if isinstance(metadata, dict) and metadata.get("verdict") in {"reject", "revise"}:
        return True
    text = str(getattr(result, "text_snippet", "")).lower()
    return any(
        marker in text
        for marker in [
            "already solves",
            "already addresses",
            "covers the gap",
            "counterevidence",
            "not a gap",
            "duplicate",
            "closest prior work",
        ]
    )


def _support_rows_from_note(
    note: PaperNote,
    gap: Gap,
    gap_terms: set[str],
    spans: list[EvidenceSpan],
    section_by_id: dict[str, PaperSection],
) -> list[GapEvidenceRow]:
    rows: list[GapEvidenceRow] = []
    for text in note.stated_limitations + note.what_it_cannot_answer + note.unstated_limitations:
        if _relevant(text, gap_terms) or _type_relevant(gap.type, text):
            rows.append(_row_from_note(note, text, "limitation", "supports", spans, section_by_id))
    for assumption in note.assumptions:
        if gap.type == "assumption gap" or _relevant(assumption, gap_terms):
            rows.append(_row_from_note(note, assumption, "assumption", "supports", spans, section_by_id))
    if gap.type in {"measurement gap", "evaluation gap"} and not note.metrics:
        rows.append(_row_from_note(note, "Structured note has no extracted metrics.", "missing-metric", "supports", spans, section_by_id))
    if gap.type in {"benchmark gap", "deployment gap"} and not note.datasets:
        rows.append(
            _row_from_note(
                note,
                "Structured note has no extracted datasets or benchmarks.",
                "missing-dataset",
                "supports",
                spans,
                section_by_id,
            )
        )
    if gap.type == "deployment gap" and note.datasets and all("synthetic" in item.lower() for item in note.datasets):
        rows.append(
            _row_from_note(
                note,
                "Structured note reports synthetic-only dataset evidence.",
                "missing-dataset",
                "supports",
                spans,
                section_by_id,
            )
        )
    if not rows and note.one_sentence_summary:
        rows.append(_row_from_note(note, note.one_sentence_summary, "contextual", "contextual", spans, section_by_id))
    return rows


def _span_rows_for_gap(
    gap: Gap,
    gap_terms: set[str],
    spans: list[EvidenceSpan],
    section_by_id: dict[str, PaperSection],
) -> list[GapEvidenceRow]:
    rows = []
    support_ids = set(gap.supporting_paper_ids or gap.linked_paper_ids)
    for span in spans:
        if support_ids and span.paper_id not in support_ids:
            continue
        if not _relevant(span.quote, gap_terms) and not _type_relevant(gap.type, span.quote):
            continue
        rows.append(_row_from_span(span, "supports", section_by_id))
    return rows


def _claim_rows_for_gap(gap: Gap, claims: list[Claim]) -> list[GapEvidenceRow]:
    rows = []
    claim_by_id = {claim.id: claim for claim in claims}
    for claim_id in gap.supporting_claim_ids:
        claim = claim_by_id.get(claim_id)
        if claim is None:
            continue
        for paper_id in claim.source_paper_ids or [""]:
            rows.append(
                GapEvidenceRow(
                    paper_id=paper_id,
                    claim_or_note_id=claim.id,
                    evidence_type=claim.type,
                    text=claim.text,
                    supports_or_counters="supports",
                    locator="claim-ledger",
                )
            )
    for claim_id in gap.counterevidence_claim_ids:
        claim = claim_by_id.get(claim_id)
        if claim is None:
            continue
        for paper_id in claim.source_paper_ids or [""]:
            rows.append(
                GapEvidenceRow(
                    paper_id=paper_id,
                    claim_or_note_id=claim.id,
                    evidence_type=claim.type,
                    text=claim.text,
                    supports_or_counters="counters",
                    locator="claim-ledger",
                )
            )
    return rows


def _counter_rows_for_gap(
    gap: Gap,
    notes: list[PaperNote],
    spans: list[EvidenceSpan],
    section_by_id: dict[str, PaperSection],
) -> list[GapEvidenceRow]:
    support_ids = set(gap.supporting_paper_ids or gap.linked_paper_ids)
    rows = []
    for note in notes:
        if note.paper_id in support_ids:
            continue
        counter_text = _counter_text(gap, note)
        if counter_text:
            rows.append(_row_from_note(note, counter_text, "counterevidence", "counters", spans, section_by_id))
    return rows


def _row_from_note(
    note: PaperNote,
    text: str,
    evidence_type: str,
    supports_or_counters: str,
    spans: list[EvidenceSpan],
    section_by_id: dict[str, PaperSection],
) -> GapEvidenceRow:
    span = _best_span(note.paper_id, text, spans)
    section = section_by_id.get(span.section_id) if span is not None else None
    return GapEvidenceRow(
        paper_id=note.paper_id,
        claim_or_note_id=f"note:{note.paper_id}",
        evidence_span_id=span.id if span is not None else "",
        evidence_type=evidence_type,
        text=text,
        supports_or_counters=supports_or_counters,
        section_type=section.section_type if section is not None else "",
        locator=span.locator if span is not None else note.citation_key or note.paper_id,
    )


def _row_from_span(span: EvidenceSpan, supports_or_counters: str, section_by_id: dict[str, PaperSection]) -> GapEvidenceRow:
    section = section_by_id.get(span.section_id)
    return GapEvidenceRow(
        paper_id=span.paper_id,
        claim_or_note_id="",
        evidence_span_id=span.id,
        evidence_type=span.evidence_type,
        text=span.quote,
        supports_or_counters=supports_or_counters,
        section_type=section.section_type if section is not None else "",
        locator=span.locator or _span_locator(span, section),
    )


def _matrix_confidence(
    state: ResearchRunState,
    rows: list[GapEvidenceRow],
    support_papers: list[str],
    counter_papers: list[str],
) -> str:
    support_rows = [row for row in rows if row.supports_or_counters == "supports"]
    span_rows = [row for row in support_rows if row.evidence_span_id]
    abstract_only = _mostly_abstract_only(state, support_papers)
    coverage_low = state.source_coverage is None or state.source_coverage.confidence == "low"
    counter_search = _counterevidence_search_present(state)
    if len(support_papers) >= 2 and span_rows and counter_search and not counter_papers and not coverage_low and not abstract_only:
        return "high"
    if (len(support_papers) >= 2 or span_rows) and not counter_papers and not abstract_only:
        return "medium"
    if span_rows and not coverage_low:
        return "medium"
    return "low"


def _apply_matrix_confidence(state: ResearchRunState, gaps: list[Gap], matrices: list[GapEvidenceMatrix]) -> None:
    matrix_by_gap = {matrix.gap_id: matrix for matrix in matrices}
    for gap in gaps:
        matrix = matrix_by_gap.get(gap.id)
        if matrix is None:
            gap.confidence = "low"
            if not gap.explicit_reason:
                gap.explicit_reason = "No evidence matrix could be built for this gap."
            continue
        gap.confidence = _min_confidence(gap.confidence, matrix.confidence)
        if matrix.papers_countering:
            gap.confidence = _lower_confidence(gap.confidence)
            counter_text = f" Potential counterevidence papers: {', '.join(matrix.papers_countering[:5])}."
            if counter_text not in gap.risk_that_gap_is_fake:
                gap.risk_that_gap_is_fake = (gap.risk_that_gap_is_fake + counter_text).strip()
        if not matrix.evidence_rows and not gap.explicit_reason:
            gap.explicit_reason = "No note, claim, or span evidence was available for the evidence matrix."


def _filter_by_confidence(gaps: list[Gap], min_confidence: str) -> list[Gap]:
    threshold = CONFIDENCE_ORDER.get(min_confidence, 1)
    return [gap for gap in gaps if CONFIDENCE_ORDER.get(gap.confidence, 1) >= threshold]


def _preserve_locked_gaps(
    state: ResearchRunState,
    new_gaps: list[Gap],
    new_matrices: list[GapEvidenceMatrix],
) -> tuple[list[Gap], list[GapEvidenceMatrix]]:
    locked_ids = locked_object_ids(state, "gap")
    if not locked_ids:
        return new_gaps, new_matrices

    locked_gaps = {gap.id: gap for gap in state.gaps if gap.id in locked_ids}
    locked_matrices = {matrix.gap_id: matrix for matrix in state.gap_evidence_matrices if matrix.gap_id in locked_ids}

    merged_gaps = [locked_gaps.get(gap.id, gap) for gap in new_gaps]
    gap_ids = {gap.id for gap in merged_gaps}
    merged_gaps.extend(gap for gap_id, gap in locked_gaps.items() if gap_id not in gap_ids)

    merged_matrices = [locked_matrices.get(matrix.gap_id, matrix) for matrix in new_matrices]
    matrix_ids = {matrix.gap_id for matrix in merged_matrices}
    merged_matrices.extend(matrix for gap_id, matrix in locked_matrices.items() if gap_id not in matrix_ids)
    return merged_gaps, merged_matrices


def _has_any(values: list[str], terms: list[str]) -> bool:
    text = " ".join(values).lower()
    return any(term in text for term in terms)


CONFIDENCE_ORDER = {"low": 1, "medium": 2, "high": 3}
STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "that",
    "the",
    "this",
    "with",
    "without",
    "gap",
    "papers",
    "paper",
    "work",
}


def _gap_terms(gap: Gap) -> set[str]:
    text = " ".join(
        [
            gap.title,
            gap.description,
            gap.type,
            gap.why_existing_work_does_not_solve_it,
            gap.minimum_experiment_needed,
        ]
    )
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOP_WORDS and len(token) > 3}


def _relevant(text: str, terms: set[str]) -> bool:
    if not text or not terms:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return len(tokens & terms) >= 1


def _type_relevant(gap_type: str, text: str) -> bool:
    lowered = text.lower()
    type_terms = {
        "benchmark gap": ["benchmark", "dataset", "label", "ground truth"],
        "evaluation gap": ["evaluation", "metric", "baseline", "result"],
        "measurement gap": ["metric", "false positive", "specificity", "precision", "recall"],
        "assumption gap": ["assume", "assumption", "controlled", "synthetic"],
        "deployment gap": ["deployment", "real-world", "real world", "shift", "external"],
        "reproducibility gap": ["code", "reproduc", "replication", "implementation"],
        "negative-result gap": ["negative", "failure", "fails", "cannot"],
        "theory gap": ["theory", "contradiction", "explain"],
        "scalability gap": ["scale", "scalability", "large-scale", "latency"],
        "cross-domain gap": ["transfer", "adjacent", "imported"],
    }
    return any(term in lowered for term in type_terms.get(gap_type, []))


def _best_span(paper_id: str, text: str, spans: list[EvidenceSpan]) -> EvidenceSpan | None:
    candidates = [span for span in spans if span.paper_id == paper_id]
    if not candidates:
        return None
    text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    best: tuple[int, EvidenceSpan] | None = None
    for span in candidates:
        overlap = len(text_tokens & set(re.findall(r"[a-z0-9]+", span.quote.lower())))
        if best is None or overlap > best[0]:
            best = (overlap, span)
    if best is not None and best[0] > 0:
        return best[1]
    return None


def _span_locator(span: EvidenceSpan, section: PaperSection | None) -> str:
    if span.locator:
        return span.locator
    section_name = section.normalized_title or section.title if section is not None else "section"
    page = span.page_start or (section.page_start if section is not None else 0)
    return f"{span.paper_id}:{section_name}:p{page}" if page else f"{span.paper_id}:{section_name}"


def _counter_text(gap: Gap, note: PaperNote) -> str:
    lowered_gap = " ".join([gap.title, gap.description, gap.type]).lower()
    if gap.type in {"measurement gap", "evaluation gap"} and note.metrics:
        metric_text = " ".join(note.metrics).lower()
        if "false" in lowered_gap and any(term in metric_text for term in ["false positive", "false-positive", "specificity", "fpr"]):
            return f"Note reports relevant metrics: {', '.join(note.metrics)}."
        if "metric" in lowered_gap:
            return f"Note reports metrics: {', '.join(note.metrics)}."
    if gap.type == "benchmark gap" and note.datasets:
        return f"Note reports datasets or benchmarks: {', '.join(note.datasets)}."
    if gap.type == "deployment gap":
        text = " ".join(note.datasets + note.main_results + note.stated_limitations).lower()
        if any(term in text for term in ["real-world", "real world", "deployment", "external"]):
            return "Note appears to include deployment or real-world evidence."
    if gap.type == "reproducibility gap":
        text = " ".join(note.useful_technical_tools + note.main_results + note.stated_limitations).lower()
        if any(term in text for term in ["code available", "replication", "reproducible"]):
            return "Note appears to include reproducibility evidence."
    if gap.type == "assumption gap":
        text = " ".join(note.main_results + note.stated_limitations + note.what_it_cannot_answer).lower()
        if any(term in text for term in ["ablation", "tested", "validated", "robust"]):
            return "Note appears to test or validate the relevant assumption."
    return ""


def _mostly_abstract_only(state: ResearchRunState, paper_ids: list[str]) -> bool:
    if not paper_ids:
        return True
    notes = [note for note in state.paper_notes if note.paper_id in set(paper_ids)]
    if not notes:
        return False
    return sum(1 for note in notes if note.source_basis != "full text") >= max(1, len(notes) // 2)


def _counterevidence_search_present(state: ResearchRunState) -> bool:
    return bool(
        state.novelty_assessments
        or state.novelty_dossiers
        or any(record.purpose in {"novelty", "citation_expansion"} for record in state.search_queries)
    )


def _adjacent_field_sources_searched(state: ResearchRunState) -> bool:
    if state.field_map is None:
        return False
    adjacent_fields = [field.lower() for field in state.field_map.adjacent_fields]
    if not adjacent_fields:
        return False
    for record in state.search_queries:
        query = record.query.lower()
        if record.purpose == "analogy" and any(field in query for field in adjacent_fields):
            return True
    return any(analogy.papers_or_sources_to_search for analogy in state.cross_domain_analogies)


def _dedupe_rows(rows: list[GapEvidenceRow]) -> list[GapEvidenceRow]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped = []
    for row in rows:
        key = (row.paper_id, row.evidence_span_id, row.evidence_type, row.text[:120])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _min_confidence(left: str, right: str) -> str:
    return left if CONFIDENCE_ORDER.get(left, 1) <= CONFIDENCE_ORDER.get(right, 1) else right


def _lower_confidence(value: str) -> str:
    if value == "high":
        return "medium"
    if value == "medium":
        return "low"
    return "low"


def _why_it_matters(gap_type: str, topic: str) -> str:
    if gap_type in {"measurement gap", "evaluation gap"}:
        return f"Without better measurement, progress on {topic} can optimize the wrong objective."
    if gap_type == "benchmark gap":
        return f"Without realistic benchmarks, {topic} claims may fail outside curated examples."
    if gap_type == "deployment gap":
        return f"Deployment gaps determine whether {topic} is usable in real decision workflows."
    if gap_type == "assumption gap":
        return f"Untested assumptions can make {topic} methods brittle or misleading."
    return f"This gap could change which research directions are credible for {topic}."


def _questions_for_gap(gap_type: str, topic: str) -> list[str]:
    return [
        f"What evidence would falsify this {gap_type} for {topic}?",
        f"Which closest prior work already partially addresses this {gap_type}?",
        "What minimal benchmark would distinguish a real gap from missing metadata?",
    ]


def _minimum_experiment(gap_type: str, topic: str) -> str:
    if gap_type in {"measurement gap", "evaluation gap"}:
        return f"Re-evaluate representative papers on a shared {topic} metric suite with explicit false-positive reporting."
    if gap_type == "benchmark gap":
        return f"Build a small benchmark audit comparing synthetic and realistic {topic} cases."
    if gap_type == "deployment gap":
        return "Test the method under a documented deployment shift and compare failure modes."
    if gap_type == "assumption gap":
        return "Run an ablation that violates the shared assumption and measure degradation."
    return f"Run a focused prior-work check plus one falsifiable pilot experiment for {topic}."


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value and value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _dedupe_gaps(gaps: list[Gap]) -> list[Gap]:
    seen = set()
    deduped = []
    for gap in gaps:
        key = (gap.type, gap.title.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gap)
    return deduped
