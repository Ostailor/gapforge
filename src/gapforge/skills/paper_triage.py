"""Rank papers into reading-depth tiers."""

from __future__ import annotations

import math
import re
from collections import Counter

from gapforge.claim_ledger import ClaimLedger
from gapforge.models import (
    Evidence,
    Paper,
    PaperNote,
    PaperTriageDecision,
    PaperTriageResult,
    Provenance,
    ResearchRunState,
)
from gapforge.skills.base import Skill
from gapforge.sources.ranking_v2 import infer_paper_role, rank_papers_v2
from gapforge.state import utc_now_iso

AUTHORITATIVE_VENUE_TERMS = {
    "nature",
    "science",
    "neurips",
    "icml",
    "iclr",
    "acl",
    "emnlp",
    "cvpr",
    "kdd",
    "www",
    "sigir",
    "chi",
    "usenix",
    "sigmod",
    "vldb",
    "jmlr",
    "pnas",
}

BENCHMARK_TERMS = {"benchmark", "dataset", "corpus", "evaluation", "leaderboard", "ground truth", "labels"}
NOVELTY_TERMS = {"novel", "new", "first", "propose", "introduce", "framework", "architecture"}
LIMITATION_TERMS = {"limitation", "future work", "open problem", "challenge", "gap", "fails", "failure"}
METHOD_TERMS = {"method", "model", "algorithm", "graph", "neural", "calibration", "abstention", "detector"}


