"""v0.5 live-literature campaign profiles."""

from __future__ import annotations

from gapforge.models import Provenance, RealLiteratureCampaignProfile
from gapforge.state import utc_now_iso


def default_real_literature_profiles() -> list[RealLiteratureCampaignProfile]:
    now = utc_now_iso()
    common_artifacts = [
        "live_source_diagnostic_latest.md",
        "campaign_report.md",
        "source_coverage.md",
        "novelty_dossiers.md",
        "related_work_matrix.md",
    ]
    return [
        RealLiteratureCampaignProfile(
            id="live_low_fpr_collusion",
            title="Live low-FPR collusion literature campaign",
            topic="low false positive collusion detection in LLM agents",
            source_profile="ai_safety",
            required_live_sources=["arxiv", "openreview", "semantic-scholar"],
            recommended_live_sources=["crossref", "dblp", "web"],
            max_papers=60,
            max_expanded_papers=30,
            min_real_papers=12,
            min_full_text_or_abstract_notes=8,
            min_closest_prior_work=2,
            expected_artifacts=common_artifacts + ["gap_evidence_matrix.md", "experiment_protocols.md"],
            acceptance_criteria=[
                "Required AI-safety live sources are reachable and return non-fallback results.",
                "Campaign considers multiple closest-prior-work candidates before recommending a direction.",
                "Strict report refuses novelty if closest prior work or source coverage is weak.",
            ],
            known_risks=[
                "Frontier AI-safety work may appear in preprints, workshop papers, or blog-like venues.",
                "Terminology around collusion, monitors, and low false positives is inconsistent.",
            ],
            provenance=_profile_provenance(now),
        ),
        RealLiteratureCampaignProfile(
            id="live_llm_monitor_evasion",
            title="Live LLM monitor evasion literature campaign",
            topic="lexical substitution attacks against LLM monitor systems",
            source_profile="ai_safety",
            required_live_sources=["arxiv", "openreview", "semantic-scholar"],
            recommended_live_sources=["crossref", "dblp", "web"],
            max_papers=50,
            max_expanded_papers=25,
            min_real_papers=10,
            min_full_text_or_abstract_notes=7,
            min_closest_prior_work=2,
            expected_artifacts=common_artifacts + ["gap_evidence_matrix.md"],
            acceptance_criteria=[
                "Campaign separates monitor evasion, adversarial examples, jailbreaks, and lexical attacks.",
                "Novelty dossier lists closest prior work or marks novelty unknown.",
            ],
            known_risks=["Live sources may use security or NLP terminology rather than AI-safety terminology."],
            provenance=_profile_provenance(now),
        ),
        RealLiteratureCampaignProfile(
            id="live_multi_agent_covert_channels",
            title="Live multi-agent covert-channel literature campaign",
            topic="covert communication and collusion in multi-agent AI systems",
            source_profile="multi_agent_systems",
            required_live_sources=["arxiv", "semantic-scholar"],
            recommended_live_sources=["openreview", "crossref", "dblp", "web"],
            max_papers=60,
            max_expanded_papers=30,
            min_real_papers=12,
            min_full_text_or_abstract_notes=8,
            min_closest_prior_work=2,
            expected_artifacts=common_artifacts + ["citation_graph.md", "related_work_matrix.md"],
            acceptance_criteria=[
                "Campaign searches both AI multi-agent work and adjacent covert-channel/security literature.",
                "Closest prior work is explicit before any novelty claim.",
            ],
            known_risks=["Covert-channel prior work may live outside standard ML venues."],
            provenance=_profile_provenance(now),
        ),
        RealLiteratureCampaignProfile(
            id="live_specificity_cross_domain",
            title="Live specificity cross-domain literature campaign",
            topic="medical screening specificity methods for low false-positive AI safety monitoring",
            source_profile="medicine",
            required_live_sources=["crossref", "semantic-scholar"],
            recommended_live_sources=["arxiv", "web", "dblp"],
            max_papers=70,
            max_expanded_papers=35,
            min_real_papers=15,
            min_full_text_or_abstract_notes=10,
            min_closest_prior_work=2,
            expected_artifacts=common_artifacts + ["cross_domain_transfers.md", "experiment_protocols.md"],
            acceptance_criteria=[
                "Campaign distinguishes medical screening specificity evidence from AI-safety target evidence.",
                "Cross-domain transfer candidate is evidence-backed and states what breaks.",
            ],
            known_risks=[
                "GapForge has no first-class PubMed connector yet; medicine profile may require explicit source warnings.",
                "Cross-domain analogy must not be treated as proof of an AI-safety result.",
            ],
            provenance=_profile_provenance(now),
        ),
        RealLiteratureCampaignProfile(
            id="live_undercovered_refusal",
            title="Live undercovered-topic refusal campaign",
            topic=("an intentionally narrow topic where GapForge should refuse to recommend a direction if evidence is insufficient"),
            source_profile="generic",
            required_live_sources=["semantic-scholar"],
            recommended_live_sources=["crossref", "arxiv", "web"],
            max_papers=15,
            max_expanded_papers=5,
            min_real_papers=3,
            min_full_text_or_abstract_notes=0,
            min_closest_prior_work=0,
            expected_artifacts=["live_source_diagnostic_latest.md", "campaign_report.md", "strict refusal or no-ready-direction record"],
            acceptance_criteria=[
                "Campaign may pass by correctly refusing to recommend a direction when live evidence is insufficient.",
                "Offline or disabled-source runs do not count as live-literature acceptance.",
            ],
            known_risks=["This profile validates conservative refusal, not positive research ideation quality."],
            provenance=_profile_provenance(now),
        ),
    ]


