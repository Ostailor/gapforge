"""Check gaps and hypotheses against closest prior work."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import (
    Evidence,
    Gap,
    Hypothesis,
    NoveltyAssessment,
    NoveltyDossier,
    Paper,
    Provenance,
    RejectedIdea,
    ResearchRunState,
)
from gapforge.novelty import NoveltyDossierBuilder, NoveltyQueryPlanner
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.skills.base import Skill
from gapforge.sources.coverage import add_search_query_record
from gapforge.sources.ranking import rank_papers
from gapforge.state import utc_now_iso


class NoveltyGate(Skill):
    name = "novelty-gate"

    def __init__(self, sources: Iterable[Any] | None = None, *, search_sources: bool = False) -> None:
        self.sources = list(sources or [])
        self.search_sources = search_sources
        self.query_planner = NoveltyQueryPlanner()
        self.dossier_builder = NoveltyDossierBuilder()

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.assess(state)

    def assess(self, state: ResearchRunState, *, gap_id: str | None = None, deep: bool = False) -> ResearchRunState:
        targets = self._targets(state, gap_id=gap_id)
        assessments: list[NoveltyAssessment] = []
        dossiers: list[NoveltyDossier] = []
        rejected: list[RejectedIdea] = []

        for target_id, summary, gap in targets:
            queries = self.query_planner.plan(state, target_id, summary, gap)
            candidates = self._retrieval_ordered_candidates(state, summary)
            source_search_ran = self.search_sources or deep
            if source_search_ran:
                candidates = self._merge_source_candidates(state, queries, candidates)
            dossier, assessment = self.dossier_builder.build(
                state,
                target_id=target_id,
                idea_summary=summary,
                query_plan=queries,
                candidates=candidates,
                gap=gap,
                source_search_ran=source_search_ran,
            )
            dossiers.append(dossier)
            assessments.append(assessment)
            if gap is not None:
                gap.closest_prior_work = assessment.closest_prior_work
                gap.novelty_status = _gap_novelty_status(assessment)
            if assessment.verdict == "reject":
                rejected.append(
                    RejectedIdea(
                        id=f"rejected-{target_id}",
                        idea=summary,
                        reason=(
                            f"Novelty gate found closest prior work with high overlap: {'; '.join(assessment.closest_prior_work[:2])}."
                        ),
                        provenance=Provenance(
                            created_by_skill=self.name,
                            source_ids=assessment.closest_prior_work,
                            timestamp=utc_now_iso(),
                            reasoning_summary="Rejected the idea because existing run papers already appear to cover it.",
                        ),
                    )
                )

        assessed_ids = [assessment.target_gap_or_hypothesis_id for assessment in assessments]
        state.novelty_assessments = _replace_assessments(state.novelty_assessments, assessments)
        state.novelty_dossiers = _replace_dossiers(state.novelty_dossiers, dossiers)
        state.rejected_ideas = _replace_rejections(state.rejected_ideas, rejected, assessed_ids)
        state.claims = self._add_novelty_claims(state, assessments).claims
        self.mark_complete(state)
        return state

    def _retrieval_ordered_candidates(self, state: ResearchRunState, summary: str) -> list[Paper]:
        try:
            _results, paper_ids = retrieval_candidates_for_state(state, summary, top_k=30)
        except (FileNotFoundError, ValueError, OSError, RuntimeError):
            return list(state.papers)
        paper_by_id = {paper.id: paper for paper in state.papers}
        ordered = [paper_by_id[paper_id] for paper_id in paper_ids if paper_id in paper_by_id]
        ordered_ids = {paper.id for paper in ordered}
        ordered.extend(paper for paper in state.papers if paper.id not in ordered_ids)
        return ordered

    def _targets(self, state: ResearchRunState, *, gap_id: str | None) -> list[tuple[str, str, Gap | None]]:
        gaps = [gap for gap in state.gaps if gap_id is None or gap.id == gap_id]
        hypotheses = [
            hypothesis for hypothesis in state.hypotheses if gap_id is None or hypothesis.gap_id == gap_id or hypothesis.id == gap_id
        ]
        targets: list[tuple[str, str, Gap | None]] = []
        gap_by_id = {gap.id: gap for gap in gaps}
        for gap in gaps:
            targets.append((gap.id, _gap_summary(gap), gap))
        for hypothesis in hypotheses:
            targets.append((hypothesis.id, _hypothesis_summary(hypothesis), gap_by_id.get(hypothesis.gap_id)))
        return targets

    def _merge_source_candidates(self, state: ResearchRunState, queries: list[str], candidates: list[Paper]) -> list[Paper]:
        papers = list(candidates)
        for query in queries[:8]:
            found_for_query: list[Paper] = []
            failures: list[str] = []
            for source in self.sources:
                source_name = str(getattr(source, "name", source.__class__.__name__))
                try:
                    found_for_query.extend(source.search(query, max_results=3, sort="newest", date_from=None, date_to=None))
                except Exception as exc:
                    failures.append(f"{source_name} search failed for {query!r}: {exc}")
            add_search_query_record(
                state,
                query=query,
                source_names=[str(getattr(source, "name", source.__class__.__name__)) for source in self.sources],
                purpose="novelty",
                max_results=3 * max(1, len(self.sources)),
                date_from=None,
                date_to=None,
                result_paper_ids=[paper.id for paper in found_for_query],
                failure_messages=failures,
            )
            papers = rank_papers(state.topic.text, papers + found_for_query, newest_first=True)
        state.papers = rank_papers(state.topic.text, state.papers + papers, newest_first=True)
        return papers

    def _add_novelty_claims(self, state: ResearchRunState, assessments: list[NoveltyAssessment]) -> ClaimLedger:
        ledger = ClaimLedger(state.claims)
        existing = {claim.notes for claim in state.claims if claim.created_by_skill == self.name}
        for assessment in assessments:
            if not assessment.closest_prior_work:
                continue
            note_key = f"novelty-assessment:{assessment.target_gap_or_hypothesis_id}"
            if note_key in existing:
                continue
            evidence = [
                Evidence(
                    source_id=item.split(":", 1)[0],
                    quote=item,
                    locator="current-run-paper-store",
                    confidence=assessment.confidence,
                    source_paper_id=item.split(":", 1)[0],
                    notes=f"Similarity score {assessment.similarity_to_prior_work:.2f}",
                )
                for item in assessment.closest_prior_work[:3]
            ]
            status = "contested" if assessment.verdict in {"reject", "revise"} else "uncertain"
            claim = ledger.add_claim(
                text=(
                    f"Novelty gate verdict for {assessment.target_gap_or_hypothesis_id}: "
                    f"{assessment.verdict} with {assessment.novelty_strength} novelty strength."
                ),
                claim_type="novelty",
                confidence=assessment.confidence,
                source_paper_ids=[item.source_paper_id for item in evidence],
                created_by_skill=self.name,
                needs_verification=assessment.verdict != "reject",
                notes=note_key,
                closest_prior_work=assessment.closest_prior_work,
            )
            for item in evidence:
                ledger.add_evidence(claim.id, item)
            if status == "contested":
                ledger.mark_contested(claim.id, confidence=assessment.confidence)
            else:
                ledger.mark_uncertain(claim.id, confidence=assessment.confidence)
        return ledger


def _gap_summary(gap: Gap) -> str:
    parts = [gap.title, gap.description, gap.why_existing_work_does_not_solve_it, gap.minimum_experiment_needed]
    return " ".join(part for part in parts if part).strip() or gap.id


def _hypothesis_summary(hypothesis: Hypothesis) -> str:
    return " ".join(part for part in [hypothesis.text, hypothesis.rationale] if part).strip() or hypothesis.id


def _gap_novelty_status(assessment: NoveltyAssessment) -> str:
    if assessment.verdict == "reject":
        return "likely_not_new"
    if assessment.verdict == "revise":
        return "weak"
    if assessment.verdict == "pursue":
        return assessment.novelty_strength
    return "unchecked"


def _replace_assessments(existing: list[NoveltyAssessment], new_items: list[NoveltyAssessment]) -> list[NoveltyAssessment]:
    replacing = {item.target_gap_or_hypothesis_id for item in new_items}
    return [item for item in existing if item.target_gap_or_hypothesis_id not in replacing] + new_items


def _replace_dossiers(existing: list[NoveltyDossier], new_items: list[NoveltyDossier]) -> list[NoveltyDossier]:
    replacing = {item.target_id for item in new_items}
    return [item for item in existing if item.target_id not in replacing] + new_items


def _replace_rejections(existing: list[RejectedIdea], new_items: list[RejectedIdea], assessed_ids: list[str]) -> list[RejectedIdea]:
    replacing = {item.id for item in new_items} | {f"rejected-{target_id}" for target_id in assessed_ids}
    return [item for item in existing if item.id not in replacing] + new_items
