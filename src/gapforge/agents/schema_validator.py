"""Strict validation for Codex/GPT-5.4 agent patch outputs."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from gapforge.agents.records import task_pack_dir, utc_now_iso
from gapforge.models import AgentTaskSpec, AgentValidationResult, Provenance, ResearchRunState
from gapforge.state import utc_now_compact

TASK_OUTPUTS: dict[str, dict[str, dict[str, Any]]] = {
    "deep_reading": {
        "paper_notes_patch.json": {"top_key": "paper_notes", "required_item_fields": ["paper_id"]},
        "claims_patch.json": {"top_key": "claims", "required_item_fields": ["id", "text", "type"]},
        "evidence_spans_patch.json": {"top_key": "evidence_spans", "required_item_fields": ["id", "paper_id", "quote"]},
    },
    "gap_mining": {
        "gaps_patch.json": {"top_key": "gaps", "required_item_fields": ["id", "description", "risk_that_gap_is_fake"]},
        "gap_evidence_matrices_patch.json": {"top_key": "gap_evidence_matrices", "required_item_fields": ["gap_id"]},
        "claims_patch.json": {"top_key": "claims", "required_item_fields": ["id", "text", "type"]},
    },
    "novelty": {
        "novelty_dossiers_patch.json": {"top_key": "novelty_dossiers", "required_item_fields": ["target_id", "idea_summary", "verdict"]},
        "novelty_assessments_patch.json": {
            "top_key": "novelty_assessments",
            "required_item_fields": ["target_gap_or_hypothesis_id", "idea_summary", "verdict"],
        },
        "rejected_ideas_patch.json": {"top_key": "rejected_ideas", "required_item_fields": []},
    },
    "reviewer": {
        "reviewer_objections_patch.json": {"top_key": "reviewer_objections", "required_item_fields": ["id", "objection"]},
        "reviewer_summaries_patch.json": {"top_key": "reviewer_summaries", "required_item_fields": ["experiment_id"]},
    },
    "related_work": {
        "related_work_matrix_patch.json": {"top_key": "related_work_matrices", "required_item_fields": ["direction_id"]},
    },
    "manuscript": {
        "paper_package_patch.json": {"top_key": "paper_packages", "required_item_fields": []},
    },
}

_UNKNOWN_VALUES = {"", "unknown", "none", "n/a", "not available", "missing"}


def expected_output_files(task_spec: AgentTaskSpec) -> list[str]:
    if task_spec.task_type == "manuscript":
        return ["paper_package_patch.json", "manuscript_outline.md"]
    return list(TASK_OUTPUTS.get(task_spec.task_type, {}).keys()) or task_spec.required_output_files


def expected_output_schema(task_spec: AgentTaskSpec) -> dict[str, Any]:
    files = TASK_OUTPUTS.get(task_spec.task_type, {})
    schema_files: dict[str, Any] = {}
    for filename, spec in files.items():
        schema_files[filename] = {
            "type": "object",
            "required": [spec["top_key"]],
            "properties": {
                spec["top_key"]: {
                    "type": "array",
                    "items": {"type": "object", "required": spec["required_item_fields"]},
                },
                "public_reasoning_summary": {"type": "string"},
                "search_requests": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": "preserved only if validation-safe",
        }
    if task_spec.task_type == "manuscript":
        schema_files["manuscript_outline.md"] = {"type": "markdown", "required": False}
    return {
        "schema_name": task_spec.output_schema_name,
        "task_type": task_spec.task_type,
        "files": schema_files,
        "global_rules": [
            "JSON must parse.",
            "Required top-level fields must exist.",
            "Known paper and evidence IDs must resolve.",
            "Supported/high-confidence claims require evidence.",
            "Novelty requires closest prior work or explicit unknown status.",
        ],
    }


def validate_task_outputs(
    state: ResearchRunState,
    task_spec: AgentTaskSpec,
    output_paths: list[Path] | None = None,
) -> AgentValidationResult:
    files_to_validate = _resolve_output_paths(state, task_spec, output_paths)
    issues: list[str] = []
    accepted: list[str] = []
    rejected: list[str] = []
    unsupported_claim_count = 0
    invalid_locator_count = 0
    invalid_prior_work_count = 0
    known_paper_ids = _known_paper_ids(state)
    known_search_ids = {paper_id for record in state.search_queries for paper_id in record.result_paper_ids}
    known_locators = {span.locator for span in state.evidence_spans if span.locator}
    known_span_ids = {span.id for span in state.evidence_spans if span.id}
    patch_span_ids = _patch_evidence_span_ids(files_to_validate)
    contracts = TASK_OUTPUTS.get(task_spec.task_type, {})
    present_names = {path.name for path in files_to_validate if path.exists()}
    missing = _missing_required_files(task_spec, present_names)
    issues.extend(f"missing required output file: {name}" for name in missing)

    for path in files_to_validate:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            rejected.append(str(resolved))
            continue
        if resolved.suffix.lower() == ".md":
            accepted.append(str(resolved))
            continue
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f"{resolved.name}: invalid JSON: {exc}")
            rejected.append(str(resolved))
            continue
        contract = contracts.get(resolved.name)
        if contract is not None:
            top_key = str(contract["top_key"])
            if top_key not in payload or not isinstance(payload[top_key], list):
                issues.append(f"{resolved.name}: missing required list field `{top_key}`")
            else:
                required_item_fields = list(contract.get("required_item_fields", []))
                for index, item in enumerate(payload[top_key]):
                    if not isinstance(item, dict):
                        issues.append(f"{resolved.name}: `{top_key}` item {index} is not an object")
                        continue
                    for field_name in required_item_fields:
                        if field_name not in item or item[field_name] in (None, "", []):
                            issues.append(f"{resolved.name}: `{top_key}` item {index} missing `{field_name}`")
        file_issues, counters = _validate_payload(
            payload,
            known_paper_ids=known_paper_ids | known_search_ids,
            known_locators=known_locators,
            known_span_ids=known_span_ids | patch_span_ids,
        )
        if file_issues:
            issues.extend(f"{resolved.name}: {issue}" for issue in file_issues)
        unsupported_claim_count += counters["unsupported_claim_count"]
        invalid_locator_count += counters["invalid_locator_count"]
        invalid_prior_work_count += counters["invalid_prior_work_count"]
        if any(issue.startswith(f"{resolved.name}:") for issue in issues):
            rejected.append(str(resolved))
        else:
            accepted.append(str(resolved))

    blocking = bool(issues)
    return AgentValidationResult(
        id=f"agent-validation-{utc_now_compact()}-{task_spec.id}",
        task_spec_id=task_spec.id,
        status="invalid" if blocking else "valid",
        issues=issues,
        accepted_output_paths=[] if blocking else sorted(set(accepted)),
        rejected_output_paths=sorted(set(rejected + ([] if not blocking else accepted))),
        unsupported_claim_count=unsupported_claim_count,
        invalid_locator_count=invalid_locator_count,
        invalid_prior_work_count=invalid_prior_work_count,
        provenance=Provenance(
            created_by_skill="agent-schema-validator",
            source_ids=[task_spec.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Strictly validated Codex agent patch outputs before import.",
        ),
    )


def _resolve_output_paths(state: ResearchRunState, task_spec: AgentTaskSpec, output_paths: list[Path] | None) -> list[Path]:
    if output_paths:
        return [path.expanduser().resolve() for path in output_paths]
    output_dir = task_pack_dir(state, task_spec) / "outputs"
    return [output_dir / filename for filename in expected_output_files(task_spec)]


def _missing_required_files(task_spec: AgentTaskSpec, present_names: set[str]) -> list[str]:
    expected = expected_output_files(task_spec)
    if task_spec.task_type == "manuscript" and ({"paper_package_patch.json", "manuscript_outline.md"} & present_names):
        return []
    return [name for name in expected if name not in present_names]


def _patch_evidence_span_ids(output_paths: list[Path]) -> set[str]:
    span_ids: set[str] = set()
    for path in output_paths:
        if path.name != "evidence_spans_patch.json" or not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in payload.get("evidence_spans", []):
            if isinstance(item, dict) and item.get("id"):
                span_ids.add(str(item["id"]))
    return span_ids


def _validate_payload(
    payload: Any,
    *,
    known_paper_ids: set[str],
    known_locators: set[str],
    known_span_ids: set[str],
) -> tuple[list[str], dict[str, int]]:
    issues: list[str] = []
    counters = {"unsupported_claim_count": 0, "invalid_locator_count": 0, "invalid_prior_work_count": 0}
    seen_invalid_paper_ids: set[str] = set()
    for node in _walk_dicts(payload):
        for paper_id in _extract_paper_ids(node):
            if _is_unknown(paper_id):
                continue
            if paper_id not in known_paper_ids and paper_id not in seen_invalid_paper_ids:
                seen_invalid_paper_ids.add(paper_id)
                counters["invalid_prior_work_count"] += 1
                issues.append(f"unknown paper_id: {paper_id}")
        for locator in _extract_locator_values(node):
            if _is_unknown(locator):
                continue
            if locator not in known_locators and locator not in known_span_ids:
                counters["invalid_locator_count"] += 1
                issues.append(f"unknown EvidenceSpan locator or id: {locator}")
        if _claim_supported_without_evidence(node):
            counters["unsupported_claim_count"] += 1
            issues.append(f"supported claim lacks evidence: {_node_label(node)}")
        if _high_confidence_result_without_evidence(node):
            counters["unsupported_claim_count"] += 1
            issues.append(f"high-confidence result lacks evidence: {_node_label(node)}")
        if _novelty_without_prior_work(node):
            counters["invalid_prior_work_count"] += 1
            issues.append(f"novelty claim lacks closest prior work or unknown verdict: {_node_label(node)}")
        for citation in _extract_citation_like_values(node):
            if _is_unknown(citation) or any(paper_id in citation for paper_id in known_paper_ids):
                continue
            if _is_search_request_context(node):
                continue
            counters["invalid_prior_work_count"] += 1
            issues.append(f"citation does not resolve to known corpus paper: {citation[:120]}")
    return issues, counters


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _known_paper_ids(state: ResearchRunState) -> set[str]:
    return {paper.id for paper in state.papers}


def _extract_paper_ids(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in node.items():
        key_lower = key.lower()
        if (
            key_lower == "paper_id"
            or key_lower.endswith("_paper_id")
            or key_lower.endswith("_paper_ids")
            or key_lower
            in {
                "paper_ids",
                "source_paper_ids",
                "supporting_paper_ids",
                "counterevidence_paper_ids",
            }
        ):
            values.extend(_string_values(value))
        if key_lower in {"top_prior_work", "closest_prior_work", "prior_work"}:
            values.extend(_paper_ids_from_prior_value(value))
    return values


def _paper_ids_from_prior_value(value: Any) -> list[str]:
    if isinstance(value, dict):
        ids = _string_values(value.get("paper_id", ""))
        for nested in value.values():
            if isinstance(nested, (list, dict)):
                ids.extend(_paper_ids_from_prior_value(nested))
        return ids
    if isinstance(value, list):
        list_ids: list[str] = []
        for item in value:
            if isinstance(item, dict):
                list_ids.extend(_paper_ids_from_prior_value(item))
        return list_ids
    return []


def _extract_locator_values(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in node.items():
        key_lower = key.lower()
        if "locator" in key_lower or key_lower in {"evidence_span_id", "evidence_span_ids"}:
            values.extend(_string_values(value))
    return values


def _claim_supported_without_evidence(node: dict[str, Any]) -> bool:
    if str(node.get("status", "")).lower() != "supported":
        return False
    return not _has_evidence(node)


def _high_confidence_result_without_evidence(node: dict[str, Any]) -> bool:
    if str(node.get("confidence", "")).lower() != "high":
        return False
    key_text = " ".join(node.keys()).lower()
    if not any(term in key_text for term in ("result", "claim", "main_results", "text", "limitation")):
        return False
    return not _has_evidence(node)


def _novelty_without_prior_work(node: dict[str, Any]) -> bool:
    claim_type = str(node.get("type", node.get("claim_type", ""))).lower()
    is_novelty = claim_type == "novelty" or (
        ("target_id" in node or "target_gap_or_hypothesis_id" in node) and ("idea_summary" in node or "novelty_strength" in node)
    )
    if not is_novelty:
        return False
    verdict = str(node.get("verdict", node.get("novelty_status", ""))).lower()
    strength = str(node.get("novelty_strength", node.get("confidence", ""))).lower()
    if verdict == "unknown" or strength == "unknown":
        return False
    return not any(node.get(key) for key in ("closest_prior_work", "top_prior_work", "closest_prior_work_ids"))


def _has_evidence(node: dict[str, Any]) -> bool:
    for key in ("supporting_evidence", "evidence", "evidence_span_ids", "evidence_locators", "locators", "locator"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
    return False


def _extract_citation_like_values(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in node.items():
        key_lower = key.lower()
        if key_lower in {"citation", "citations", "reference", "references", "prior_work", "closest_prior_work", "top_prior_work"}:
            if isinstance(value, str):
                values.append(value.strip())
            elif isinstance(value, list):
                values.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
    return values


def _is_search_request_context(node: dict[str, Any]) -> bool:
    return any("search" in key.lower() for key in node)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_string_values(item))
        return values
    if isinstance(value, dict):
        nested_values: list[str] = []
        for item in value.values():
            nested_values.extend(_string_values(item))
        return nested_values
    return []


def _is_unknown(value: str) -> bool:
    return value.strip().lower() in _UNKNOWN_VALUES


def _node_label(node: dict[str, Any]) -> str:
    for key in ("id", "claim_id", "target_id", "paper_id", "text", "claim", "idea_summary"):
        value = str(node.get(key, "")).strip()
        if value:
            return value[:100]
    return "unlabeled"
