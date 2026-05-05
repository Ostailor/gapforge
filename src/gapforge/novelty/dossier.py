"""Novelty dossier assembly."""

from __future__ import annotations

from datetime import UTC, datetime

from gapforge.models import EvidenceSpan, Gap, NoveltyAssessment, NoveltyDossier, Paper, Provenance, ResearchRunState
from gapforge.novelty.comparator import PriorWorkComparator, PriorWorkMatch, comparison_row


class NoveltyDossierBuilder:
    def __init__(self, comparator: PriorWorkComparator | None = None) -> None:
        self.comparator = comparator or PriorWorkComparator()

    def build(
        self,
        state: ResearchRunState,
        *,
        target_id: str,
        idea_summary: str,
        query_plan: list[str],
        candidates: list[Paper],
        gap: Gap | None = None,
        source_search_ran: bool = False,
    ) -> tuple[NoveltyDossier, NoveltyAssessment]:
        matches = self.comparator.compare(
            idea_summary,
            candidates,
            gap=gap,
            notes=state.paper_notes,
            sections=state.paper_sections,
        )
        coverage_weak = _coverage_is_weak(state, source_search_ran)
        verdict, strength, confidence = _verdict(matches, coverage_weak)
        top = matches[0] if matches else None
        missing = [] if source_search_ran else [f"source connector search: {query}" for query in query_plan]
        if state.source_coverage is not None and state.source_coverage.confidence == "low":
            missing.append("strong source/full-text coverage")
        decisive = _decisive_difference(top, gap, coverage_weak)
        objection = _reviewer_objection(top, verdict, coverage_weak)
        action = _recommended_action(verdict, coverage_weak)
        evidence_spans = _supporting_spans(state, matches[:3])
        top_prior = [_prior_label(match) for match in matches[:5]]
        now = _now()
        dossier = NoveltyDossier(
            target_id=target_id,
            idea_summary=idea_summary,
            query_plan=query_plan,
            candidates_considered=[paper.id for paper in candidates],
            top_prior_work=top_prior,
            comparison_table=[comparison_row(match) for match in matches[:10]],
            decisive_difference_needed=decisive,
            missing_searches=_dedupe(missing),
            verdict=verdict,
            novelty_strength=strength,
            confidence=confidence,
            evidence_spans=evidence_spans,
            reviewer_objection=objection,
            recommended_action=action,
            provenance=Provenance(
                created_by_skill="novelty-gate",
                source_ids=[match.paper.id for match in matches[:5]],
                timestamp=now,
                reasoning_summary="Built closest-prior-work dossier with deterministic lexical and structured-field comparison.",
            ),
        )
        assessment = NoveltyAssessment(
            target_gap_or_hypothesis_id=target_id,
            idea_summary=idea_summary,
            closest_prior_work=top_prior[:3],
            similarity_to_prior_work=top.overall_similarity if top is not None else 0.0,
            what_is_new=_what_is_new(top, gap),
            what_is_not_new=_what_is_not_new(top),
            possible_reviewer_objection=objection,
            decisive_difference_needed=decisive,
            search_queries_used=query_plan,
            missing_searches=dossier.missing_searches,
            verdict=verdict,
            novelty_strength=strength,
            confidence=confidence,
            provenance=dossier.provenance,
        )
        return dossier, assessment


def _verdict(matches: list[PriorWorkMatch], coverage_weak: bool) -> tuple[str, str, str]:
    if not matches:
        return "unknown", "unknown", "low"
    top = matches[0]
    covers_core = top.problem_overlap >= 0.6 and top.method_overlap >= 0.5 and top.evaluation_overlap >= 0.5
    if covers_core or top.overall_similarity >= 0.72:
        return "reject", "weak", "high"
    if top.problem_overlap >= 0.5 and top.overall_similarity >= 0.38:
        return "revise", "weak", "medium"
    if coverage_weak:
        return "unknown", "unknown", "low"
    if top.overall_similarity >= 0.18:
        return "pursue", "medium", "medium"
    return "unknown", "unknown", "low"


def _coverage_is_weak(state: ResearchRunState, source_search_ran: bool) -> bool:
    if not state.search_queries and not source_search_ran:
        return True
    if state.source_coverage is not None and state.source_coverage.confidence == "low":
        return True
    if state.papers and not state.paper_sections and state.source_coverage is not None and not state.source_coverage.papers_with_full_text:
        return True
    return False


def _decisive_difference(match: PriorWorkMatch | None, gap: Gap | None, coverage_weak: bool) -> str:
    if match is None:
        return "Run broader source and citation-neighborhood searches, then identify the closest prior work before claiming novelty."
    if coverage_weak:
        return "Improve source/full-text coverage before making a novelty claim; then compare against the listed closest prior work."
    if gap is not None and gap.minimum_experiment_needed:
        return f"Show that closest prior work does not test: {gap.minimum_experiment_needed}"
    return "State the exact problem setting, method, metric, dataset, or failure mode that closest prior work does not cover."


def _reviewer_objection(match: PriorWorkMatch | None, verdict: str, coverage_weak: bool) -> str:
    if coverage_weak:
        return "Novelty cannot be trusted because search or full-text coverage is weak."
    if match is None:
        return "A reviewer may find unsearched prior work that already covers this idea."
    if verdict == "reject":
        return f"{match.paper.title} appears to cover the core problem, method, and evaluation."
    if verdict == "revise":
        return f"{match.paper.title} overlaps on the main problem; the paper must sharpen what is different."
    return f"Related prior work exists, especially {match.paper.title}; it must be used as a baseline or positioning anchor."


def _recommended_action(verdict: str, coverage_weak: bool) -> str:
    if verdict == "reject":
        return "Reject or substantially reframe the idea."
    if verdict == "revise":
        return "Revise the setting, metric, or experiment until the difference from closest prior work is decisive."
    if coverage_weak or verdict == "unknown":
        return "Do not advance yet; expand searches and improve full-text evidence."
    return "Pursue as a candidate direction with closest prior work as baseline."


def _what_is_new(match: PriorWorkMatch | None, gap: Gap | None) -> list[str]:
    if match is None:
        return ["Not established; no closest prior work was found."]
    hints = []
    if gap is not None and gap.why_existing_work_does_not_solve_it:
        hints.append(gap.why_existing_work_does_not_solve_it)
    if match.metric_overlap < 0.4:
        hints.append("The target metric/evaluation emphasis may differ from closest prior work.")
    if match.dataset_overlap < 0.4:
        hints.append("The target dataset or deployment setting may differ from closest prior work.")
    return hints or ["No decisive novelty is visible from the current dossier."]


def _what_is_not_new(match: PriorWorkMatch | None) -> list[str]:
    if match is None:
        return ["Unknown."]
    parts = []
    if match.problem_overlap:
        parts.append("problem framing")
    if match.method_overlap:
        parts.append("method family")
    if match.evaluation_overlap:
        parts.append("evaluation setting")
    return [f"Closest prior work overlaps on {', '.join(parts) or 'core terminology'}."]


def _supporting_spans(state: ResearchRunState, matches: list[PriorWorkMatch]) -> list[EvidenceSpan]:
    paper_ids = {match.paper.id for match in matches}
    return [span for span in state.evidence_spans if span.paper_id in paper_ids][:10]


def _prior_label(match: PriorWorkMatch) -> str:
    return f"{match.paper.id}: {match.paper.title} (similarity {match.overall_similarity:.2f})"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _now() -> str:
    return datetime.now(UTC).isoformat()