class PaperTriage(Skill):
    name = "paper-triage"

    def __init__(self, max_tier1: int = 20) -> None:
        self.max_tier1 = max_tier1

    def run(self, state: ResearchRunState) -> ResearchRunState:
        ranking = rank_papers_v2(state.topic.text, state.papers, state=state)
        state.paper_ranking = ranking
        triage = self.triage(state.topic.text, state.papers, max_tier1=self.max_tier1, state=state)
        state.paper_triage = triage
        state.paper_notes = self._notes_for_selected_papers(state, triage)
        state.claims = self._add_triage_claims(state, triage).claims
        self.mark_complete(state)
        return state

    def triage(
        self,
        topic: str,
        papers: list[Paper],
        *,
        max_tier1: int | None = None,
        state: ResearchRunState | None = None,
    ) -> PaperTriageResult:
        max_tier1 = max_tier1 if max_tier1 is not None else self.max_tier1
        ranking = (
            state.paper_ranking if state is not None and state.paper_ranking is not None else rank_papers_v2(topic, papers, state=state)
        )
        ranking_by_id = {decision.paper_id: decision for decision in ranking.decisions}
        scored = [self.score_paper(topic, paper, state=state, ranking_decision=ranking_by_id.get(paper.id)) for paper in papers]
        scored.sort(key=lambda decision: (decision.score, _role_priority(decision.paper_role)), reverse=True)
        decisions = _assign_tiers_with_diversity(scored, papers, max_tier1=max_tier1)
        tier_counts = Counter(decision.tier for decision in decisions)
        return PaperTriageResult(
            topic=topic,
            decisions=decisions,
            tier_counts={tier: tier_counts.get(tier, 0) for tier in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]},
            max_tier1=max_tier1,
            scoring_summary=(
                "Deterministic triage scored papers by topic relevance, v0.2 ranking score, paper role, recency, venue authority, "
                "citation importance, benchmark/survey/canonical signals, full-text availability, source diversity, novelty-checking "
                "importance, and cross-domain transfer importance."
            ),
            limitations=[
                "Heuristic scoring cannot replace expert judgment.",
                "Citation counts and venue labels may be missing or uneven across sources.",
                "Tier decisions are reading-priority recommendations, not claims about paper quality.",
            ],
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=[paper.id for paper in papers],
                timestamp=utc_now_iso(),
                reasoning_summary="Deterministic triage ranked papers into reading-depth tiers using metadata and abstract cues.",
            ),
        )

    def score_paper(
        self,
        topic: str,
        paper: Paper,
        *,
        state: ResearchRunState | None = None,
        ranking_decision=None,
    ) -> PaperTriageDecision:
        reasons: list[str] = []
        concerns: list[str] = []
        score = 0.0
        role, role_reasons = infer_paper_role(topic, paper, state=state)
        if ranking_decision is not None:
            role = ranking_decision.paper_role
            role_reasons = ranking_decision.role_reasons
            score += ranking_decision.score * 0.35
            reasons.append(f"ranking-v2 score {ranking_decision.score:.2f}")

        relevance = _topic_relevance(topic, paper)
        score += relevance * 28
        if relevance >= 0.65:
            reasons.append("high topic relevance")
        elif relevance < 0.25:
            concerns.append("weak lexical overlap with topic")

        directness = _directness(topic, paper)
        score += directness * 18
        if directness >= 0.7:
            reasons.append("directly addresses the user topic")

        recency = _recency_score(paper.year)
        score += recency * 14
        if recency >= 0.7:
            reasons.append("recent paper")
        elif paper.year and paper.year < 2018:
            concerns.append("older paper; may be useful mainly for background")

        venue_score = _venue_score(paper.venue)
        score += venue_score * 10
        if venue_score:
            reasons.append(f"authoritative venue signal: {paper.venue}")

        citation_score = min(math.log1p(max(paper.citation_count, 0)) / math.log(501), 1.0)
        score += citation_score * 10
        if paper.citation_count >= 50:
            reasons.append("citation importance signal")
        elif paper.citation_count == 0:
            concerns.append("citation importance unavailable or zero")

        benchmark_score = _term_presence(paper, BENCHMARK_TERMS)
        score += benchmark_score * 8
        if benchmark_score:
            reasons.append("mentions benchmark, dataset, labels, or evaluation")

        novelty_score = _term_presence(paper, NOVELTY_TERMS | METHOD_TERMS)
        score += novelty_score * 7
        if novelty_score:
            reasons.append("contains method or novelty signals")

        limitation_score = _term_presence(paper, LIMITATION_TERMS)
        score += limitation_score * 5
        if limitation_score:
            reasons.append("mentions limitations, future work, open problems, or challenges")

        if role in {"seminal", "survey"}:
            score += 10
            reasons.append(f"{role} paper should anchor literature context")
        elif role in {"benchmark", "dataset"}:
            score += 8
            reasons.append(f"{role} paper is important for evaluation design")
        elif role == "frontier":
            score += 7
            reasons.append("frontier paper captures current direction")
        elif role == "adjacent_field":
            score += 5
            reasons.append("adjacent-field paper may support transfer candidate")
        elif role == "negative_result":
            score += 5
            reasons.append("negative-result paper can prevent overclaiming")

        important_for_novelty = _important_for_novelty(paper.id, state) or role in {"seminal", "survey"}
        important_for_transfer = _important_for_transfer(paper.id, state) or role == "adjacent_field"
        should_download = bool(paper.pdf_url or paper.arxiv_id or paper.openreview_id) and (
            relevance >= 0.35 or role in {"seminal", "survey", "benchmark", "dataset", "adjacent_field"} or important_for_novelty
        )
        if important_for_novelty:
            score += 6
            reasons.append("important for novelty checking or closest-prior-work positioning")
        if important_for_transfer:
            score += 5
            reasons.append("important for cross-domain transfer validation")
        if _has_full_text(paper.id, state):
            score += 4
            reasons.append("parsed full text is available")

        if not paper.abstract:
            concerns.append("missing abstract limits triage confidence")
        if not paper.venue:
            concerns.append("venue metadata unavailable")

        score = max(0.0, min(100.0, score))
        return PaperTriageDecision(
            paper_id=paper.id,
            title=paper.title,
            tier="Unassigned",
            score=round(score, 2),
            reasons=_dedupe(reasons),
            concerns=_dedupe(concerns),
            recommended_reading_depth="pending tier assignment",
            paper_role=role,
            why_this_role="; ".join(role_reasons),
            source_coverage_reason=_source_coverage_reason(paper, state),
            should_download_full_text=should_download,
            important_for_novelty_checking=important_for_novelty,
            important_for_cross_domain_transfer=important_for_transfer,
        )

    def _notes_for_selected_papers(self, state: ResearchRunState, triage: PaperTriageResult) -> list[PaperNote]:
        by_id = {paper.id: paper for paper in state.papers}
        notes: list[PaperNote] = []
        for decision in triage.decisions:
            if decision.tier not in {"Tier 1", "Tier 2"}:
                continue
            paper = by_id.get(decision.paper_id)
            if paper is None:
                continue
            notes.append(
                PaperNote(
                    paper_id=paper.id,
                    citation_key=_citation_key(paper),
                    one_sentence_summary=f"{decision.tier} triage: {paper.title}.",
                    relevance_to_topic=", ".join(decision.reasons[:3]) or "Selected by deterministic triage.",
                    confidence="medium" if paper.abstract else "low",
                    quotes_or_evidence_snippets=[
                        Evidence(
                            source_id=paper.id,
                            source_paper_id=paper.id,
                            quote=(paper.abstract or paper.title)[:500],
                            locator=paper.url or paper.id,
                            confidence="medium" if paper.abstract else "low",
                            notes=f"Recommended depth: {decision.recommended_reading_depth}",
                        )
                    ],
                    created_by_skill=self.name,
                    source_basis="metadata/abstract only",
                    summary=f"{decision.tier} triage: {paper.title}.",
                    methods=[reason for reason in decision.reasons if "method" in reason or "novelty" in reason],
                    limitations=decision.concerns,
                    evidence=[
                        Evidence(
                            source_id=paper.id,
                            source_paper_id=paper.id,
                            quote=(paper.abstract or paper.title)[:500],
                            locator=paper.url or paper.id,
                            confidence="medium" if paper.abstract else "low",
                            notes=f"Recommended depth: {decision.recommended_reading_depth}",
                        )
                    ],
                    provenance=Provenance(
                        created_by_skill=self.name,
                        source_ids=[paper.id],
                        timestamp=utc_now_iso(),
                        reasoning_summary=f"Created paper note from {decision.tier} triage decision.",
                    ),
                )
            )
        return notes

    def _add_triage_claims(self, state: ResearchRunState, triage: PaperTriageResult) -> ClaimLedger:
        ledger = ClaimLedger(state.claims)
        tier1 = [decision for decision in triage.decisions if decision.tier == "Tier 1"]
        if not tier1:
            return ledger

        tier1_papers = [paper for decision in tier1 if (paper := _paper_by_id(state.papers, decision.paper_id)) is not None]
        top_sources = Counter(paper.source for paper in tier1_papers)
        source_names = [source for source in top_sources if source]
        claim = ledger.add_claim(
            f"The triage pass identified {len(tier1)} papers that deserve deep reading for {state.topic.text}.",
            "method",
            created_by_skill=self.name,
            confidence="medium" if len(tier1) >= 3 else "low",
            source_paper_ids=[decision.paper_id for decision in tier1],
            needs_verification=True,
            notes=f"Tier 1 sources represented: {', '.join(source_names) if source_names else 'unknown'}.",
            reasoning_summary="Claim describes the output of deterministic triage, not the truth of the papers' findings.",
        )
        for decision in tier1[:5]:
            paper = _paper_by_id(state.papers, decision.paper_id)
            if paper is None:
                continue
            ledger.add_evidence(
                claim.id,
                Evidence(
                    source_id=paper.id,
                    source_paper_id=paper.id,
                    quote=(paper.abstract or paper.title)[:500],
                    locator=paper.url or paper.id,
                    confidence="medium" if paper.abstract else "low",
                    notes=f"Score {decision.score:.2f}; {', '.join(decision.reasons[:3])}",
                ),
            )
        ledger.mark_uncertain(claim.id, confidence=claim.confidence)
        return ledger


