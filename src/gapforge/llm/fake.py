"""Deterministic fake LLM client for tests and offline development."""

from __future__ import annotations

import json
from typing import Any

from gapforge.llm.base import LLMResponse
from gapforge.llm.schemas import schema_for


class FakeLLMClient:
    """A no-network client with stable responses."""

    model = "gapforge-fake-llm"

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        prompt_marker = " ".join(prompt.split())[:160]
        text = f"FAKE_LLM_RESPONSE temperature={temperature:.1f} max_tokens={max_tokens or 'none'} prompt={prompt_marker}"
        return LLMResponse(
            text=text,
            model=self.model,
            usage={"prompt_chars": len(prompt), "system_chars": len(system), "completion_chars": len(text)},
            raw={"temperature": temperature, "max_tokens": max_tokens},
        )

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        schema_for(schema_name)
        base: dict[str, Any] = {
            "schema_name": schema_name,
            "model": self.model,
            "confidence": "low",
            "reasoning_summary": "Deterministic fake output; no research conclusion was produced.",
        }
        if schema_name == "deep-reading":
            base.update({"paper_notes": [], "claims": [], "evidence_spans": [], "limitations": ["fake client did not read papers"]})
        elif schema_name == "gap-mining":
            base.update({"gaps": [], "claim_updates": [], "limitations": ["fake client did not mine gaps"]})
        elif schema_name == "novelty-gate":
            base.update(
                {
                    "target_id": _extract_target_id(prompt),
                    "closest_prior_work": [],
                    "comparison_table": [],
                    "what_is_new": [],
                    "what_is_not_new": [],
                    "possible_reviewer_objection": "Fake client cannot assess novelty.",
                    "decisive_difference_needed": "Run deterministic novelty gate or a real reviewed prior-work search.",
                    "missing_searches": ["fake client performs no searches"],
                    "verdict": "unknown",
                    "novelty_strength": "unknown",
                }
            )
        elif schema_name == "reviewer-simulation":
            base.update(
                {
                    "objections": [],
                    "submission_readiness_score": 0,
                    "final_recommendation": "not_ready",
                }
            )
        return json.loads(json.dumps(base, sort_keys=True))


def _extract_target_id(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.lower().startswith("target id:"):
            return line.split(":", 1)[1].strip()
    return "unknown"
