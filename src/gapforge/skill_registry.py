"""Registry for built-in research skills."""

from __future__ import annotations

from gapforge.config import GapForgeConfig
from gapforge.skills import (
    CrossDomainAnalogy,
    DeepReading,
    DeepReadingLLM,
    ExperimentDesigner,
    GapMining,
    GapMiningLLM,
    LiteratureCartographer,
    NoveltyGate,
    NoveltyGateLLM,
    PaperTriage,
    ReviewerSimulation,
)
from gapforge.skills.base import Skill
from gapforge.sources import ArxivSource, CrossrefSource, DblpSource, OpenReviewSource, SemanticScholarSource, WebSource
from gapforge.sources.http_client import CachedHttpClient


def default_sources(config: GapForgeConfig | None = None):
    http = CachedHttpClient((config or GapForgeConfig.from_cwd()).cache_dir)
    return [
        ArxivSource(http),
        CrossrefSource(http),
        DblpSource(http),
        OpenReviewSource(http),
        SemanticScholarSource(http),
        WebSource(),
    ]


class SkillRegistry:
    def __init__(self, config: GapForgeConfig | None = None) -> None:
        sources = default_sources(config)
        self._skills: dict[str, Skill] = {
            "literature-cartographer": LiteratureCartographer(sources),
            "paper-triage": PaperTriage(),
            "deep-reading": DeepReading(),
            "deep-reading-llm": DeepReadingLLM(),
            "gap-mining": GapMining(),
            "gap-mining-llm": GapMiningLLM(),
            "cross-domain-analogy": CrossDomainAnalogy(sources),
            "novelty-gate": NoveltyGate(sources),
            "novelty-gate-llm": NoveltyGateLLM(),
            "experiment-designer": ExperimentDesigner(),
            "reviewer-simulation": ReviewerSimulation(),
        }

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def ordered(self) -> list[Skill]:
        return list(self._skills.values())
