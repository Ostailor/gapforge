"""Deterministic fake LLM client for tests and offline development."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from gapforge.llm.base import LLMResponse
from gapforge.llm.budget import LLMBudgetTracker
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.json_guard import JSONGuard
from gapforge.llm.transcripts import LLMTranscriptLogger


class FakeLLMClient:
    """A no-network client with stable responses."""

    model = "gapforge-fake-llm"

    def __init__(
        self,
        *,
        run_dir: str | Path | None = None,
        skill_name: str = "fake",
        prompt_pack_id: str = "",
        config: LLMRuntimeConfig | None = None,
    ) -> None:
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.skill_name = skill_name
        self.prompt_pack_id = prompt_pack_id
        self.config = config or LLMRuntimeConfig.from_env()
        self.budget = LLMBudgetTracker(self.run_dir, config=self.config)
        self.transcripts = LLMTranscriptLogger(self.run_dir)

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
        response = LLMResponse(
            text=text,
            model=self.model,
            usage={"prompt_chars": len(prompt), "system_chars": len(system), "completion_chars": len(text)},
            raw={"temperature": temperature, "max_tokens": max_tokens},
        )
        call_id = f"llm-fake-{uuid.uuid4().hex[:12]}"
        self.budget.record(call_id, prompt, response)
        self.transcripts.record(
            call_id=call_id,
            skill_name=self.skill_name,
            prompt_pack_id=self.prompt_pack_id,
            model=self.model,
            response_status="ok",
            prompt=prompt,
            response=response,
            reasoning_summary="Deterministic fake LLM response for offline testing.",
            usage=self.budget.to_dict(),
        )
        return response

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        reasoning_summary = "Deterministic fake output; no research conclusion was produced."
        base: dict[str, Any] = {}
        if schema_name == "deep-reading":
            base.update({"paper_notes": [], "claims": [], "evidence_spans": [], "limitations": ["fake client did not read papers"]})
        elif schema_name == "gap-mining":
            base.update({"gaps": [], "claim_updates": [], "limitations": ["fake client did not mine gaps or counterevidence"]})
        elif schema_name in {"novelty-gate", "novelty-comparison"}:
            base.update(
                {
                    "confidence": "low",
                    "reasoning_summary": reasoning_summary,
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
                    "reasoning_summary": reasoning_summary,
                    "objections": [],
                    "submission_readiness_score": 0,
                    "final_recommendation": "not_ready",
                }
            )
        response_text = json.dumps(base, sort_keys=True)
        response = LLMResponse(
            text=response_text,
            model=self.model,
            usage={"prompt_chars": len(prompt), "system_chars": len(system), "completion_chars": len(response_text)},
            raw={"temperature": temperature, "max_tokens": max_tokens, "schema_name": schema_name},
        )
        call_id = f"llm-fake-{uuid.uuid4().hex[:12]}"
        self.budget.record(call_id, prompt, response)
        self.transcripts.record(
            call_id=call_id,
            skill_name=self.skill_name,
            prompt_pack_id=self.prompt_pack_id,
            model=self.model,
            schema_name=schema_name,
            response_status="ok",
            prompt=prompt,
            response=response,
            reasoning_summary=str(base.get("reasoning_summary", reasoning_summary)),
            usage=self.budget.to_dict(),
        )
        return JSONGuard().parse_and_validate(response_text, schema_name=schema_name).data


def _extract_target_id(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.lower().startswith("target id:"):
            return line.split(":", 1)[1].strip()
    return "unknown"
