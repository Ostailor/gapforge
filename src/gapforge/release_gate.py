"""Release-gate metadata parsing for auditable release notes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReleaseGateStatus:
    version: str
    actual_run_acceptance: str
    actual_run_acceptance_passed: bool
    accepted_real_canary_count: int = 0
    real_canaries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.actual_run_acceptance == "passed"
            and self.actual_run_acceptance_passed
            and self.accepted_real_canary_count > 0
            and any(item.get("status") == "accepted" for item in self.real_canaries)
        )


def parse_release_gate(path: str | Path) -> ReleaseGateStatus:
    """Parse JSON front matter from a release-gate Markdown file."""
    text = Path(path).read_text(encoding="utf-8")
    metadata = _parse_json_front_matter(text)
    return ReleaseGateStatus(
        version=str(metadata.get("version", "")),
        actual_run_acceptance=str(metadata.get("actual_run_acceptance", "not_completed")),
        actual_run_acceptance_passed=bool(metadata.get("actual_run_acceptance_passed", False)),
        accepted_real_canary_count=int(metadata.get("accepted_real_canary_count", 0)),
        real_canaries=list(metadata.get("real_canaries", [])),
    )


def _parse_json_front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("Release gate file must start with JSON front matter delimited by ---")
    try:
        end_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("Release gate front matter is missing closing --- delimiter") from exc
    raw = "\n".join(lines[1:end_index]).strip()
    if not raw:
        raise ValueError("Release gate front matter is empty")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Release gate front matter must be JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Release gate front matter must be a JSON object")
    return parsed
