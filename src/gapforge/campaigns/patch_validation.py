"""Validation for campaign-level Codex/GPT-5.4 output patches."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignState
from gapforge.campaigns.task_packs import CAMPAIGN_TASK_OUTPUTS, campaign_task_pack_dir
from gapforge.config import GapForgeConfig
from gapforge.models import CampaignImportRecord, Provenance
from gapforge.state import utc_now_compact, utc_now_iso


def validate_campaign_patch(
    config: GapForgeConfig,
    campaign_state: CampaignState,
    task_id: str,
    paths: list[Path],
) -> CampaignImportRecord:
    task_type = task_type_from_id(task_id)
    expected = set(CAMPAIGN_TASK_OUTPUTS.get(task_type, []))
    paths_to_check = resolve_paths(config, campaign_state.campaign.id, task_id, paths, expected)
    known_papers = known_paper_ids(config, campaign_state.campaign.project_id)
    known_steps = {step.id for step in campaign_state.steps}
    known_tasks = set(campaign_state.campaign.task_ids)
    known_evidence_spans = known_evidence_span_ids(config, campaign_state)
    issues: list[str] = []
    accepted_objects: list[dict[str, Any]] = []
    rejected_objects: list[dict[str, Any]] = []

    present = {path.name for path in paths_to_check if path.exists()}
    for missing in sorted(expected - present):
        issues.append(f"missing required output file: {missing}")

    for path in paths_to_check:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            rejected_objects.append(_rejected("file", str(resolved), "missing output file"))
            continue
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rejected_objects.append(_rejected("file", str(resolved), f"invalid JSON: {exc}"))
            issues.append(f"{resolved.name}: invalid JSON: {exc}")
            continue
        top_key = resolved.name.removesuffix(".json")
        if top_key not in payload:
            reason = f"missing required field `{top_key}`"
            issues.append(f"{resolved.name}: {reason}")
            rejected_objects.append(_rejected("file", str(resolved), reason))
            continue
        file_accepted = False
        for index, item in enumerate(_items(payload[top_key])):
            object_id = _object_id(item, fallback=f"{resolved.name}:{index}")
            object_issues = validate_patch_object(
                item,
                known_papers=known_papers,
                known_evidence_spans=known_evidence_spans,
                known_steps=known_steps,
                known_tasks=known_tasks,
            )
            if object_issues:
                rejected_objects.append(_rejected(top_key, object_id, "; ".join(object_issues), source_path=str(resolved)))
                issues.extend(f"{resolved.name}:{object_id}: {issue}" for issue in object_issues)
            else:
                accepted_objects.append({"type": top_key, "id": object_id, "source_path": str(resolved)})
                file_accepted = True
        if file_accepted and not any(item.get("source_path") == str(resolved) for item in rejected_objects):
            accepted_objects.append({"type": "file", "id": resolved.name, "source_path": str(resolved)})

    status = _status(accepted_objects, rejected_objects, issues)
    return CampaignImportRecord(
        id=f"campaign-import-{utc_now_compact()}-{task_id}",
        campaign_id=campaign_state.campaign.id,
        task_id=task_id,
        input_paths=[str(path.expanduser().resolve()) for path in paths_to_check],
        status=status,
        accepted_objects=accepted_objects,
        rejected_objects=rejected_objects,
        issues=issues,
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="campaign-patch-validation",
            source_ids=[campaign_state.campaign.id, task_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Validated campaign patch objects before applying any mutation.",
        ),
    )


def validate_patch_object(
    item: dict[str, Any],
    *,
    known_papers: set[str],
    known_evidence_spans: set[str],
    known_steps: set[str],
    known_tasks: set[str],
) -> list[str]:
    issues: list[str] = []
    for paper_id in _paper_ids(item):
        if _unknown(paper_id):
            continue
        if paper_id not in known_papers:
            issues.append(f"unknown paper_id: {paper_id}")
    for evidence_span_id in _evidence_span_ids(item):
        if _unknown(evidence_span_id):
            continue
        if evidence_span_id not in known_evidence_spans:
            issues.append(f"unknown evidence_span_id: {evidence_span_id}")
    for step_id in _ids_for_keys(item, {"campaign_step_id", "step_id", "linked_step_id"}):
        if step_id not in known_steps:
            issues.append(f"unknown campaign step id: {step_id}")
    for linked_task_id in _ids_for_keys(item, {"task_id", "task_spec_id", "linked_task_id"}):
        if linked_task_id not in known_tasks:
            issues.append(f"unknown campaign task id: {linked_task_id}")
    for citation in _citations(item):
        if not _citation_resolves(citation, known_papers):
            issues.append(f"citation does not resolve to known corpus paper: {citation[:120]}")
    for doi_or_arxiv in _doi_arxiv_claims(item):
        if doi_or_arxiv and not _is_search_request(item):
            issues.append(f"unknown DOI/arXiv claim must be converted into a search request: {doi_or_arxiv}")
    confidence = str(item.get("confidence", "")).lower()
    if confidence == "high" and not _has_evidence(item):
        issues.append("high-confidence claim lacks evidence locator")
    novelty_strength = str(item.get("novelty_strength", "")).lower()
    if novelty_strength == "strong" and not _strong_novelty_gate_passes(item):
        issues.append("strong novelty is blocked until closest prior work, coverage, and missing searches gates pass")
    if _novelty_without_prior_work(item):
        issues.append("novelty output lacks closest prior work or unknown verdict")
    return issues


def resolve_paths(config: GapForgeConfig, campaign_id: str, task_id: str, paths: list[Path], expected: set[str]) -> list[Path]:
    if paths:
        return [path.expanduser().resolve() for path in paths]
    outputs_dir = campaign_task_pack_dir(config, campaign_id, task_id) / "outputs"
    return [outputs_dir / name for name in sorted(expected)]


def task_type_from_id(task_id: str) -> str:
    for task_type in CAMPAIGN_TASK_OUTPUTS:
        if task_id.endswith(task_type):
            return task_type
    return task_id.rsplit("-", 1)[-1]


def known_paper_ids(config: GapForgeConfig, project_id: str) -> set[str]:
    corpus_path = config.project_root / project_id / "corpus_papers.json"
    if not corpus_path.exists():
        return set()
    try:
        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    paper_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("paper_id"):
            paper_ids.add(str(item["paper_id"]))
        for source_id in item.get("source_paper_ids", []):
            if source_id:
                paper_ids.add(str(source_id))
    return paper_ids


def known_evidence_span_ids(config: GapForgeConfig, campaign_state: CampaignState) -> set[str]:
    span_ids: set[str] = set()
    for run_id in campaign_state.campaign.run_ids:
        evidence_path = config.runs_dir / run_id / "evidence_spans.json"
        if not evidence_path.exists():
            continue
        try:
            raw = json.loads(evidence_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in raw:
            if isinstance(item, dict):
                if item.get("id"):
                    span_ids.add(str(item["id"]))
                if item.get("locator"):
                    span_ids.add(str(item["locator"]))
    return span_ids


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _status(accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], issues: list[str]) -> str:
    if accepted and (rejected or issues):
        return "partial"
    if accepted and not issues:
        return "valid"
    return "rejected"


def _object_id(item: dict[str, Any], *, fallback: str) -> str:
    for key in ("id", "target_id", "gap_id", "paper_id", "experiment_id", "reason", "recommendation"):
        value = str(item.get(key, "")).strip()
        if value:
            return value[:120]
    return fallback


def _rejected(object_type: str, object_id: str, reason: str, *, source_path: str = "") -> dict[str, Any]:
    return {"type": object_type, "id": object_id, "reason": reason, "source_path": source_path}


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _paper_ids(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for nested in _walk_dicts(node):
        for key, value in nested.items():
            key_lower = key.lower()
            if "paper_id" in key_lower:
                values.extend(_strings(value))
            if key_lower in {"top_prior_work", "closest_prior_work", "prior_work"}:
                values.extend(_prior_work_ids(value))
    return values


def _evidence_span_ids(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for nested in _walk_dicts(node):
        for key, value in nested.items():
            if "evidence_span" in key.lower() or "locator" in key.lower():
                values.extend(_strings(value))
    return values


def _ids_for_keys(node: dict[str, Any], keys: set[str]) -> list[str]:
    values: list[str] = []
    for nested in _walk_dicts(node):
        for key, value in nested.items():
            if key.lower() in keys:
                values.extend(_strings(value))
    return values


def _citations(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for nested in _walk_dicts(node):
        for key, value in nested.items():
            if key.lower() in {"citation", "citations", "reference", "references", "top_prior_work", "closest_prior_work"}:
                values.extend(_strings(value))
    return values


def _prior_work_ids(value: Any) -> list[str]:
    if isinstance(value, dict):
        ids = _strings(value.get("paper_id", ""))
        for nested in value.values():
            if isinstance(nested, (list, dict)):
                ids.extend(_prior_work_ids(nested))
        return ids
    if isinstance(value, list):
        list_ids: list[str] = []
        for item in value:
            if isinstance(item, dict):
                list_ids.extend(_prior_work_ids(item))
        return list_ids
    return []


def _doi_arxiv_claims(node: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for nested in _walk_dicts(node):
        for key, value in nested.items():
            key_lower = key.lower()
            if key_lower in {"doi", "arxiv_id"}:
                values.extend(_strings(value))
            elif isinstance(value, str) and (re.search(r"10\.\d{4,9}/\S+", value) or re.search(r"\b\d{4}\.\d{4,5}\b", value)):
                values.append(value)
    return values


def _citation_resolves(citation: str, known_papers: set[str]) -> bool:
    return bool(citation and any(paper_id in citation for paper_id in known_papers))


def _has_evidence(item: dict[str, Any]) -> bool:
    return bool(item.get("evidence_span_ids") or item.get("evidence_locators") or item.get("locator") or item.get("supporting_evidence"))


def _is_search_request(item: dict[str, Any]) -> bool:
    return any("search" in key.lower() for key in item)


def _strong_novelty_gate_passes(item: dict[str, Any]) -> bool:
    coverage = str(item.get("source_coverage", item.get("coverage", ""))).lower()
    missing = item.get("missing_searches", [])
    return bool(item.get("closest_prior_work") or item.get("top_prior_work") and coverage in {"medium", "high", "strong"} and not missing)


def _novelty_without_prior_work(item: dict[str, Any]) -> bool:
    text = " ".join(item.keys()).lower()
    if "novelty" not in text and "prior_work" not in text:
        return False
    verdict = str(item.get("verdict", "")).lower()
    if verdict == "unknown":
        return False
    return not (item.get("closest_prior_work") or item.get("top_prior_work"))


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [nested for item in value for nested in _strings(item)]
    if isinstance(value, dict):
        return [nested for item in value.values() for nested in _strings(item)]
    return []


def _unknown(value: str) -> bool:
    return value.strip().lower() in {"", "unknown", "none", "n/a", "missing"}
