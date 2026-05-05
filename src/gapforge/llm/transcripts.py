"""Transcript logging for optional LLM calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.llm.base import LLMResponse
from gapforge.redaction import redact_text
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class LLMTranscriptRecord:
    id: str
    skill_name: str
    prompt_pack_id: str
    model: str
    timestamp: str
    schema_name: str
    response_status: str
    reasoning_summary: str = ""
    prompt_preview: str = ""
    response_preview: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class LLMTranscriptLogger:
    def __init__(self, run_dir: str | Path | None = None) -> None:
        self.run_dir = Path(run_dir) if run_dir is not None else None

    def record(
        self,
        *,
        call_id: str,
        skill_name: str,
        prompt_pack_id: str = "",
        model: str,
        schema_name: str = "",
        response_status: str,
        prompt: str,
        response: LLMResponse | None = None,
        reasoning_summary: str = "",
        usage: dict[str, Any] | None = None,
    ) -> LLMTranscriptRecord:
        record = LLMTranscriptRecord(
            id=call_id,
            skill_name=skill_name,
            prompt_pack_id=prompt_pack_id,
            model=model,
            timestamp=utc_now_iso(),
            schema_name=schema_name,
            response_status=response_status,
            reasoning_summary=redact_text(reasoning_summary)[:500],
            prompt_preview=redact_text(prompt)[:1200],
            response_preview=redact_text(response.text if response is not None else "")[:1200],
            usage=usage or (response.usage if response is not None else {}),
        )
        self._append(record)
        return record

    def read(self) -> list[dict[str, Any]]:
        if self.run_dir is None:
            return []
        path = self.run_dir / "llm_transcripts.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def render_markdown(self) -> str:
        records = self.read()
        lines = ["# LLM Transcripts", ""]
        if not records:
            lines.append("No LLM transcripts recorded.")
            return "\n".join(lines).rstrip() + "\n"
        for record in records:
            lines.extend(
                [
                    f"## {record['id']}",
                    "",
                    f"- Skill: {record.get('skill_name') or 'unknown'}",
                    f"- Prompt pack: {record.get('prompt_pack_id') or 'none'}",
                    f"- Model: {record.get('model') or 'unknown'}",
                    f"- Timestamp: {record.get('timestamp') or 'unknown'}",
                    f"- Schema: {record.get('schema_name') or 'none'}",
                    f"- Status: {record.get('response_status') or 'unknown'}",
                    f"- Public reasoning summary: {record.get('reasoning_summary') or 'none'}",
                    "",
                    "Prompt preview:",
                    "",
                    f"> {record.get('prompt_preview', '')}",
                    "",
                    "Response preview:",
                    "",
                    f"> {record.get('response_preview', '')}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def _append(self, record: LLMTranscriptRecord) -> None:
        if self.run_dir is None:
            return
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "llm_transcripts.json"
        records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        records.append(asdict(record))
        path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        (self.run_dir / "llm_transcripts.md").write_text(self.render_markdown(), encoding="utf-8")


def _redact(text: str) -> str:
    return redact_text(text)
