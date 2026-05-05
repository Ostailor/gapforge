"""Budget presets for active research loops."""

from __future__ import annotations

from gapforge.models import ResearchBudget


def budget_from_name(name: str) -> ResearchBudget:
    key = name.strip().lower()
    if key == "small":
        return ResearchBudget(
            max_papers=12,
            max_full_text_papers=4,
            max_queries=6,
            max_llm_calls=0,
            max_cost_usd=0.0,
            max_iterations=4,
            wall_clock_limit_minutes=10,
        )
    if key == "medium":
        return ResearchBudget(
            max_papers=40,
            max_full_text_papers=12,
            max_queries=20,
            max_llm_calls=8,
            max_cost_usd=5.0,
            max_iterations=8,
            wall_clock_limit_minutes=30,
        )
    if key == "large":
        return ResearchBudget(
            max_papers=100,
            max_full_text_papers=30,
            max_queries=60,
            max_llm_calls=24,
            max_cost_usd=20.0,
            max_iterations=14,
            wall_clock_limit_minutes=90,
        )
    raise ValueError(f"Unknown active-loop budget preset: {name}")