def get_real_literature_profile(profile_id: str) -> RealLiteratureCampaignProfile:
    for profile in default_real_literature_profiles():
        if profile.id == profile_id:
            return profile
    raise KeyError(f"Unknown real literature campaign profile: {profile_id}")


def render_real_literature_plan(profile: RealLiteratureCampaignProfile) -> str:
    commands = [
        f"gapforge live-source-diagnostic --topic {profile.topic!r} --source-profile {profile.source_profile} --write-report",
        f"gapforge real-literature-run --profile {profile.id}",
        "gapforge real-literature-status --record-id <record-id>",
    ]
    lines = [
        f"# Real Literature Campaign Plan: {profile.id}",
        "",
        f"- Title: {profile.title}",
        f"- Topic: {profile.topic}",
        f"- Source profile: `{profile.source_profile}`",
        f"- Required live sources: {', '.join(profile.required_live_sources) or 'none'}",
        f"- Recommended live sources: {', '.join(profile.recommended_live_sources) or 'none'}",
        f"- Max papers: {profile.max_papers}",
        f"- Max expanded papers: {profile.max_expanded_papers}",
        f"- Minimum real papers: {profile.min_real_papers}",
        f"- Minimum full-text or abstract notes: {profile.min_full_text_or_abstract_notes}",
        f"- Minimum closest prior work items: {profile.min_closest_prior_work}",
        "",
        "## Recommended Commands",
        "",
    ]
    lines.extend(f"```bash\n{command}\n```" for command in commands)
    lines.extend(["", "## Expected Artifacts", ""])
    lines.extend(f"- {artifact}" for artifact in profile.expected_artifacts)
    lines.extend(["", "## Acceptance Criteria", ""])
    lines.extend(f"- {criterion}" for criterion in profile.acceptance_criteria)
    lines.extend(["", "## Known Risks", ""])
    lines.extend(f"- {risk}" for risk in profile.known_risks)
    lines.extend(
        [
            "",
            "These profiles are for live-literature campaign quality. They are not normal CI targets, and "
            "fixture-only/fake-agent runs do not satisfy them.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _profile_provenance(timestamp: str) -> Provenance:
    return Provenance(
        created_by_skill="real-literature-profile",
        timestamp=timestamp,
        reasoning_summary="Defined a v0.5 live-literature campaign quality profile.",
    )
