"""Check gaps and hypotheses against closest prior work."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import (
    Evidence,
    Gap,
    Hypothesis,
    NoveltyAssessment,
    Paper,
    PaperNote,
    Provenance,
    RejectedIdea,
    ResearchRunState,
)
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "without",
}


@dataclass(slots=True)
class PriorMatch:
    paper: Paper
    similarity: float
    overlap_terms: list[str]


class NoveltyGate(Skill):
    name = "novelty-gate"

    def __init__(self, sources: Iterable[Any] | None = None, *, search_sources: bool = False) -> None:
        self.sources = list(sources or [])
        self.search_sources = search_sources

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.assess(state)

    def assess(self, state: ResearchRunState, *, gap_id: str | None = None) -> ResearchRunState:
        targets = self._targets(state, gap_id=gap_id)
        assessments: list[NoveltyAssessment] = []
        rejected: list[RejectedIdea] = []

        for target_id, summary, gap in targets:
            queries = self._queries(state, summary, gap)
            matches = self._closest_prior_work(summary, state.papers, state.paper_notes)
            if self.search_sources:
                matches = self._merge_source_matches(summary, queries, matches)
            assessment = self._assessment_for(target_id, summary, gap, queries, matches, source_search_ran=self.search_sources)
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
        state.rejected_ideas = _replace_rejections(state.rejected_ideas, rejected, assessed_ids)
        state.claims = self._add_novelty_claims(state, assessments).claims
        self.mark_complete(state)
        return state

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

    def _queries(self, state: ResearchRunState, summary: str, gap: Gap | None) -> list[str]:
        topic = state.topic.text
        terms = " ".join(_keywords(summary, limit=6))
        queries = [
            f"{topic} {terms} closest prior work",
            f"{terms} benchmark evaluation prior work",
            f"{terms} limitations future work",
        ]
        if gap is not None:
            queries.append(f"{topic} {gap.type} {gap.title}")
            if gap.minimum_experiment_needed:
                queries.append(f"{terms} {gap.minimum_experiment_needed}")
        if state.field_map is not None:
            for adjacent in state.field_map.adjacent_fields[:2]:
                queries.append(f"{terms} {adjacent} prior work")
        return _dedupe_strings(queries)

    def _closest_prior_work(self, summary: str, papers: list[Paper], notes: list[PaperNote]) -> list[PriorMatch]:
        note_by_paper = {note.paper_id: note for note in notes}
        idea_tokens = set(_tokens(summary))
        matches: list[PriorMatch] = []
        for paper in papers:
            note = note_by_paper.get(paper.id)
            corpus = _paper_text(paper, note)
            paper_tokens = set(_tokens(corpus))
            if not paper_tokens:
                continue
            overlap_terms = sorted(idea_tokens & paper_tokens)
            overlap = len(overlap_terms) / max(1, len(idea_tokens))
            title_ratio = SequenceMatcher(None, _normalize(summary), _normalize(paper.title)).ratio()
            exact_title_bonus = 0.5 if _normalize(paper.title) in _normalize(summary) else 0.0
            similarity = min(1.0, max(overlap * 0.8, title_ratio * 0.5) + exact_title_bonus)
            if similarity >= 0.12:
                matches.append(PriorMatch(paper=paper, similarity=similarity, overlap_terms=overlap_terms[:8]))
        return sorted(matches, key=lambda match: match.similarity, reverse=True)[:5]

    def _merge_source_matches(self, summary: str, queries: list[str], matches: list[PriorMatch]) -> list[PriorMatch]:
        papers = [match.paper for match in matches]
        seen = {paper.id for paper in papers}
        for source in self.sources:
            for query in queries[:2]:
                try:
                    found = source.search(query, max_results=3, sort="newest", date_from=None, date_to=None)
                except Exception:
                    continue
                for paper in found:
                    if paper.id not in seen:
                        papers.append(paper)
                        seen.add(paper.id)
        return self._closest_prior_work(summary, papers, [])

    def _assessment_for(
        self,
        target_id: str,
        summary: str,
        gap: Gap | None,
        queries: list[str],
        matches: list[PriorMatch],
        *,
        source_search_ran: bool,
    ) -> NoveltyAssessment:
        top = matches[0] if matches else None
        if top is None:
            verdict = "unknown"
            strength = "unknown"
            confidence = "low"
            what_new = ["No close prior work was found in the current run, but adjacent-source searches remain missing."]
            what_not_new = ["Not established because closest prior work has not been found."]
            objection = "A reviewer could find an unsearched paper that already resolves this idea."
            decisive = "Run connector searches and compare against citation-neighborhood papers before proposing this idea."
        elif top.similarity >= 0.72:
            verdict = "reject"
            strength = "weak"
            confidence = "high"
            what_new = ["No decisive novelty is visible from the current evidence."]
            what_not_new = [
                f"{top.paper.title} appears to cover the central terms: {', '.join(top.overlap_terms) or 'high title overlap'}."
            ]
            objection = "This appears duplicative of closest prior work."
            decisive = "Show a materially different task, setting, metric, or theoretical contribution."
        elif top.similarity >= 0.42:
            verdict = "revise"
            strength = "weak"
            confidence = "medium"
            what_new = [_novelty_hint(gap)]
            what_not_new = [f"Closest prior work already overlaps on {', '.join(top.overlap_terms) or 'the main framing'}."]
            objection = "The idea may read as an incremental variant unless the difference is sharpened."
            decisive = "State the exact condition, benchmark, or failure mode not handled by closest prior work."
        elif top.similarity >= 0.18:
            verdict = "pursue"
            strength = "medium"
            confidence = "medium"
            what_new = [_novelty_hint(gap)]
            what_not_new = [f"Related prior work exists, especially {top.paper.title}, so framing and baselines are not new."]
            objection = "A reviewer may ask why related methods or benchmarks from the closest prior are insufficient."
            decisive = "Include the closest prior as a baseline and make the failure mode measurable."
        else:
            verdict = "unknown"
            strength = "unknown"
            confidence = "low"
            what_new = ["The current run does not contain enough relevant prior work to assess novelty."]
            what_not_new = ["Unknown."]
            objection = "Novelty cannot be evaluated without broader source searches."
            decisive = "Search external sources and read the nearest papers before advancing this idea."

        closest = [_prior_label(match) for match in matches[:3]]
        missing = [] if source_search_ran else [f"source connector search: {query}" for query in queries]
        return NoveltyAssessment(
            target_gap_or_hypothesis_id=target_id,
            idea_summary=summary,
            closest_prior_work=closest,
            similarity_to_prior_work=top.similarity if top is not None else 0.0,
            what_is_new=what_new,
            what_is_not_new=what_not_new,
            possible_reviewer_objection=objection,
            decisive_difference_needed=decisive,
            search_queries_used=queries,
            missing_searches=missing,
            verdict=verdict,
            novelty_strength=strength,
            confidence=confidence,
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=[match.paper.id for match in matches[:3]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Compared the idea against existing run papers and notes using deterministic lexical overlap. "
                    "No hidden reasoning is stored."
                ),
            ),
        )

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


def _paper_text(paper: Paper, note: PaperNote | None) -> str:
    note_parts: list[str] = []
    if note is not None:
        note_parts = [
            note.one_sentence_summary,
            " ".join(note.core_claims),
            " ".join(note.method),
            " ".join(note.main_results),
            " ".join(note.assumptions),
            " ".join(note.stated_limitations),
            " ".join(note.unstated_limitations),
            " ".join(note.what_it_cannot_answer),
        ]
    return " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords), *note_parts])


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOP_WORDS and len(token) > 2]


def _keywords(text: str, *, limit: int) -> list[str]:
    seen: list[str] = []
    for token in _tokens(text):
        if token not in seen:
            seen.append(token)
        if len(seen) == limit:
            break
    return seen


def _normalize(text: str) -> str:
    return " ".join(_tokens(text))


def _prior_label(match: PriorMatch) -> str:
    return f"{match.paper.id}: {match.paper.title} (similarity {match.similarity:.2f})"


def _novelty_hint(gap: Gap | None) -> str:
    if gap is None:
        return "The hypothesis may be new only if its exact failure mode is not covered by closest prior work."
    if gap.why_existing_work_does_not_solve_it:
        return gap.why_existing_work_does_not_solve_it
    if gap.minimum_experiment_needed:
        return f"The proposed experiment may test a condition not yet checked: {gap.minimum_experiment_needed}"
    return "The gap may be new only if the linked papers truly leave the stated condition unresolved."


def _gap_novelty_status(assessment: NoveltyAssessment) -> str:
    if assessment.verdict == "reject":
        return "likely_not_new"
    if assessment.verdict == "revise":
        return "weak"
    if assessment.verdict == "pursue":
        return assessment.novelty_strength
    return "unchecked"


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(value.split())
        key = clean.lower()
        if clean and key not in seen:
            deduped.append(clean)
            seen.add(key)
    return deduped


def _replace_assessments(existing: list[NoveltyAssessment], new_items: list[NoveltyAssessment]) -> list[NoveltyAssessment]:
    replacing = {item.target_gap_or_hypothesis_id for item in new_items}
    return [item for item in existing if item.target_gap_or_hypothesis_id not in replacing] + new_items


def _replace_rejections(existing: list[RejectedIdea], new_items: list[RejectedIdea], assessed_ids: list[str]) -> list[RejectedIdea]:
    replacing = {item.id for item in new_items} | {f"rejected-{target_id}" for target_id in assessed_ids}
    return [item for item in existing if item.id not in replacing] + new_items