def _assign_tiers_with_diversity(
    decisions: list[PaperTriageDecision],
    papers: list[Paper],
    *,
    max_tier1: int,
) -> list[PaperTriageDecision]:
    by_id = {paper.id: paper for paper in papers}
    tier1_limit = min(max_tier1, max(1, len(decisions)))
    tier1: list[PaperTriageDecision] = []
    remaining = list(decisions)
    source_counts: Counter[str] = Counter()
    venue_counts: Counter[str] = Counter()

    while remaining and len(tier1) < tier1_limit:
        candidate = _best_diverse_candidate(remaining, by_id, source_counts, venue_counts)
        remaining.remove(candidate)
        paper = by_id.get(candidate.paper_id)
        if paper is not None:
            source_counts[paper.source] += 1
            venue_counts[paper.venue] += 1
        tier1.append(candidate)

    ordered = tier1 + remaining
    for index, decision in enumerate(ordered):
        if decision in tier1 and decision.score >= 45:
            _set_tier(decision, "Tier 1", "read full paper deeply")
        elif decision.score >= 38 or (decision.score >= 28 and index < max(tier1_limit + 5, math.ceil(len(ordered) * 0.35))):
            _set_tier(decision, "Tier 2", "read method, results, and limitations")
        elif decision.score >= 24:
            _set_tier(decision, "Tier 3", "skim for related work and positioning")
        else:
            _set_tier(decision, "Tier 4", "metadata only")
    return ordered


def _best_diverse_candidate(
    decisions: list[PaperTriageDecision],
    by_id: dict[str, Paper],
    source_counts: Counter[str],
    venue_counts: Counter[str],
) -> PaperTriageDecision:
    def adjusted(decision: PaperTriageDecision) -> float:
        paper = by_id.get(decision.paper_id)
        if paper is None:
            return decision.score
        penalty = source_counts[paper.source] * 4 + venue_counts[paper.venue] * 2
        return decision.score - penalty

    return max(decisions, key=adjusted)


