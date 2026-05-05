"""v0.2 paper ranking with role, source, and coverage diversity."""

from __future__ import annotations

import math
import re
from collections import Counter

from gapforge.models import Paper, PaperRankingDecision, PaperRankingResult, ResearchRunState
from gapforge.sources.ranking import AUTHORITATIVE_VENUE_TERMS, deduplicate_papers

PAPER_ROLES = {
    "frontier",
    "seminal",
    "survey",
    "benchmark",
    "dataset",
    "method",
    "theory",
    "negative_result",
    "adjacent_field",
    "unclear",
}


def rank_papers_v2(
    topic: str,
    papers: list[Paper],
    *,
    state: ResearchRunState | None = None,
    query_purpose: str = "initial_topic",
    recency_preference: str = "newest",
    source_diversity_target: int = 2,
    role_diversity_target: int = 2,
) -> PaperRankingResult:
    deduped = deduplicate_papers(papers)
    decisions = [
        _score_paper(
            topic,
            paper,
            state=state,
            query_purpose=query_purpose,
            recency_preference=recency_preference,
        )
        for paper in deduped
    ]
    decisions.sort(key=lambda decision: decision.score, reverse=True)
    decisions = _apply_diversity(decisions, source_diversity_target, role_diversity_target)
    for index, decision in enumerate(decisions, start=1):
        decision.rank = index
    return PaperRankingResult(
        topic=topic,
        decisions=decisions,
        query_purpose=query_purpose,
        recency_preference=recency_preference,
        source_diversity_target=source_diversity_target,
        role_diversity_target=role_diversity_target,
        scoring_summary=(
            "v0.2 ranking combines topic relevance, recency, citation count, venue/source authority, role/source diversity, "
            "full-text availability, novelty/closest-prior-work importance, adjacent-field transfer evidence, survey signals, "
            "and exact method/metric/dataset overlap."
        ),
    )


def infer_paper_role(topic: str, paper: Paper, *, state: ResearchRunState | None = None) -> tuple[str, list[str]]:
    if paper.roles:
        role = paper.roles[0] if paper.roles[0] in PAPER_ROLES else "unclear"
        return role, [f"manual/source role annotation: {role}"]
    text = _paper_text(paper)
    reasons: list[str] = []
    if _is_adjacent_field(paper, state):
        return "adjacent_field", ["paper is linked to a promoted/query adjacent-field transfer candidate"]
    if any(term in text for term in ["survey", "systematic review", "review of", "meta-analysis", "tutorial"]):
        return "survey", ["title/abstract indicates survey or systematic review"]
    if any(term in text for term in ["benchmark", "leaderboard", "evaluation suite"]):
        return "benchmark", ["mentions benchmark or evaluation suite"]
    if any(term in text for term in ["dataset", "corpus", "labels", "ground truth"]):
        return "dataset", ["mentions dataset, corpus, labels, or ground truth"]
    if any(term in text for term in ["negative result", "null result", "failure", "fails", "does not improve"]):
        return "negative_result", ["mentions negative result or failure"]
    if any(term in text for term in ["theory", "theorem", "bound", "proof", "game theoretic", "mechanism design"]):
        return "theory", ["theory or formal-model signal"]
    if paper.citation_count >= 250 and paper.year and paper.year <= 2021:
        return "seminal", ["older highly cited paper; likely canonical or seminal"]
    if paper.year >= 2024 and _topic_relevance(topic, paper) >= 0.45:
        return "frontier", ["recent and directly relevant"]
    if any(term in text for term in ["method", "algorithm", "model", "framework", "approach", "propose", "introduce"]):
        return "method", ["method or algorithm signal"]
    reasons.append("no strong role signal")
    return "unclear", reasons


def _score_paper(
    topic: str,
    paper: Paper,
    *,
    state: ResearchRunState | None,
    query_purpose: str,
    recency_preference: str,
) -> PaperRankingDecision:
    role, role_reasons = infer_paper_role(topic, paper, state=state)
    relevance = _topic_relevance(topic, paper)
    recency = _recency_score(paper.year, recency_preference)
    citations = min(math.log1p(max(paper.citation_count, 0)) / math.log(1001), 1.0)
    authority = _authority_score(paper)
    full_text = 1.0 if _has_full_text(paper.id, state) else 0.0
    novelty = _novelty_importance(paper.id, state)
    adjacent = _adjacent_transfer_importance(paper.id, state)
    method_overlap = _method_metric_dataset_overlap(topic, paper)
    role_bonus = ROLE_BONUS.get(role, 0.1)
    score = (
        relevance * 34
        + recency * 12
        + citations * 12
        + authority * 8
        + role_bonus * 10
        + full_text * 5
        + novelty * 9
        + adjacent * 7
        + method_overlap * 8
    )
    if role in {"seminal", "survey"} and citations >= 0.45:
        score += 8
    if query_purpose in {"novelty", "citation_expansion"} and novelty:
        score += 6
    if query_purpose == "analogy" and adjacent:
        score += 6
    return PaperRankingDecision(
        paper_id=paper.id,
        title=paper.title,
        score=round(min(100.0, score), 2),
        paper_role=role,
        role_reasons=role_reasons,
        source=paper.source,
        relevance_score=round(relevance, 3),
        recency_score=round(recency, 3),
        citation_score=round(citations, 3),
        authority_score=round(authority, 3),
        full_text_score=full_text,
        novelty_score=novelty,
        adjacent_transfer_score=adjacent,
    )


