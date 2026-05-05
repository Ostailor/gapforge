"""JSON extraction and schema validation for model outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from gapforge.llm.base import LLMClient
from gapforge.llm.schemas import schema_for


class JSONGuardError(ValueError):
    """Raised when model output cannot be accepted as valid JSON."""


@dataclass(slots=True)
class JSONGuardResult:
    data: dict[str, Any]
    repaired: bool = False
    warnings: list[str] = field(default_factory=list)


class JSONGuard:
    """Extract and validate model JSON before it can enter GapForge state."""

    def __init__(self, *, reject_unknown_schema: bool = True) -> None:
        self.reject_unknown_schema = reject_unknown_schema

    def parse_and_validate(
        self,
        response_text: str,
        *,
        schema_name: str,
        repair_client: LLMClient | None = None,
        repair_prompt: str | None = None,
        provider_mode: bool = False,
    ) -> JSONGuardResult:
        try:
            data = self._parse(response_text)
            self.validate(data, schema_name=schema_name)
            return JSONGuardResult(data=data)
        except JSONGuardError:
            if not provider_mode or repair_client is None:
                raise
        repair = repair_client.complete(
            _repair_prompt(response_text, schema_name, repair_prompt),
            system="Return only valid JSON. Do not add prose.",
            temperature=0.0,
        )
        data = self._parse(repair.text)
        self.validate(data, schema_name=schema_name)
        return JSONGuardResult(data=data, repaired=True, warnings=["Malformed JSON repaired with one provider retry."])

    def validate(self, data: dict[str, Any], *, schema_name: str) -> None:
        try:
            schema = schema_for(schema_name)
        except KeyError as exc:
            if self.reject_unknown_schema:
                raise JSONGuardError(str(exc)) from exc
            return
        _validate_object(data, schema, path="$")

    def _parse(self, text: str) -> dict[str, Any]:
        candidates = [text, *_json_blocks(text), _between_braces(text)]
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                raise JSONGuardError("Model JSON output must be an object.")
            return parsed
        raise JSONGuardError("No valid JSON object found in model response.")


def extract_json(text: str) -> dict[str, Any]:
    return JSONGuard()._parse(text)


def _validate_object(data: Any, schema: dict[str, Any], *, path: str) -> None:
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(data, dict):
            raise JSONGuardError(f"{path} must be an object.")
        allowed = set(schema.get("properties", {}))
        required = set(schema.get("required", []))
        missing = sorted(required - set(data))
        if missing:
            raise JSONGuardError(f"{path} is missing required fields: {', '.join(missing)}")
        unknown = sorted(set(data) - allowed)
        if allowed and unknown:
            raise JSONGuardError(f"{path} contains unknown fields: {', '.join(unknown)}")
        for key, value in data.items():
            child_schema = schema.get("properties", {}).get(key)
            if child_schema is not None:
                _validate_object(value, child_schema, path=f"{path}.{key}")
    elif expected_type == "array":
        if not isinstance(data, list):
            raise JSONGuardError(f"{path} must be an array.")
        item_schema = schema.get("items", {})
        for index, item in enumerate(data):
            _validate_object(item, item_schema, path=f"{path}[{index}]")
    elif expected_type == "string":
        if not isinstance(data, str):
            raise JSONGuardError(f"{path} must be a string.")
        enum = schema.get("enum")
        if enum and data not in enum:
            raise JSONGuardError(f"{path} must be one of: {', '.join(enum)}")
    elif expected_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            raise JSONGuardError(f"{path} must be an integer.")
    elif expected_type == "boolean":
        if not isinstance(data, bool):
            raise JSONGuardError(f"{path} must be a boolean.")


def _json_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)


def _between_braces(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    return text[start : end + 1] if start >= 0 and end > start else ""


def _repair_prompt(response_text: str, schema_name: str, original_prompt: str | None) -> str:
    return (
        f"Repair the following response into valid JSON for schema `{schema_name}`. "
        "Use only fields in the schema and preserve uncertainty. Return JSON only.\n\n"
        f"Original prompt summary:\n{(original_prompt or '')[:2000]}\n\n"
        f"Malformed response:\n{response_text[:6000]}"
    )
