"""Sanitize LLM-assisted novelty comparisons against known prior work."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gapforge.models import EvidenceSpan, Gap, NoveltyAssessment, NoveltyDossier, Paper, Provenance, ResearchRunState
from gapforge.review.audit import is_rejected
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class LLMNoveltyComparisonResult:
    dossier: NoveltyDossier
    assessment: NoveltyAssessment
    rejected_reasons: list[str] = field(default_factory=list)
    contested: bool = False


class LLMNoveltyComparator:
    """Conservative adapter from model JSON to auditable novelty artifacts."""

    def refine(
        self,
        state: ResearchRunState,
        *,
        target_id: str,
        idea_summary: str,
        deterministic_dossier: NoveltyDossier,
        deterministic_assessment: NoveltyAssessment,
        payload: dict[str, Any],
        candidates: list[Paper],
        retrieval_ran: bool,
        citation_expansion_ran: bool,
        gap: Gap | None = None,
    ) -> LLMNoveltyComparisonResult:
        rejected: list[str] = []
        allowed_prior_ids = _allowed_prior_ids(state, candidates)
        closest_prior_work = _valid_prior_work(payload.get("closest_prior_work", []), allowed_prior_ids)
        invalid_prior = _invalid_prior_work(payload.get("closest_prior_work", []), allowed_prior_ids)
        rejected.extend([f"Rejected invalid prior-work ID: {item}" for item in invalid_prior])
        if invalid_prior and not closest_prior_work:
            payload = {**payload, "verdict": "unknown", "novelty_strength": "unknown", "confidence": "low"}

        comparison_table, comparison_rejections = _sanitize_comparison_table(state, payload.get("comparison_table", []), allowed_prior_ids)
        rejected.extend(comparison_rejections)
        if not comparison_table and deterministic_dossier.comparison_table:
            comparison_table = deterministic_dossier.comparison_table[:10]

        model_supplied_prior = bool(closest_prior_work)
        model_supplied_table = bool(comparison_table)
        missing_searches = _dedupe(
            _list_strings(payload.get("missing_searches")) + _required_missing_searches(state, retrieval_ran, citation_expansion_ran)
        )
        verdict = _enum(str(payload.get("verdict", deterministic_dossier.verdict)), {"reject", "revise", "pursue", "unknown"}, "unknown")
        strength = _enum(
            str(payload.get("novelty_strength", deterministic_dossier.novelty_strength)),
            {"weak", "medium", "strong", "unknown"},
            "unknown",
        )
        confidence = _enum(str(payload.get("confidence", deterministic_dossier.confidence)), {"low", "medium", "high"}, "low")
        if not model_supplied_prior and not model_supplied_table and verdict == "unknown" and deterministic_dossier.top_prior_work:
            verdict = deterministic_dossier.verdict
            strength = deterministic_dossier.novelty_strength
            confidence = deterministic_dossier.confidence
        contested = _contradicts_deterministic(deterministic_assessment.verdict, verdict)
        if contested and not _comparison_has_locator_support(comparison_table):
            verdict = "revise" if deterministic_assessment.verdict in {"reject", "revise"} else "unknown"
            strength = "weak" if verdict == "revise" else "unknown"
            confidence = "low"
            rejected.append("LLM verdict contradicted deterministic comparator without locator-backed comparison support.")

        if strength == "strong" and not _strong_novelty_allowed(
            state,
            closest_prior_work,
            missing_searches,
            retrieval_ran,
            citation_expansion_ran,
            target_id,
        ):
            strength = "medium" if verdict == "pursue" else "unknown"
            confidence = "medium" if confidence == "high" else confidence
            rejected.append("Strong novelty downgraded because coverage/prior-work/search prerequisites were not met.")

        if not closest_prior_work:
            closest_prior_work = deterministic_dossier.top_prior_work[:3]
        if not closest_prior_work and verdict == "pursue":
            verdict = "unknown"
            strength = "unknown"
            confidence = "low"
            missing_searches = _dedupe(missing_searches + ["closest prior work"])
            rejected.append("Pursue verdict downgraded because no closest prior work was listed.")

        objection = str(payload.get("possible_reviewer_objection") or deterministic_dossier.reviewer_objection)
        if contested:
            objection = f"Contested novelty comparison: {objection}".strip()
        decisive = str(payload.get("decisive_difference_needed") or deterministic_dossier.decisive_difference_needed)
        now = utc_now_iso()
        evidence_spans = _evidence_spans_for_comparison(state, comparison_table, closest_prior_work)
        dossier = NoveltyDossier(
            target_id=target_id,
            idea_summary=idea_summary,
            query_plan=deterministic_dossier.query_plan,
            candidates_considered=_dedupe(deterministic_dossier.candidates_considered + [paper.id for paper in candidates]),
            top_prior_work=closest_prior_work,
            comparison_table=comparison_table,
            decisive_difference_needed=decisive,
            missing_searches=missing_searches,
            verdict=verdict,
            novelty_strength=strength,
            confidence=confidence,
            evidence_spans=evidence_spans,
            reviewer_objection=objection,
            recommended_action=_recommended_action(verdict, contested, missing_searches),
            provenance=Provenance(
                created_by_skill="novelty-gate-llm",
                source_ids=_dedupe([_prior_id(item) for item in closest_prior_work] + [span.id for span in evidence_spans]),
                timestamp=now,
                reasoning_summary=str(payload.get("reasoning_summary") or "LLM novelty comparison accepted after prior-work validation."),
            ),
        )
        assessment = NoveltyAssessment(
            target_gap_or_hypothesis_id=target_id,
            idea_summary=idea_summary,
            closest_prior_work=closest_prior_work[:3],
            similarity_to_prior_work=_top_similarity(comparison_table),
            what_is_new=_list_strings(payload.get("what_is_new")) or deterministic_assessment.what_is_new,
            what_is_not_new=_list_strings(payload.get("what_is_not_new")) or deterministic_assessment.what_is_not_new,
            possible_reviewer_objection=objection,
            decisive_difference_needed=decisive,
            search_queries_used=deterministic_assessment.search_queries_used,
            missing_searches=missing_searches,
            verdict=verdict,
            novelty_strength=strength,
            confidence=confidence,
            provenance=dossier.provenance,
        )
        return LLMNoveltyComparisonResult(dossier=dossier, assessment=assessment, rejected_reasons=rejected, contested=contested)


def _allowed_prior_ids(state: ResearchRunState, candidates: list[Paper]) -> set[str]:
    ids = {paper.id for paper in state.papers} | {paper.id for paper in candidates}
    for record in state.search_queries:
        ids.update(record.result_paper_ids)
    return ids


def _valid_prior_work(raw_items: Any, allowed_ids: set[str]) -> list[str]:
    return [item for item in _list_strings(raw_items) if _prior_id(item) in allowed_ids]


def _invalid_prior_work(raw_items: Any, allowed_ids: set[str]) -> list[str]:
    return [item for item in _list_strings(raw_items) if _prior_id(item) not in allowed_ids]


def _sanitize_comparison_table(
    state: ResearchRunState,
    raw_rows: Any,
    allowed_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw_rows, list):
        return [], []
    rejected: list[str] = []
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        paper_id = str(row.get("paper_id", "")).strip() or _prior_id(str(row.get("prior_work", "")))
        if paper_id not in allowed_ids:
            rejected.append(f"Rejected comparison row with unknown prior-work paper ID: {paper_id or 'missing'}")
            continue
        evidence_locators = _valid_locators(state, paper_id, row.get("evidence_locators", []))
        sanitized = {
            key: value
            for key, value in row.items()
            if key
            in {
                "paper_id",
                "title",
                "overall_similarity",
                "similarity",
                "problem_overlap",
                "method_overlap",
                "dataset_overlap",
                "metric_overlap",
                "evaluation_overlap",
                "tests_minimum_experiment",
                "overlap_terms",
                "what_overlaps",
                "what_differs",
                "evidence_locators",
            }
        }
        sanitized["paper_id"] = paper_id
        sanitized["evidence_locators"] = evidence_locators
        rows.append(sanitized)
    return rows, rejected


def _valid_locators(state: ResearchRunState, paper_id: str, raw_locators: Any) -> list[str]:
    wanted = set(_list_strings(raw_locators))
    if not wanted:
        return []
    valid = []
    for span in state.evidence_spans:
        if span.paper_id == paper_id and (span.locator in wanted or span.id in wanted):
            valid.append(span.locator or span.id)
    return valid


def _required_missing_searches(state: ResearchRunState, retrieval_ran: bool, citation_expansion_ran: bool) -> list[str]:
    missing = []
    if state.source_coverage is None or state.source_coverage.confidence not in {"medium", "high"}:
        missing.append("medium-or-better source coverage")
    if not retrieval_ran:
        missing.append("retrieval candidate search")
    if not citation_expansion_ran:
        missing.append("citation expansion")
    return missing


def _strong_novelty_allowed(
    state: ResearchRunState,
    closest_prior_work: list[str],
    missing_searches: list[str],
    retrieval_ran: bool,
    citation_expansion_ran: bool,
    target_id: str,
) -> bool:
    coverage_ok = state.source_coverage is not None and state.source_coverage.confidence in {"medium", "high"}
    return (
        coverage_ok
        and bool(closest_prior_work)
        and retrieval_ran
        and citation_expansion_ran
        and not missing_searches
        and not is_rejected(state, "gap", target_id)
    )


def _contradicts_deterministic(deterministic_verdict: str, llm_verdict: str) -> bool:
    if deterministic_verdict in {"reject", "revise"} and llm_verdict == "pursue":
        return True
    if deterministic_verdict == "reject" and llm_verdict in {"unknown", "pursue"}:
        return True
    return False


def _comparison_has_locator_support(comparison_table: list[dict[str, Any]]) -> bool:
    return any(row.get("evidence_locators") for row in comparison_table)


def _evidence_spans_for_comparison(
    state: ResearchRunState,
    comparison_table: list[dict[str, Any]],
    closest_prior_work: list[str],
) -> list[EvidenceSpan]:
    paper_ids = {_prior_id(item) for item in closest_prior_work}
    locators = {locator for row in comparison_table for locator in _list_strings(row.get("evidence_locators"))}
    spans = []
    for span in state.evidence_spans:
        if span.paper_id in paper_ids or span.locator in locators or span.id in locators:
            spans.append(span)
    return spans[:12]


def _recommended_action(verdict: str, contested: bool, missing_searches: list[str]) -> str:
    if contested:
        return "Treat as contested; resolve disagreement with evidence-located prior-work comparison."
    if missing_searches:
        return "Do not claim novelty; complete missing searches and rerun the novelty dossier."
    if verdict == "reject":
        return "Reject or substantially reframe the idea."
    if verdict == "revise":
        return "Revise the contribution until the decisive difference from closest prior work is clear."
    if verdict == "pursue":
        return "Pursue cautiously with closest prior work as the required positioning baseline."
    return "Keep novelty unknown until closest prior work and coverage improve."


def _top_similarity(comparison_table: list[dict[str, Any]]) -> float:
    scores = []
    for row in comparison_table:
        value = row.get("overall_similarity", row.get("similarity", 0.0))
        try:
            scores.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(scores or [0.0])


def _prior_id(item: str) -> str:
    return item.split(":", 1)[0].strip()


def _enum(value: str, allowed: set[str], default: str) -> str:
    return value if value in allowed else default


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