ROLE_BONUS = {
    "frontier": 0.9,
    "seminal": 0.9,
    "survey": 0.85,
    "benchmark": 0.85,
    "dataset": 0.75,
    "method": 0.65,
    "theory": 0.6,
    "negative_result": 0.55,
    "adjacent_field": 0.55,
    "unclear": 0.1,
}


def _apply_diversity(
    decisions: list[PaperRankingDecision],
    source_target: int,
    role_target: int,
) -> list[PaperRankingDecision]:
    selected: list[PaperRankingDecision] = []
    remaining = list(decisions)
    source_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    while remaining:
        best = max(
            remaining,
            key=lambda decision: (
                decision.score
                - max(0, source_counts[decision.source] - source_target + 1) * 5
                - max(0, role_counts[decision.paper_role] - role_target + 1) * 4
            ),
        )
        remaining.remove(best)
        if source_counts[best.source] >= source_target:
            best.source_diversity_reason = f"source {best.source or 'unknown'} already represented; diversity penalty applied"
        else:
            best.source_diversity_reason = f"source {best.source or 'unknown'} contributes diversity"
        if role_counts[best.paper_role] >= role_target:
            best.role_diversity_reason = f"role {best.paper_role} already represented; diversity penalty applied"
        else:
            best.role_diversity_reason = f"role {best.paper_role} contributes role coverage"
        selected.append(best)
        source_counts[best.source] += 1
        role_counts[best.paper_role] += 1
    return selected


def _paper_text(paper: Paper) -> str:
    return " ".join([paper.title, paper.abstract, paper.venue, paper.source, " ".join(paper.keywords)]).lower()


def _topic_relevance(topic: str, paper: Paper) -> float:
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return 0.0
    paper_tokens = set(_tokens(_paper_text(paper)))
    return sum(1 for token in topic_tokens if token in paper_tokens) / len(topic_tokens)


def _recency_score(year: int, preference: str) -> float:
    if not year:
        return 0.2
    if preference == "canonical":
        return 0.65 if year < 2020 else 0.5
    if year >= 2025:
        return 1.0
    if year >= 2022:
        return 0.8
    if year >= 2018:
        return 0.55
    if year >= 2012:
        return 0.35
    return 0.2


def _authority_score(paper: Paper) -> float:
    venue = paper.venue.lower()
    if any(term in venue for term in AUTHORITATIVE_VENUE_TERMS):
        return 1.0
    if paper.source.lower() in {"semantic scholar", "crossref", "dblp", "openreview", "arxiv"}:
        return 0.5
    return 0.2 if paper.source else 0.0


def _has_full_text(paper_id: str, state: ResearchRunState | None) -> bool:
    if state is None:
        return False
    return any(section.paper_id == paper_id and section.text.strip() for section in state.paper_sections)


def _novelty_importance(paper_id: str, state: ResearchRunState | None) -> float:
    if state is None:
        return 0.0
    prior_text = " ".join(work for assessment in state.novelty_assessments for work in assessment.closest_prior_work)
    dossier_text = " ".join(work for dossier in state.novelty_dossiers for work in dossier.top_prior_work)
    if paper_id in prior_text or paper_id in dossier_text:
        return 1.0
    if state.citation_graph and any(
        edge.source_paper_id == paper_id or edge.target_paper_id == paper_id for edge in state.citation_graph.edges
    ):
        return 0.5
    return 0.0


def _adjacent_transfer_importance(paper_id: str, state: ResearchRunState | None) -> float:
    if state is None:
        return 0.0
    if any(paper_id in transfer.source_paper_ids for transfer in state.cross_domain_transfers):
        return 1.0
    if any(paper_id in analogy.source_paper_ids for analogy in state.cross_domain_analogies):
        return 0.7
    return 0.0


def _is_adjacent_field(paper: Paper, state: ResearchRunState | None) -> bool:
    if state is None:
        return False
    return _adjacent_transfer_importance(paper.id, state) > 0


def _method_metric_dataset_overlap(topic: str, paper: Paper) -> float:
    topic_terms = _tokens(topic)
    if not topic_terms:
        return 0.0
    text = _paper_text(paper)
    important_terms = {"metric", "dataset", "benchmark", "method", "false", "positive", "calibration", "specificity", "baseline"}
    topic_important = [term for term in topic_terms if term in important_terms or term in text]
    if not topic_important:
        return 0.0
    return min(1.0, sum(1 for term in topic_important if term in text) / len(topic_important))


def _tokens(text: str) -> list[str]:
    stop = {"and", "for", "from", "that", "this", "with", "under", "paper", "study"}
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stop and len(token) > 2]


def ranking_provenance_source_ids(result: PaperRankingResult) -> list[str]:
    return [decision.paper_id for decision in result.decisions]
