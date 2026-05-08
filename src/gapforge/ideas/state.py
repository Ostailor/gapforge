"""Persistence envelope for v2 idea discovery state."""

from __future__ import annotations

from dataclasses import dataclass, field

from gapforge.ideas.models import (
    ConstructiveGapCandidate,
    IdeaBank,
    IdeaCandidate,
    IdeaEvidenceLink,
    IdeaFeedbackRecord,
    IdeaMutationRecord,
    IdeaNoveltyAssessment,
    IdeaPreferenceProfile,
    IdeaReviewRecord,
    IdeaSearchDecision,
    IdeaTournament,
    IdeaTransferCandidate,
    ResearchAgenda,
)


@dataclass(slots=True)
class IdeaDiscoveryState:
    idea_bank: IdeaBank | None = None
    candidates: list[IdeaCandidate] = field(default_factory=list)
    preference_profiles: list[IdeaPreferenceProfile] = field(default_factory=list)
    evidence_links: list[IdeaEvidenceLink] = field(default_factory=list)
    feedback_records: list[IdeaFeedbackRecord] = field(default_factory=list)
    novelty_assessments: list[IdeaNoveltyAssessment] = field(default_factory=list)
    reviews: list[IdeaReviewRecord] = field(default_factory=list)
    mutations: list[IdeaMutationRecord] = field(default_factory=list)
    constructive_gaps: list[ConstructiveGapCandidate] = field(default_factory=list)
    transfer_candidates: list[IdeaTransferCandidate] = field(default_factory=list)
    search_decisions: list[IdeaSearchDecision] = field(default_factory=list)
    tournaments: list[IdeaTournament] = field(default_factory=list)
    agendas: list[ResearchAgenda] = field(default_factory=list)