def _set_tier(decision: PaperTriageDecision, tier: str, depth: str) -> None:
    decision.tier = tier
    decision.recommended_reading_depth = depth
    if decision.paper_role == "adjacent_field" and tier in {"Tier 1", "Tier 2"}:
        decision.recommended_reading_depth = f"{depth}; read as adjacent-field transfer evidence"
    if decision.important_for_novelty_checking and tier != "Tier 4":
        decision.recommended_reading_depth = f"{decision.recommended_reading_depth}; inspect closest-prior-work positioning"


def _topic_relevance(topic: str, paper: Paper) -> float:
    topic_tokens = _tokens(topic)
    if not topic_tokens:
        return 0.0
    text_tokens = set(_tokens(_paper_text(paper)))
    overlap = sum(1 for token in topic_tokens if token in text_tokens)
    return overlap / len(topic_tokens)


def _directness(topic: str, paper: Paper) -> float:
    title = paper.title.lower()
    abstract = paper.abstract.lower()
    topic_norm = topic.lower()
    if topic_norm in title:
        return 1.0
    if topic_norm in abstract:
        return 0.8
    title_overlap = _topic_relevance(topic, Paper(id="", title=paper.title, authors=[], abstract="", year=paper.year))
    return min(0.7, title_overlap)


def _recency_score(year: int) -> float:
    if not year:
        return 0.2
    if year >= 2025:
        return 1.0
    if year >= 2022:
        return 0.8
    if year >= 2019:
        return 0.55
    if year >= 2015:
        return 0.35
    return 0.15


def _venue_score(venue: str) -> float:
    venue_norm = venue.lower()
    return 1.0 if any(term in venue_norm for term in AUTHORITATIVE_VENUE_TERMS) else 0.0


def _role_priority(role: str) -> int:
    return {
        "frontier": 9,
        "seminal": 9,
        "survey": 8,
        "benchmark": 8,
        "dataset": 7,
        "method": 6,
        "theory": 5,
        "negative_result": 5,
        "adjacent_field": 4,
        "unclear": 0,
    }.get(role, 0)


def _important_for_novelty(paper_id: str, state: ResearchRunState | None) -> bool:
    if state is None:
        return False
    return any(paper_id in item for assessment in state.novelty_assessments for item in assessment.closest_prior_work) or any(
        paper_id in item for dossier in state.novelty_dossiers for item in dossier.top_prior_work
    )


def _important_for_transfer(paper_id: str, state: ResearchRunState | None) -> bool:
    if state is None:
        return False
    return any(paper_id in transfer.source_paper_ids for transfer in state.cross_domain_transfers) or any(
        paper_id in analogy.source_paper_ids for analogy in state.cross_domain_analogies
    )


def _has_full_text(paper_id: str, state: ResearchRunState | None) -> bool:
    if state is None:
        return False
    return any(section.paper_id == paper_id and section.text.strip() for section in state.paper_sections)


def _source_coverage_reason(paper: Paper, state: ResearchRunState | None) -> str:
    if state is None or state.source_coverage is None:
        return f"source={paper.source or 'unknown'}; no source coverage report available"
    coverage = state.source_coverage
    if paper.id in coverage.papers_with_full_text:
        return f"source={paper.source or 'unknown'}; parsed full text available"
    if paper.id in coverage.papers_with_pdf:
        return f"source={paper.source or 'unknown'}; PDF available but may need parsing"
    if paper.id in coverage.papers_abstract_only:
        return f"source={paper.source or 'unknown'}; abstract-only evidence"
    return f"source={paper.source or 'unknown'}; coverage status not classified"


def _term_presence(paper: Paper, terms: set[str]) -> float:
    text = _paper_text(paper)
    return min(1.0, sum(1 for term in terms if term in text) / 2)


def _paper_text(paper: Paper) -> str:
    return " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords)]).lower()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z][a-z0-9]{2,}", text.lower()) if token not in {"the", "and", "for", "with"}]


def _paper_by_id(papers: list[Paper], paper_id: str) -> Paper | None:
    return next((paper for paper in papers if paper.id == paper_id), None)


def _citation_key(paper: Paper) -> str:
    author = paper.authors[0].split()[-1].lower() if paper.authors else "unknown"
    return f"{author}{paper.year or 'nd'}"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
