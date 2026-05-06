"""Coverage target extraction for planned literature searches."""

from __future__ import annotations

from gapforge.models import SourcePolicyProfile


def coverage_targets_for_profile(profile: SourcePolicyProfile) -> dict[str, object]:
    return {
        "minimum_papers": profile.minimum_papers,
        "minimum_full_text_papers": profile.minimum_full_text_papers,
        "minimum_surveys": profile.minimum_surveys,
        "minimum_citation_expansion_rounds": profile.minimum_citation_expansion_rounds,
        "recency_window_years": profile.recency_window_years,
        "novelty_search_requirements": list(profile.novelty_search_requirements),
        "adjacent_field_requirements": list(profile.adjacent_field_requirements),
        "required_sources": list(profile.required_sources),
        "recommended_sources": list(profile.recommended_sources),
    }
