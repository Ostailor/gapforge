"""Campaign-level Codex/GPT-5.4 task-pack generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.codex_campaign_prompts import render_campaign_task_markdown, render_rules
from gapforge.campaigns.handoff import write_campaign_handoff
from gapforge.config import GapForgeConfig
from gapforge.models import CampaignStep, Provenance, to_plain
from gapforge.state import utc_now_compact, utc_now_iso

CAMPAIGN_TASK_OUTPUTS: dict[str, list[str]] = {
    "campaign_planning": ["campaign_plan_patch.json", "proposed_steps.json", "risk_register.json"],
    "literature_scout": ["search_queries_patch.json", "source_coverage_requests.json", "papers_to_prioritize.json"],
    "deep_reader_batch": ["paper_notes_patch.json", "claims_patch.json", "evidence_spans_patch.json"],
    "gap_synthesis": ["gaps_patch.json", "gap_evidence_matrices_patch.json", "counterevidence_requests.json"],
    "novelty_reviewer": ["novelty_dossiers_patch.json", "rejected_ideas_patch.json", "missing_searches_patch.json"],
    "experiment_architect": ["experiment_protocols_patch.json", "baseline_requests.json", "reproducibility_checklists_patch.json"],
    "reviewer_panel": ["review_panel_patch.json", "rebuttal_plan_patch.json", "required_fixes.json"],
    "campaign_stop_decision": ["stop_condition_patch.json", "final_recommendation_patch.json"],
    "research_synthesis": [
        "research_directions_patch.json",
        "gap_evidence_matrices_patch.json",
        "novelty_dossiers_patch.json",
        "related_work_matrix_patch.json",
        "uncertainty_register.json",
        "search_requests.json",
    ],
}


def create_campaign_task_pack(config: GapForgeConfig, campaign_id: str, task_type: str) -> Path:
    manager = CampaignManager(config)
    campaign_state = manager.load_campaign_state(campaign_id)
    normalized_type = _normalize_task_type(task_type)
    if normalized_type not in CAMPAIGN_TASK_OUTPUTS:
        raise ValueError(f"Unsupported campaign task type: {task_type}")
    task_id = f"campaign-task-{utc_now_compact()}-{normalized_type}"
    pack_dir = _task_pack_dir(config, campaign_state, task_id)
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "outputs").mkdir(parents=True, exist_ok=True)
    expected_outputs = CAMPAIGN_TASK_OUTPUTS[normalized_type]
    context = _campaign_context(campaign_state, task_id, normalized_type)
    input_manifest = _input_manifest(config, campaign_state, normalized_type)
    expected = _expected_outputs(normalized_type, expected_outputs)
    schema_examples = _schema_examples(normalized_type, expected_outputs)
    task_context = _build_compact_task_context(config, campaign_id, normalized_type, task_id)
    input_manifest["artifact_links"]["task_context.json"] = str(pack_dir / "task_context.json")
    input_manifest["artifact_summaries"].insert(
        0,
        {
            "name": "task_context.json",
            "path": str(pack_dir / "task_context.json"),
            "bytes": len(json.dumps(task_context)),
            "inline_in_task": False,
            "note": "Retrieval-selected compact context; inspect before opening larger artifacts.",
        },
    )
    input_manifest["known_evidence_locators"] = [
        span.get("locator", "") for span in task_context.get("relevant_evidence_spans", []) if span.get("locator")
    ]
    input_manifest["known_evidence_span_ids"] = task_context.get("allowed_object_ids", {}).get("evidence_span_ids", [])

    (pack_dir / "CAMPAIGN_TASK.md").write_text(
        render_campaign_task_markdown(campaign_state, task_id, normalized_type, expected_outputs),
        encoding="utf-8",
    )
    (pack_dir / "campaign_context.json").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "task_context.json").write_text(json.dumps(task_context, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "input_manifest.json").write_text(json.dumps(input_manifest, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "expected_outputs.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "schema_examples.json").write_text(json.dumps(schema_examples, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "validation_rules.md").write_text(render_rules("Validation Rules", _validation_rules()), encoding="utf-8")
    (pack_dir / "evidence_rules.md").write_text(render_rules("Evidence Rules", _evidence_rules()), encoding="utf-8")
    (pack_dir / "novelty_rules.md").write_text(render_rules("Novelty Rules", _novelty_rules()), encoding="utf-8")
    (pack_dir / "stop_rules.md").write_text(render_rules("Stop Rules", _stop_rules()), encoding="utf-8")
    write_campaign_handoff(campaign_state, task_id, pack_dir, expected_outputs=expected_outputs)
    _write_token_budget(pack_dir)

    step = CampaignStep(
        id=f"campaign-step-{utc_now_compact()}-agent-task",
        campaign_id=campaign_id,
        name=f"Campaign task {normalized_type}",
        step_type=_step_type_for_task(normalized_type),
        status="pending",
        task_spec_id=task_id,
        input_artifacts=list(input_manifest["artifact_links"].values()),
        output_artifacts=[str(pack_dir / "outputs" / name) for name in expected_outputs],
        provenance=Provenance(
            created_by_skill="campaign-task-pack",
            source_ids=[campaign_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Created a validation-gated campaign-level Codex task pack.",
        ),
    )
    campaign_state.campaign.task_ids.append(task_id)
    campaign_state.steps.append(step)
    manager.save_campaign_state(campaign_state)
    return pack_dir


def campaign_task_pack_dir(config: GapForgeConfig, campaign_id: str, task_id: str) -> Path:
    manager = CampaignManager(config)
    state = manager.load_campaign_state(campaign_id)
    return _task_pack_dir(config, state, task_id)


def _task_pack_dir(config: GapForgeConfig, campaign_state: CampaignState, task_id: str) -> Path:
    return config.project_root / campaign_state.campaign.project_id / "campaigns" / campaign_state.campaign.id / "agent_tasks" / task_id


def _campaign_context(campaign_state: CampaignState, task_id: str, task_type: str) -> dict[str, Any]:
    campaign = campaign_state.campaign
    return {
        "task_id": task_id,
        "task_type": task_type,
        "campaign": to_plain(campaign),
        "budget": to_plain(campaign_state.budget),
        "step_count": len(campaign_state.steps),
        "decision_count": len(campaign_state.decisions),
        "milestone_count": len(campaign_state.milestones),
        "stop_conditions": to_plain(campaign_state.stop_conditions),
    }


def _input_manifest(config: GapForgeConfig, campaign_state: CampaignState, task_type: str) -> dict[str, Any]:
    campaign_dir = config.project_root / campaign_state.campaign.project_id / "campaigns" / campaign_state.campaign.id
    project_dir = config.project_root / campaign_state.campaign.project_id
    common_paths = [
        campaign_dir / "campaign.json",
        campaign_dir / "steps.json",
        campaign_dir / "decisions.json",
        campaign_dir / "milestones.json",
        campaign_dir / "campaign_report.md",
    ]
    task_paths = {
        "campaign_planning": [
            project_dir / "project_report.md",
            project_dir / "campaigns.json",
            project_dir / "memory_records.json",
        ],
        "literature_scout": [
            project_dir / "project_report.md",
            project_dir / "corpus_papers.json",
            project_dir / "memory_records.json",
        ],
        "deep_reader_batch": [
            project_dir / "corpus_papers.json",
            project_dir / "memory_records.json",
        ],
        "gap_synthesis": [
            project_dir / "corpus_papers.json",
            project_dir / "memory_records.json",
            project_dir / "research_directions.json",
        ],
        "novelty_reviewer": [
            project_dir / "corpus_papers.json",
            project_dir / "memory_records.json",
            project_dir / "research_directions.json",
            project_dir / "related_work_matrices.json",
        ],
        "experiment_architect": [
            project_dir / "corpus_papers.json",
            project_dir / "research_directions.json",
            project_dir / "related_work_matrices.json",
            project_dir / "experiment_protocols.json",
        ],
        "reviewer_panel": [
            project_dir / "research_directions.json",
            project_dir / "related_work_matrices.json",
            project_dir / "experiment_protocols.json",
            project_dir / "review_panels.json",
        ],
        "campaign_stop_decision": [
            project_dir / "project_report.md",
            project_dir / "research_directions.json",
            project_dir / "review_queue.md",
        ],
        "research_synthesis": [
            project_dir / "project_report.md",
            project_dir / "corpus_papers.json",
            project_dir / "memory_records.json",
            project_dir / "research_directions.json",
            project_dir / "related_work_matrices.json",
            project_dir / "review_queue.md",
        ],
    }
    candidate_paths = [
        *common_paths,
        *task_paths.get(
            task_type,
            [
                project_dir / "project_report.md",
                project_dir / "corpus_papers.json",
                project_dir / "memory_records.json",
                project_dir / "research_directions.json",
            ],
        ),
        project_dir / "retrieval" / "manifest.json",
        project_dir / "source_coverage.md",
    ]
    # Preserve order while removing duplicate paths.
    candidate_paths = list(dict.fromkeys(candidate_paths))
    artifact_links = {path.name: str(path) for path in candidate_paths if path.exists()}
    return {
        "campaign_id": campaign_state.campaign.id,
        "project_id": campaign_state.campaign.project_id,
        "artifact_links": artifact_links,
        "artifact_summaries": [_artifact_summary(path) for path in candidate_paths if path.exists()],
        "prompt_size_policy": {
            "large_artifacts_are_linked_not_inlined": True,
            "inspect_only_artifacts_needed_for_the_task": True,
            "prefer_retrieval_selected_excerpts_when_available": True,
        },
        "known_paper_ids": _known_project_paper_ids(project_dir),
        "known_evidence_locators": [],
        "known_evidence_span_ids": [],
    }


def _expected_outputs(task_type: str, filenames: list[str]) -> dict[str, Any]:
    return {
        "task_type": task_type,
        "files": {
            name: {
                "type": "object",
                "required": [_top_key_for_file(name)],
                "public_reasoning_summary": "required when synthesis is provided",
            }
            for name in filenames
        },
    }


def _schema_examples(task_type: str, filenames: list[str]) -> dict[str, Any]:
    examples: dict[str, Any] = {"task_type": task_type, "files": {}}
    for filename in filenames:
        top_key = _top_key_for_file(filename)
        examples["files"][filename] = {
            top_key: [],
            "public_reasoning_summary": "One or two public sentences explaining the evidence basis and uncertainty.",
        }
    if "novelty_dossiers_patch.json" in filenames:
        examples["files"]["novelty_dossiers_patch.json"] = {
            "novelty_dossiers": [
                {
                    "target_id": "gap-or-direction-id",
                    "idea_summary": "Concise idea summary.",
                    "top_prior_work": ["known-paper-id"],
                    "verdict": "unknown",
                    "novelty_strength": "unknown",
                    "confidence": "low",
                    "missing_searches": ["search that still needs to be run"],
                    "public_reasoning_summary": "Novelty remains unknown because closest-prior-work coverage is incomplete.",
                }
            ]
        }
    if task_type == "research_synthesis" and "research_directions_patch.json" in filenames:
        examples["files"]["research_directions_patch.json"] = {
            "research_directions_patch": [
                {
                    "id": "direction-id",
                    "title": "Evidence-grounded direction title",
                    "summary": "Conservative summary tied to evidence.",
                    "linked_gap_ids": ["known-gap-id"],
                    "supporting_paper_ids": ["known-paper-id"],
                    "evidence_span_ids": ["known-evidence-span-id-or-locator"],
                    "closest_prior_work": ["known-paper-id"],
                    "risk_that_gap_is_fake": "Closest prior work may already cover the exact evaluation setting.",
                    "novelty_strength": "unknown",
                    "confidence": "low",
                    "missing_searches": ["search still needed before stronger novelty claims"],
                    "public_reasoning_summary": "Direction is provisional and cites only known evidence.",
                }
            ]
        }
    if "stop_condition_patch.json" in filenames:
        examples["files"]["stop_condition_patch.json"] = {
            "stop_condition_patch": [
                {
                    "reason": "not_ready_poor_coverage",
                    "triggered": True,
                    "evidence": ["source coverage is low"],
                    "public_reasoning_summary": "Campaign should stop rather than recommend under weak coverage.",
                }
            ]
        }
    return examples


def _artifact_summary(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    summary = {
        "name": path.name,
        "path": str(path),
        "bytes": size,
        "inline_in_task": False,
        "note": "Linked artifact; inspect only if needed for this task.",
    }
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary["json"] = "invalid"
        else:
            if isinstance(data, list):
                summary["json"] = {"type": "list", "items": len(data)}
            elif isinstance(data, dict):
                summary["json"] = {"type": "object", "keys": sorted(data)[:20]}
    return summary


def _write_token_budget(pack_dir: Path) -> None:
    threshold = _task_pack_warning_threshold()
    files = []
    total = 0
    for path in sorted(pack_dir.glob("*")):
        if not path.is_file():
            continue
        chars = len(path.read_text(encoding="utf-8", errors="replace"))
        total += chars
        files.append({"name": path.name, "chars": chars})
    warnings = []
    if total > threshold:
        warnings.append(
            f"Task pack text is {total} chars, above threshold {threshold}; inspect manifest summaries and avoid pasting large artifacts."
        )
    (pack_dir / "token_budget.json").write_text(
        json.dumps({"threshold_chars": threshold, "total_chars": total, "files": files, "warnings": warnings}, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_compact_task_context(config: GapForgeConfig, campaign_id: str, task_type: str, task_id: str) -> dict[str, Any]:
    from gapforge.campaigns.context_builder import build_task_context

    budget = os.environ.get("GAPFORGE_TASK_CONTEXT_BUDGET", "medium").strip().lower() or "medium"
    return build_task_context(config, campaign_id, task_type, budget=budget, task_id=task_id)


def _task_pack_warning_threshold() -> int:
    raw = os.environ.get("GAPFORGE_TASK_PACK_WARNING_CHARS", "20000").strip()
    try:
        return max(1000, int(raw))
    except ValueError:
        return 20000


def _known_project_paper_ids(project_dir: Path) -> list[str]:
    corpus_path = project_dir / "corpus_papers.json"
    if not corpus_path.exists():
        return []
    try:
        raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    paper_ids: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("paper_id"):
            paper_ids.append(str(item["paper_id"]))
        paper_ids.extend(str(source_id) for source_id in item.get("source_paper_ids", []) if source_id)
    return sorted(set(paper_ids))


def _normalize_task_type(task_type: str) -> str:
    return task_type.strip().lower().replace("-", "_")


def _top_key_for_file(filename: str) -> str:
    return filename.removesuffix(".json")


def _step_type_for_task(task_type: str) -> str:
    mapping = {
        "campaign_planning": "review",
        "literature_scout": "search",
        "deep_reader_batch": "read",
        "gap_synthesis": "gap_mining",
        "novelty_reviewer": "novelty",
        "experiment_architect": "experiment",
        "reviewer_panel": "review",
        "campaign_stop_decision": "stop",
    }
    return mapping.get(task_type, "review")


def _validation_rules() -> list[str]:
    return [
        "JSON must parse.",
        "Required top-level patch keys must exist.",
        "Known paper IDs must resolve to project corpus or attached run artifacts.",
        "Evidence span IDs and locators must resolve when used.",
        "Fake citations, unsupported high-confidence claims, and unsupported novelty claims are rejected.",
    ]


def _evidence_rules() -> list[str]:
    return [
        "Cite only known paper IDs and EvidenceSpan locators.",
        "Do not invent citations, prior work, results, datasets, or metrics.",
        "High-confidence claims require explicit evidence.",
        "Abstract-only evidence must be labeled lower confidence.",
    ]


def _novelty_rules() -> list[str]:
    return [
        "Novelty requires closest prior work or an explicit unknown verdict.",
        "List missing searches when closest prior work is not enough.",
        "Reject or downgrade ideas that duplicate known work.",
    ]


def _stop_rules() -> list[str]:
    return [
        "Stop if source coverage is too weak to recommend a direction.",
        "Stop if novelty remains unknown after required searches.",
        "Stop if evidence is insufficient for high-confidence claims.",
        "Write stop conditions explicitly instead of overclaiming.",
    ]
