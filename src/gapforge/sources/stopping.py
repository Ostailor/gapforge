"""Policy-aware literature coverage stopping criteria."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from gapforge.models import CoverageStoppingAssessment, Provenance, ResearchRunState, SourcePolicyProfile
from gapforge.sources.coverage import generate_source_coverage
from gapforge.sources.policies import get_source_policy_profile, infer_source_policy_profile


def assess_literature_coverage(
    state: ResearchRunState,
    *,
    profile: SourcePolicyProfile | str | None = None,
) -> CoverageStoppingAssessment:
    """Assess whether current search coverage is sufficient for each research stage."""

    resolved_profile = _resolve_profile(state, profile)
    coverage = state.source_coverage or generate_source_coverage(state)
    seen_sources = {_normalize_source(source) for source in coverage.searched_sources}
    paper_count = sum(coverage.papers_by_source.values())
    full_text_count = len(coverage.papers_with_full_text)
    survey_count = _survey_count(state)
    citation_rounds = _citation_expansion_rounds(state)
    novelty_queries = _purpose_count(state, "novelty")
    related_queries = _purpose_count(state, "related_work") + _purpose_count(state, "citation_expansion")
    analogy_queries = _purpose_count(state, "analogy")
    missing: list[str] = []
    recommended: list[str] = []

    for source in resolved_profile.required_sources:
        normalized = _normalize_source(source)
        if normalized not in seen_sources:
            missing.append(f"required source not searched: {source}")
            recommended.append(f"{state.topic.text} source:{source}")

    for pattern in resolved_profile.must_include_query_patterns:
        if not _query_pattern_seen(state, pattern):
            missing.append(f"required query pattern not searched: {pattern}")
            recommended.append(f"{state.topic.text} {pattern}")

    if paper_count < resolved_profile.minimum_papers:
        missing.append(f"minimum papers not met: {paper_count}/{resolved_profile.minimum_papers}")
        recommended.append(f"{state.topic.text} recent papers")
    if full_text_count < resolved_profile.minimum_full_text_papers:
        missing.append(f"minimum full-text papers not met: {full_text_count}/{resolved_profile.minimum_full_text_papers}")
        recommended.append(f"{state.topic.text} pdf full text")
    if survey_count < resolved_profile.minimum_surveys:
        missing.append(f"minimum surveys/reviews not met: {survey_count}/{resolved_profile.minimum_surveys}")
        recommended.append(f"{state.topic.text} survey OR systematic review")
    if citation_rounds < resolved_profile.minimum_citation_expansion_rounds:
        missing.append(f"citation expansion rounds not met: {citation_rounds}/{resolved_profile.minimum_citation_expansion_rounds}")
        recommended.append(f"{state.topic.text} cited by related work")

    if "novelty" in resolved_profile.novelty_search_requirements and novelty_queries == 0:
        missing.append("novelty-specific closest-prior-work search has not run")
        recommended.append(f"{state.topic.text} closest prior work benchmark")
    if "citation_expansion" in resolved_profile.novelty_search_requirements and related_queries == 0:
        missing.append("citation/related-work expansion has not run")
        recommended.append(f"{state.topic.text} systematic related work")
    if "related_work" in resolved_profile.novelty_search_requirements and related_queries == 0:
        missing.append("related-work expansion has not run")
        recommended.append(f"{state.topic.text} related work survey")

    if resolved_profile.adjacent_field_requirements and analogy_queries == 0:
        missing.append("adjacent-field searches not run for: " + ", ".join(resolved_profile.adjacent_field_requirements[:4]))
        for field in resolved_profile.adjacent_field_requirements[:4]:
            recommended.append(f"{state.topic.text} {field}")

    if coverage.fallback_paper_count:
        missing.append("fallback/offline records are present; coverage cannot support final novelty claims")
    if coverage.failed_sources:
        missing.append("one or more required/recommended source searches failed: " + ", ".join(coverage.failed_sources))
    if _requires_unavailable_pubmed(resolved_profile, seen_sources):
        missing.append("PubMed-like source is required/recommended for this profile but no PubMed connector is available yet")
        recommended.append(f"{state.topic.text} PubMed systematic review")

    required_sources_ok = all(_normalize_source(source) in seen_sources for source in resolved_profile.required_sources)
    query_patterns_ok = all(_query_pattern_seen(state, pattern) for pattern in resolved_profile.must_include_query_patterns)
    enough_papers = paper_count >= resolved_profile.minimum_papers
    enough_full_text = full_text_count >= resolved_profile.minimum_full_text_papers
    enough_surveys = survey_count >= resolved_profile.minimum_surveys
    citation_ok = citation_rounds >= resolved_profile.minimum_citation_expansion_rounds
    novelty_ok = (
        novelty_queries > 0
        and citation_ok
        and related_queries > 0
        and coverage.confidence in {"medium", "high"}
        and not coverage.fallback_paper_count
    )
    enough_for_mapping = required_sources_ok and enough_papers and query_patterns_ok and coverage.confidence != "low"
    enough_for_gap_mining = enough_for_mapping and enough_full_text
    enough_for_novelty = enough_for_gap_mining and enough_surveys and novelty_ok
    enough_for_experiment_design = enough_for_novelty and not coverage.failed_sources

    confidence = _assessment_confidence(
        enough_for_mapping=enough_for_mapping,
        enough_for_gap_mining=enough_for_gap_mining,
        enough_for_novelty=enough_for_novelty,
        enough_for_experiment_design=enough_for_experiment_design,
        missing_count=len(missing),
    )
    return CoverageStoppingAssessment(
        run_id=state.run_id,
        project_id=str(state.config.get("project_id", "")),
        profile_id=resolved_profile.id,
        enough_for_mapping=enough_for_mapping,
        enough_for_gap_mining=enough_for_gap_mining,
        enough_for_novelty=enough_for_novelty,
        enough_for_experiment_design=enough_for_experiment_design,
        missing_requirements=_dedupe(missing),
        recommended_queries=_dedupe(recommended)[:20],
        confidence=confidence,
        provenance=Provenance(
            created_by_skill="source-policy",
            source_ids=[coverage.run_id],
            timestamp=datetime.now(UTC).isoformat(),
            reasoning_summary=(
                f"Assessed source coverage against {resolved_profile.id} profile using source counts, query ledger, "
                "full-text counts, survey presence, and citation/novelty search records."
            ),
        ),
    )


def refresh_stopping_assessment(
    state: ResearchRunState,
    *,
    profile: SourcePolicyProfile | str | None = None,
) -> CoverageStoppingAssessment:
    assessment = assess_literature_coverage(state, profile=profile)
    state.coverage_stopping_assessment = assessment
    return assessment


def render_stopping_assessment_markdown(assessment: CoverageStoppingAssessment) -> str:
    lines = [
        f"# Coverage Stopping Assessment: {assessment.profile_id}",
        "",
        f"- Run ID: `{assessment.run_id}`",
        f"- Project ID: `{assessment.project_id or 'none'}`",
        f"- Confidence: {assessment.confidence}",
        f"- Enough for mapping: {str(assessment.enough_for_mapping).lower()}",
        f"- Enough for gap mining: {str(assessment.enough_for_gap_mining).lower()}",
        f"- Enough for novelty: {str(assessment.enough_for_novelty).lower()}",
        f"- Enough for experiment design: {str(assessment.enough_for_experiment_design).lower()}",
        "",
        "## Missing Requirements",
        "",
    ]
    lines.extend([f"- {item}" for item in assessment.missing_requirements] or ["- none"])
    lines.extend(["", "## Recommended Searches", ""])
    lines.extend([f"- {query}" for query in assessment.recommended_queries] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _resolve_profile(state: ResearchRunState, profile: SourcePolicyProfile | str | None) -> SourcePolicyProfile:
    if isinstance(profile, SourcePolicyProfile):
        return profile
    if isinstance(profile, str) and profile.strip():
        return get_source_policy_profile(profile)
    configured = str(state.config.get("source_policy_profile", ""))
    if configured:
        return get_source_policy_profile(configured)
    return infer_source_policy_profile(state)


def _survey_count(state: ResearchRunState) -> int:
    count = 0
    for paper in state.papers:
        text = " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords), " ".join(paper.roles)]).lower()
        if any(term in text for term in ["survey", "systematic review", "review paper", "meta-analysis", "tutorial"]):
            count += 1
    return count


def _citation_expansion_rounds(state: ResearchRunState) -> int:
    purposes = Counter(record.purpose for record in state.search_queries)
    graph_round = 1 if state.citation_graph and state.citation_graph.edges else 0
    return max(graph_round, purposes.get("citation_expansion", 0), purposes.get("related_work", 0))


def _purpose_count(state: ResearchRunState, purpose: str) -> int:
    return sum(1 for record in state.search_queries if record.purpose == purpose)


def _query_pattern_seen(state: ResearchRunState, pattern: str) -> bool:
    normalized = pattern.lower()
    return any(normalized in record.query.lower() for record in state.search_queries)


def _requires_unavailable_pubmed(profile: SourcePolicyProfile, seen_sources: set[str]) -> bool:
    wants_pubmed = "pubmed" in {_normalize_source(source) for source in profile.required_sources + profile.recommended_sources}
    return wants_pubmed and "pubmed" not in seen_sources


def _assessment_confidence(
    *,
    enough_for_mapping: bool,
    enough_for_gap_mining: bool,
    enough_for_novelty: bool,
    enough_for_experiment_design: bool,
    missing_count: int,
) -> str:
    if enough_for_experiment_design:
        return "high"
    if enough_for_gap_mining or (enough_for_mapping and missing_count <= 3):
        return "medium"
    if enough_for_novelty:
        return "medium"
    return "low"


def _normalize_source(source: str) -> str:
    return source.strip().lower().replace(" ", "-").replace("_", "-")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
