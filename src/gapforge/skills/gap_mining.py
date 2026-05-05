"""Mine research gaps from repeated literature patterns."""

from __future__ import annotations

from collections import Counter

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import Claim, Evidence, Gap, PaperNote, Provenance, ResearchRunState
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

    def run(self, state: ResearchRunState) -> ResearchRunState:
        gaps = self.mine_gaps(state)
        state.gaps = gaps
        state.claims = self._add_gap_claims(state, gaps).claims
        self.mark_complete(state)
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
        gaps.extend(self._contradiction_gaps(state, claims))
        gaps.extend(self._cross_domain_gaps(state, claims))

        if field_map is not None:
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


def _has_any(values: list[str], terms: list[str]) -> bool:
    text = " ".join(values).lower()
    return any(term in text for term in terms)


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
