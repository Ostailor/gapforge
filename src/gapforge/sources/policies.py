"""Field-specific source coverage policies for v0.3 runs."""

from __future__ import annotations

from gapforge.models import ResearchRunState, SourcePolicyProfile


def default_source_policy_profiles() -> dict[str, SourcePolicyProfile]:
    """Return conservative built-in coverage profiles.

    Profiles are intentionally explicit and auditable. They are not claims that
    these sources are sufficient for exhaustive review; they define minimum
    gates before GapForge should trust mapping, gap, novelty, or experiment
    outputs for a field.
    """

    return {
        "machine_learning": SourcePolicyProfile(
            id="machine_learning",
            field_name="Machine Learning",
            required_sources=["arxiv", "semantic-scholar"],
            recommended_sources=["openreview", "dblp", "crossref"],
            venue_keywords=["neurips", "icml", "iclr", "acl", "emnlp", "cvpr", "aaai"],
            must_include_query_patterns=["survey", "benchmark"],
            recency_window_years=5,
            minimum_papers=20,
            minimum_full_text_papers=5,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=["analogy"],
        ),
        "ai_safety": SourcePolicyProfile(
            id="ai_safety",
            field_name="AI Safety",
            required_sources=["arxiv", "openreview", "semantic-scholar"],
            recommended_sources=["crossref", "dblp", "web"],
            venue_keywords=["neurips", "iclr", "icml", "aies", "facct", "safe", "alignment"],
            must_include_query_patterns=["survey", "benchmark", "evaluation", "threat model"],
            recency_window_years=4,
            minimum_papers=20,
            minimum_full_text_papers=6,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion", "related_work"],
            adjacent_field_requirements=["cybersecurity", "control theory", "mechanism design"],
        ),
        "multi_agent_systems": SourcePolicyProfile(
            id="multi_agent_systems",
            field_name="Multi-Agent Systems",
            required_sources=["arxiv", "semantic-scholar"],
            recommended_sources=["openreview", "dblp", "crossref"],
            venue_keywords=["aamas", "ijcai", "aaai", "neurips", "icml", "iclr"],
            must_include_query_patterns=["multi-agent", "game theory", "survey", "benchmark"],
            recency_window_years=6,
            minimum_papers=18,
            minimum_full_text_papers=5,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=["economics", "game theory"],
        ),
        "physics": SourcePolicyProfile(
            id="physics",
            field_name="Physics",
            required_sources=["arxiv", "crossref"],
            recommended_sources=["semantic-scholar"],
            venue_keywords=["physical review", "nature physics", "science", "jhep", "prl"],
            must_include_query_patterns=["review", "experiment"],
            recency_window_years=8,
            minimum_papers=15,
            minimum_full_text_papers=4,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=[],
        ),
        "biology": SourcePolicyProfile(
            id="biology",
            field_name="Biology",
            required_sources=["crossref", "semantic-scholar"],
            recommended_sources=["pubmed", "web"],
            venue_keywords=["nature", "science", "cell", "plos", "biorxiv"],
            must_include_query_patterns=["review", "dataset", "protocol"],
            recency_window_years=6,
            minimum_papers=20,
            minimum_full_text_papers=5,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=[],
        ),
        "economics": SourcePolicyProfile(
            id="economics",
            field_name="Economics",
            required_sources=["crossref", "semantic-scholar"],
            recommended_sources=["dblp", "web", "arxiv"],
            venue_keywords=["aer", "econometrica", "journal of political economy", "qje", "nber"],
            must_include_query_patterns=["survey", "empirical", "identification"],
            recency_window_years=8,
            minimum_papers=18,
            minimum_full_text_papers=4,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=[],
        ),
        "medicine": SourcePolicyProfile(
            id="medicine",
            field_name="Medicine",
            required_sources=["pubmed", "crossref"],
            recommended_sources=["semantic-scholar", "web"],
            venue_keywords=["jama", "lancet", "nejm", "bmj", "annals", "cochrane"],
            must_include_query_patterns=["systematic review", "screening", "clinical", "validation"],
            recency_window_years=5,
            minimum_papers=25,
            minimum_full_text_papers=6,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=["biostatistics", "epidemiology"],
        ),
        "cybersecurity": SourcePolicyProfile(
            id="cybersecurity",
            field_name="Cybersecurity",
            required_sources=["dblp", "semantic-scholar"],
            recommended_sources=["arxiv", "crossref", "web"],
            venue_keywords=["usenix", "ccs", "ndss", "oakland", "security", "privacy"],
            must_include_query_patterns=["survey", "benchmark", "threat model"],
            recency_window_years=5,
            minimum_papers=18,
            minimum_full_text_papers=5,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty", "citation_expansion"],
            adjacent_field_requirements=[],
        ),
        "generic": SourcePolicyProfile(
            id="generic",
            field_name="Generic Research",
            required_sources=["semantic-scholar"],
            recommended_sources=["arxiv", "crossref"],
            venue_keywords=[],
            must_include_query_patterns=["survey"],
            recency_window_years=6,
            minimum_papers=12,
            minimum_full_text_papers=3,
            minimum_surveys=1,
            minimum_citation_expansion_rounds=1,
            novelty_search_requirements=["novelty"],
            adjacent_field_requirements=[],
        ),
    }


def get_source_policy_profile(profile_id: str) -> SourcePolicyProfile:
    profiles = default_source_policy_profiles()
    key = profile_id.strip().lower().replace("-", "_")
    if key not in profiles:
        raise KeyError(f"Unknown source policy profile: {profile_id}")
    return profiles[key]


def infer_source_policy_profile(state: ResearchRunState) -> SourcePolicyProfile:
    """Infer a best-effort profile from topic and observed source context."""

    text = " ".join(
        [
            state.topic.text,
            " ".join(paper.title for paper in state.papers[:20]),
            " ".join(paper.venue for paper in state.papers[:20]),
        ]
    ).lower()
    profiles = default_source_policy_profiles()
    if any(term in text for term in ["safety", "alignment", "red team", "evasion", "agent", "llm"]):
        return profiles["ai_safety"]
    if any(term in text for term in ["multi-agent", "collusion", "cartel", "mechanism design", "game theory"]):
        return profiles["multi_agent_systems"]
    if any(term in text for term in ["medicine", "clinical", "screening", "diagnosis", "patient", "epidemiology"]):
        return profiles["medicine"]
    if any(term in text for term in ["cybersecurity", "intrusion", "malware", "covert channel", "steganography"]):
        return profiles["cybersecurity"]
    if any(term in text for term in ["biology", "genomics", "cell", "protein"]):
        return profiles["biology"]
    if any(term in text for term in ["economics", "cartel", "market", "auction"]):
        return profiles["economics"]
    if any(term in text for term in ["physics", "quantum", "particle", "statistical mechanics"]):
        return profiles["physics"]
    if any(term in text for term in ["machine learning", "ml", "benchmark", "dataset", "model"]):
        return profiles["machine_learning"]
    return profiles["generic"]
