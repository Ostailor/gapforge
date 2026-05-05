"""Usage and budget tracking for optional LLM calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.llm.base import LLMResponse
from gapforge.llm.config import LLMRuntimeConfig


@dataclass(slots=True)
class LLMUsageRecord:
    call_id: str
    model: str
    prompt_chars: int = 0
    completion_chars: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(slots=True)
class LLMUsageSummary:
    calls: int = 0
    prompt_chars: int = 0
    completion_chars: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    budget_usd: float | None = None
    warnings: list[str] = field(default_factory=list)
    records: list[LLMUsageRecord] = field(default_factory=list)


class LLMBudgetTracker:
    """Append-only usage tracker persisted per run."""

    def __init__(self, run_dir: str | Path | None = None, *, config: LLMRuntimeConfig | None = None) -> None:
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.config = config or LLMRuntimeConfig.from_env()
        self.summary = self._load()

    def record(self, call_id: str, prompt: str, response: LLMResponse) -> LLMUsageSummary:
        usage = response.usage
        prompt_chars = int(usage.get("prompt_chars", len(prompt)))
        completion_chars = int(usage.get("completion_chars", len(response.text)))
        prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", _estimate_tokens(prompt_chars))))
        completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", _estimate_tokens(completion_chars))))
        estimated_cost = float(usage.get("estimated_cost_usd", _estimate_cost(prompt_tokens, completion_tokens)))
        record = LLMUsageRecord(
            call_id=call_id,
            model=response.model,
            prompt_chars=prompt_chars,
            completion_chars=completion_chars,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost,
        )
        self.summary.records.append(record)
        self.summary.calls += 1
        self.summary.prompt_chars += prompt_chars
        self.summary.completion_chars += completion_chars
        self.summary.prompt_tokens += prompt_tokens
        self.summary.completion_tokens += completion_tokens
        self.summary.estimated_cost_usd += estimated_cost
        self.summary.budget_usd = self.config.budget_usd
        if self.config.budget_usd is not None and self.summary.estimated_cost_usd > self.config.budget_usd:
            warning = f"LLM budget exceeded: estimated ${self.summary.estimated_cost_usd:.4f} > budget ${self.config.budget_usd:.4f}."
            if warning not in self.summary.warnings:
                self.summary.warnings.append(warning)
        self.save()
        return self.summary

    def save(self) -> None:
        if self.run_dir is None:
            return
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "llm_usage.json").write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.summary.calls,
            "prompt_chars": self.summary.prompt_chars,
            "completion_chars": self.summary.completion_chars,
            "prompt_tokens": self.summary.prompt_tokens,
            "completion_tokens": self.summary.completion_tokens,
            "estimated_cost_usd": round(self.summary.estimated_cost_usd, 8),
            "budget_usd": self.summary.budget_usd,
            "warnings": self.summary.warnings,
            "records": [asdict(record) for record in self.summary.records],
        }

    def _load(self) -> LLMUsageSummary:
        if self.run_dir is None:
            return LLMUsageSummary(budget_usd=self.config.budget_usd)
        path = self.run_dir / "llm_usage.json"
        if not path.exists():
            return LLMUsageSummary(budget_usd=self.config.budget_usd)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LLMUsageSummary(
            calls=int(raw.get("calls", 0)),
            prompt_chars=int(raw.get("prompt_chars", 0)),
            completion_chars=int(raw.get("completion_chars", 0)),
            prompt_tokens=int(raw.get("prompt_tokens", 0)),
            completion_tokens=int(raw.get("completion_tokens", 0)),
            estimated_cost_usd=float(raw.get("estimated_cost_usd", 0.0)),
            budget_usd=raw.get("budget_usd", self.config.budget_usd),
            warnings=list(raw.get("warnings", [])),
            records=[LLMUsageRecord(**item) for item in raw.get("records", [])],
        )


def _estimate_tokens(chars: int) -> int:
    return max(1, int(chars / 4))


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * 0.0000005) + (completion_tokens * 0.0000015)
