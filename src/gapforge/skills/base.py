"""Base interfaces for modular research skills."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gapforge.models import ResearchRunState


class Skill(ABC):
    name: str

    @abstractmethod
    def run(self, state: ResearchRunState) -> ResearchRunState:
        """Apply this skill to a run state."""

    def mark_complete(self, state: ResearchRunState) -> None:
        if self.name not in state.completed_skills:
            state.completed_skills.append(self.name)
