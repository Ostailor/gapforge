"""Validation-gated Codex/GPT-5.4 task packs for v2 idea synthesis."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.ideas.constructive_gap import validate_constructive_gap_candidate
from gapforge.ideas.generator import is_generic_idea_title
from gapforge.ideas.models import (
    ConstructiveGapCandidate,
    IdeaMutationRecord,
    IdeaReviewRecord,
    IdeaTransferCandidate,
    validate_contribution_type,
    validate_mutation_strategy,
    validate_novelty_status,
    validate_review_status,
)
from gapforge.ideas.store import IdeaStore
from gapforge.ideas.topic_portfolio import TopicPortfolioGenerator
from gapforge.models import CampaignImportRecord, Provenance, ResearchDirection, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, slugify, utc_now_compact, utc_now_iso

IDEA_CODEX_TASK_TYPES = {
    "idea_seed_expansion",
    "idea_mutation",
    "constructive_gap_synthesis",
    "cross_domain_idea_transfer",
    "idea_critique",
    "idea_tournament_judge",
    "research_agenda_builder",
}

IDEA_CODEX_OUTPUTS = [
    "idea_candidates_patch.json",
    "idea_mutations_patch.json",
    "constructive_gaps_patch.json",
    "transfer_candidates_patch.json",
    "idea_reviews_patch.json",
    "agenda_patch.json",
]

OUTPUT_TOP_KEYS = {
    "idea_candidates_patch.json": "idea_candidates",
    "idea_mutations_patch.json": "idea_mutations",
    "constructive_gaps_patch.json": "constructive_gaps",
    "transfer_candidates_patch.json": "transfer_candidates",
    "idea_reviews_patch.json": "idea_reviews",
    "agenda_patch.json": "agenda",
}

RESULT_CLAIM_MARKERS = (
    "we found",
    "we show",
    "results show",
    "outperforms",
    "outperformed",
    "achieves",
    "achieved",
    "improves by",
    "significant improvement",
)


@dataclass(slots=True)
class IdeaCodexTask:
    id: str
    project_id: str
    task_type: str
    task_dir: str
    outputs_dir: str
    expected_outputs: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="idea-codex-task"))


class IdeaCodexTaskManager:
    """Create, hand off, validate, and import idea-synthesis Codex task packs."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.idea_store = IdeaStore(config)
        self.topic_portfolios = TopicPortfolioGenerator(config)

    def create_task(self, project_id: str, task_type: str) -> IdeaCodexTask:
        normalized = _normalize_task_type(task_type)
        program = self.project_manager.load_project(project_id)
        if self.idea_store.load_state(project_id).idea_bank is None:
            self.idea_store.create_bank(project_id=project_id, root_topic=program.project.name)
        task_id = f"idea-codex-task-{utc_now_compact()}-{normalized}"
        task_dir = Path(program.project.root_dir) / "ideas" / "codex_tasks" / task_id
        outputs_dir = task_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        task = IdeaCodexTask(
            id=task_id,
            project_id=project_id,
            task_type=normalized,
            task_dir=str(task_dir),
            outputs_dir=str(outputs_dir),
            expected_outputs=IDEA_CODEX_OUTPUTS,
            created_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="idea-codex-task",
                source_ids=[project_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a validation-gated Codex/GPT-5.4 task pack for v2 idea synthesis.",
            ),
        )
        context = self._task_context(project_id, normalized)
        (task_dir / "IDEA_CODEX_TASK.md").write_text(_render_prompt(task, context), encoding="utf-8")
        (task_dir / "task.json").write_text(json.dumps(to_plain(task), indent=2) + "\n", encoding="utf-8")
        (task_dir / "task_context.json").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
        (task_dir / "expected_outputs.json").write_text(json.dumps(_expected_outputs(), indent=2) + "\n", encoding="utf-8")
        (task_dir / "schema_examples.json").write_text(json.dumps(_schema_examples(), indent=2) + "\n", encoding="utf-8")
        (task_dir / "validation_rules.md").write_text(_validation_rules_markdown(), encoding="utf-8")
        return task

    def load_task(self, task_id: str) -> IdeaCodexTask:
        for project in self.project_manager.list_projects():
            task_path = Path(project.root_dir) / "ideas" / "codex_tasks" / task_id / "task.json"
            if task_path.exists():
                return from_dict(IdeaCodexTask, json.loads(task_path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No idea Codex task found for {task_id}")

    def handoff(self, task_id: str) -> str:
        task = self.load_task(task_id)
        path = Path(task.task_dir) / "IDEA_CODEX_TASK.md"
        return path.read_text(encoding="utf-8")

    def import_outputs(self, task_id: str) -> CampaignImportRecord:
        task = self.load_task(task_id)
        paths = [Path(task.outputs_dir) / name for name in IDEA_CODEX_OUTPUTS if (Path(task.outputs_dir) / name).exists()]
        record = self.validate_outputs(task, paths)
        if record.accepted_objects:
            self._apply(task, record, paths)
            record.status = "partial" if record.rejected_objects or record.issues else "applied"
        else:
            record.status = "rejected"
        record.created_at = record.created_at or utc_now_iso()
        record.provenance = Provenance(
            created_by_skill="idea-codex-import",
            source_ids=[task.project_id, task.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Validated idea Codex task outputs before importing accepted objects into v2 idea state.",
        )
        validation_path = Path(task.task_dir) / "validation.json"
        validation_path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        return record

    def validate_outputs(self, task: IdeaCodexTask, paths: list[Path]) -> CampaignImportRecord:
        known = self._known_ids(task.project_id)
        record = CampaignImportRecord(
            id=f"idea-codex-import-{utc_now_compact()}-{task.id}",
            campaign_id="",
            task_id=task.id,
            input_paths=[str(path) for path in paths],
            status="valid",
            created_at=utc_now_iso(),
        )
        if not paths:
            record.status = "rejected"
            record.issues.append("No idea Codex output files found.")
            return record
        for path in paths:
            if path.name not in OUTPUT_TOP_KEYS:
                record.rejected_objects.append(_rejected_file(path, "unexpected output file"))
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                record.rejected_objects.append(_rejected_file(path, f"invalid JSON: {exc}"))
                continue
            top_key = OUTPUT_TOP_KEYS[path.name]
            items = _items(payload.get(top_key))
            if path.name == "agenda_patch.json" and isinstance(payload.get(top_key), dict):
                items = [payload[top_key]]
            for index, item in enumerate(items):
                accepted, reason, normalized = self._validate_item(path.name, item, known)
                object_id = str(normalized.get("id") or normalized.get("title") or f"{path.name}:{index}")
                if accepted:
                    record.accepted_objects.append(
                        {"type": _object_type(path.name), "id": object_id, "source_path": str(path), "payload": normalized}
                    )
                else:
                    record.rejected_objects.append(
                        {"type": _object_type(path.name), "id": object_id, "source_path": str(path), "reason": reason}
                    )
        if record.rejected_objects:
            record.issues.extend(str(item["reason"]) for item in record.rejected_objects if item.get("reason"))
        if record.accepted_objects and record.rejected_objects:
            record.status = "partial"
        elif record.accepted_objects:
            record.status = "valid"
        else:
            record.status = "rejected"
        return record

    def _validate_item(self, filename: str, item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
        normalized = dict(item)
        if filename == "idea_candidates_patch.json":
            return _validate_idea_candidate_patch(normalized, known)
        if filename == "idea_mutations_patch.json":
            return _validate_mutation_patch(normalized, known)
        if filename == "constructive_gaps_patch.json":
            return _validate_constructive_gap_patch(normalized, known)
        if filename == "transfer_candidates_patch.json":
            return _validate_transfer_patch(normalized, known)
        if filename == "idea_reviews_patch.json":
            return _validate_review_patch(normalized, known)
        if filename == "agenda_patch.json":
            return _validate_agenda_patch(normalized, known)
        return False, "unsupported output file", normalized

    def _apply(self, task: IdeaCodexTask, record: CampaignImportRecord, paths: list[Path]) -> None:
        state = self.idea_store.load_state(task.project_id)
        project = self.project_manager.load_project(task.project_id)
        existing_constructive = {item.id for item in state.constructive_gaps}
        existing_transfer = {item.id for item in state.transfer_candidates}
        existing_mutations = {item.id for item in state.mutations}
        existing_reviews = {item.id for item in state.reviews}
        for accepted in record.accepted_objects:
            payload = accepted.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if accepted["type"] == "idea_candidate":
                candidate = self.idea_store.add_candidate(
                    project_id=task.project_id,
                    source_topic_id=str(payload.get("source_topic_id") or task.id),
                    title=str(payload["title"]),
                    summary=str(payload.get("summary") or ""),
                    contribution_type=str(payload["contribution_type"]),
                    core_claim=str(payload.get("core_claim") or ""),
                    proposed_experiment=str(payload.get("proposed_experiment") or ""),
                    expected_baselines=_strings(payload.get("expected_baselines")),
                    expected_metrics=_strings(payload.get("expected_metrics")),
                    closest_prior_work_ids=_strings(payload.get("closest_prior_work_ids")),
                    evidence_span_ids=_strings(payload.get("evidence_span_ids")),
                    supporting_paper_ids=_strings(payload.get("supporting_paper_ids")),
                    counterevidence_paper_ids=_strings(payload.get("counterevidence_paper_ids")),
                    novelty_status=str(payload.get("novelty_status") or "unchecked"),
                    maturity=str(payload.get("maturity") or "seed"),
                    likely_failure_mode=str(payload.get("likely_failure_mode") or ""),
                    provenance=_import_provenance(task, accepted["id"]),
                )
                accepted["id"] = candidate.id
                state = self.idea_store.load_state(task.project_id)
            elif accepted["type"] == "idea_mutation" and str(payload["id"]) not in existing_mutations:
                state.mutations.append(
                    IdeaMutationRecord(
                        id=str(payload["id"]),
                        source_idea_id=str(payload.get("source_idea_id") or ""),
                        mutated_idea_id=str(payload.get("mutated_idea_id") or ""),
                        strategy=str(payload["strategy"]),
                        what_changed=str(payload.get("what_changed") or ""),
                        why_it_may_help=str(payload.get("why_it_may_help") or ""),
                        inherited_risks=_strings(payload.get("inherited_risks")),
                        required_new_searches=_strings(payload.get("required_new_searches")),
                        provenance=_import_provenance(task, str(payload["id"])),
                    )
                )
                existing_mutations.add(str(payload["id"]))
            elif accepted["type"] == "constructive_gap" and str(payload["id"]) not in existing_constructive:
                gap = from_dict(
                    ConstructiveGapCandidate,
                    {**payload, "provenance": to_plain(_import_provenance(task, str(payload["id"])))},
                )
                state.constructive_gaps.append(gap)
                existing_constructive.add(gap.id)
            elif accepted["type"] == "transfer_candidate" and str(payload["id"]) not in existing_transfer:
                transfer = from_dict(
                    IdeaTransferCandidate,
                    {**payload, "provenance": to_plain(_import_provenance(task, str(payload["id"])))},
                )
                state.transfer_candidates.append(transfer)
                existing_transfer.add(transfer.id)
            elif accepted["type"] == "idea_review" and str(payload["id"]) not in existing_reviews:
                review = from_dict(IdeaReviewRecord, {**payload, "provenance": to_plain(_import_provenance(task, str(payload["id"])))})
                state.reviews.append(review)
                existing_reviews.add(review.id)
            elif accepted["type"] == "agenda_item":
                direction_id = str(payload.get("id") or _stable_id("agenda", task.project_id, str(payload.get("title") or task.id)))
                if not any(direction.id == direction_id for direction in project.research_directions):
                    project.research_directions.append(
                        ResearchDirection(
                            id=direction_id,
                            project_id=task.project_id,
                            title=str(payload.get("title") or direction_id),
                            summary=str(payload.get("summary") or ""),
                            maturity="agenda_item",
                            next_actions=_strings(payload.get("next_actions")),
                            blocking_issues=_strings(payload.get("blocking_issues")),
                            provenance=_import_provenance(task, direction_id),
                        )
                    )
        self.idea_store._save_state(task.project_id, state)
        self.project_manager.save_project(project)
        for path in paths:
            if path.exists():
                (Path(task.task_dir) / f"imported_{path.name}").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    def _task_context(self, project_id: str, task_type: str) -> dict[str, Any]:
        program = self.project_manager.load_project(project_id)
        state = self.idea_store.load_state(project_id)
        portfolios = self.topic_portfolios.list_project_portfolios(project_id)
        run_states = []
        for run_id in program.run_ids:
            try:
                run_states.append(self.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        prior_work_blockers = [
            {
                "idea_id": candidate.id,
                "title": candidate.title,
                "novelty_status": candidate.novelty_status,
                "closest_prior_work_ids": candidate.closest_prior_work_ids,
                "counterevidence_paper_ids": candidate.counterevidence_paper_ids,
                "rejection_reason": candidate.rejection_reason,
            }
            for candidate in state.candidates
            if candidate.closest_prior_work_ids or candidate.counterevidence_paper_ids or candidate.rejection_reason
        ]
        human_preferences = [
            to_plain(review)
            for review in state.reviews
            if review.status in {"accepted", "rejected", "revise"} or review.notes or review.required_fixes
        ]
        return {
            "task_id": "",
            "task_type": task_type,
            "project": to_plain(program.project),
            "topic_portfolio": to_plain(portfolios[-1]) if portfolios else {},
            "existing_idea_bank": to_plain(state.idea_bank),
            "idea_candidates": to_plain(state.candidates),
            "rejected_ideas": to_plain([candidate for candidate in state.candidates if candidate.maturity == "rejected"]),
            "prior_work_blockers": prior_work_blockers,
            "source_coverage_summary": _source_coverage_summary(program, run_states),
            "evidence_links": to_plain(state.evidence_links),
            "human_preferences": human_preferences,
            "constructive_gaps": to_plain(state.constructive_gaps),
            "transfer_candidates": to_plain(state.transfer_candidates),
            "output_schemas": _schema_examples(),
            "rules": {
                "no_fake_citations_or_results": True,
                "public_reasoning_summary_only": True,
                "strong_novelty_requires_prior_work_gate": True,
                "ideas_are_seeds_until_imported_and_gated": True,
            },
            "known_ids": {key: sorted(value) for key, value in self._known_ids(project_id).items()},
        }

    def _known_ids(self, project_id: str) -> dict[str, set[str]]:
        program = self.project_manager.load_project(project_id)
        state = self.idea_store.load_state(project_id)
        paper_ids = {record.paper_id for record in program.corpus_papers}
        paper_ids.update(paper_id for record in program.memory_records for paper_id in record.linked_paper_ids)
        paper_ids.update(paper_id for candidate in state.candidates for paper_id in candidate.closest_prior_work_ids)
        paper_ids.update(paper_id for candidate in state.candidates for paper_id in candidate.supporting_paper_ids)
        paper_ids.update(paper_id for candidate in state.candidates for paper_id in candidate.counterevidence_paper_ids)
        paper_ids.update(paper_id for link in state.evidence_links for paper_id in [link.paper_id] if paper_id)
        evidence_span_ids = {link.evidence_span_id for link in state.evidence_links if link.evidence_span_id}
        claim_ids = {link.claim_id for link in state.evidence_links if link.claim_id}
        for run_id in program.run_ids:
            try:
                run = self.state_manager.load_run(run_id)
            except FileNotFoundError:
                continue
            paper_ids.update(paper.id for paper in run.papers)
            evidence_span_ids.update(span.id for span in run.evidence_spans if span.id)
            claim_ids.update(claim.id for claim in run.claims if claim.id)
        return {
            "paper_ids": {item for item in paper_ids if item},
            "evidence_span_ids": {item for item in evidence_span_ids if item},
            "claim_ids": {item for item in claim_ids if item},
            "idea_ids": {candidate.id for candidate in state.candidates},
        }


def _validate_idea_candidate_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    title = str(item.get("title") or "").strip()
    item["title"] = title
    if is_generic_idea_title(title):
        item["maturity"] = "rejected"
        return False, "generic idea rejected", item
    contribution_type = str(item.get("contribution_type") or "").strip()
    if not contribution_type:
        return False, "idea candidate missing contribution type", item
    try:
        validate_contribution_type(contribution_type)
    except ValueError as exc:
        return False, str(exc), item
    novelty = str(item.get("novelty_status") or "unchecked")
    try:
        validate_novelty_status(novelty)
    except ValueError as exc:
        return False, str(exc), item
    item["novelty_status"] = novelty
    if _contains_result_claim(item):
        return False, "results are not accepted in idea synthesis patches", item
    cited = _claimed_paper_ids(item)
    unknown = sorted(cited - known["paper_ids"])
    if unknown:
        return False, f"fake or unresolved citation IDs rejected: {', '.join(unknown)}", item
    spans = set(_strings(item.get("evidence_span_ids")))
    unknown_spans = sorted(spans - known["evidence_span_ids"])
    if unknown_spans:
        return False, f"candidate evidence links do not resolve: {', '.join(unknown_spans)}", item
    if novelty == "strong" and not _strings(item.get("closest_prior_work_ids")):
        return False, "strong novelty rejected unless prior-work gates exist", item
    item.setdefault("maturity", "seed")
    item.setdefault("novelty_status", "unchecked")
    item.setdefault("summary", "")
    item.setdefault("likely_failure_mode", "Codex-generated seed must pass novelty, evidence, and human review gates.")
    return True, "", item


def _validate_mutation_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    if not item.get("source_idea_id") or not item.get("mutated_idea_id"):
        return False, "mutation patch requires source_idea_id and mutated_idea_id", item
    if item["source_idea_id"] not in known["idea_ids"] or item["mutated_idea_id"] not in known["idea_ids"]:
        return False, "mutation idea IDs must resolve before import", item
    try:
        validate_mutation_strategy(str(item.get("strategy") or ""))
    except ValueError as exc:
        return False, str(exc), item
    if not item.get("what_changed") or not item.get("why_it_may_help"):
        return False, "mutation must explain what changed and why it may help", item
    return True, "", item


def _validate_constructive_gap_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    unknown = sorted(set(_strings(item.get("closest_prior_work_ids"))) - known["paper_ids"])
    if unknown:
        return False, f"fake or unresolved citation IDs rejected: {', '.join(unknown)}", item
    try:
        validate_constructive_gap_candidate(from_dict(ConstructiveGapCandidate, item))
    except ValueError as exc:
        return False, str(exc), item
    return True, "", item


def _validate_transfer_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    if not item.get("transfer_mechanism"):
        return False, "transfer must state mechanism", item
    if not item.get("what_breaks"):
        return False, "transfer must state what breaks", item
    unknown = sorted(set(_strings(item.get("supporting_source_papers"))) - known["paper_ids"])
    if unknown:
        return False, f"fake or unresolved citation IDs rejected: {', '.join(unknown)}", item
    return True, "", item


def _validate_review_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    if item.get("idea_id") not in known["idea_ids"]:
        return False, "review idea_id must resolve", item
    try:
        validate_review_status(str(item.get("status") or ""))
    except ValueError as exc:
        return False, str(exc), item
    return True, "", item


def _validate_agenda_patch(item: dict[str, Any], known: dict[str, set[str]]) -> tuple[bool, str, dict[str, Any]]:
    if _contains_result_claim(item):
        return False, "results are not accepted in agenda patches", item
    if not item.get("title") and not item.get("summary"):
        return False, "agenda patch requires title or summary", item
    return True, "", item


def _render_prompt(task: IdeaCodexTask, context: dict[str, Any]) -> str:
    return f"""# GapForge v2 Idea Codex Task

- Task ID: `{task.id}`
- Project ID: `{task.project_id}`
- Task type: `{task.task_type}`
- Model target: Codex/GPT-5.4

You are helping synthesize v2 idea-discovery artifacts. Outputs are proposals only. GapForge will validate them before import.

## Required Context

This task pack includes:
- `task_context.json`: topic portfolio, existing idea bank, rejected ideas, prior-work blockers, source coverage summary,
  evidence links, human preferences, constructive gaps, and transfer candidates.
- `expected_outputs.json`: exact required output filenames.
- `schema_examples.json`: exact JSON output schemas.
- `validation_rules.md`: import gate rules.

## Hard Rules

- Do not invent citations.
- Do not invent results.
- Do not claim strong novelty unless the output includes prior-work gates using known IDs.
- Do not treat speculative seeds as paper-ready.
- Use public reasoning summaries only. Do not include private chain-of-thought.
- If evidence is missing, emit a required search or weak/unchecked seed rather than a confident candidate.
- Generic ideas must be rejected, narrowed, or clearly marked as weak seeds.

## Expected Outputs

Write JSON files only under `outputs/`:
{chr(10).join(f"- `{name}`" for name in IDEA_CODEX_OUTPUTS)}

## Task Context Snapshot

```json
{json.dumps(context, indent=2)}
```
"""


def _expected_outputs() -> dict[str, Any]:
    return {
        "files": {
            filename: {
                "top_key": top_key,
                "path": f"outputs/{filename}",
                "public_reasoning_summary": "required",
            }
            for filename, top_key in OUTPUT_TOP_KEYS.items()
        }
    }


def _schema_examples() -> dict[str, Any]:
    return {
        "idea_candidates_patch.json": {
            "idea_candidates": [
                {
                    "title": "Specific, non-generic seed title",
                    "summary": "What the seed proposes and why it is still uncertain.",
                    "contribution_type": "benchmark",
                    "core_claim": "Unchecked claim, phrased as a hypothesis.",
                    "proposed_experiment": "Minimum test plan without results.",
                    "expected_baselines": ["known baseline"],
                    "expected_metrics": ["false positive rate"],
                    "closest_prior_work_ids": ["known-paper-id"],
                    "evidence_span_ids": ["known-span-id"],
                    "novelty_status": "unchecked",
                    "maturity": "seed",
                    "likely_failure_mode": "Why this may fail.",
                }
            ],
            "public_reasoning_summary": "Evidence-grounded public summary only.",
        },
        "idea_mutations_patch.json": {
            "idea_mutations": [
                {
                    "id": "idea-mutation-id",
                    "source_idea_id": "known-idea-id",
                    "mutated_idea_id": "known-idea-id",
                    "strategy": "metric_shift",
                    "what_changed": "What changed.",
                    "why_it_may_help": "Why this may help.",
                    "inherited_risks": ["risk retained"],
                    "required_new_searches": ["search query"],
                }
            ],
            "public_reasoning_summary": "Public summary only.",
        },
        "constructive_gaps_patch.json": {
            "constructive_gaps": [
                {
                    "id": "constructive-gap-id",
                    "project_id": "project-id",
                    "title": "Benchmark paper candidate",
                    "contribution_type": "benchmark",
                    "problem": "Problem statement.",
                    "why_existing_work_makes_this_useful": "Evidence-grounded reason.",
                    "minimum_artifact": "Required artifact.",
                    "minimum_experiment": "Metrics and falsifiable evaluation.",
                    "required_baselines": ["baseline"],
                    "closest_prior_work_ids": ["known-paper-id"],
                    "novelty_risk": "Risk.",
                    "reviewer_risk": "Risk.",
                    "feasibility": "Feasibility.",
                    "evidence_links": ["closest_prior_work:known-paper-id"],
                }
            ],
            "public_reasoning_summary": "Public summary only.",
        },
        "transfer_candidates_patch.json": {
            "transfer_candidates": [
                {
                    "id": "idea-transfer-id",
                    "source_field": "medicine screening/specificity",
                    "source_concept": "screening specificity",
                    "target_problem": "target problem",
                    "transfer_mechanism": "Technical transfer mechanism.",
                    "target_idea_id": "",
                    "required_adaptation": "Required adaptation.",
                    "what_breaks": "What breaks.",
                    "supporting_source_papers": ["known-paper-id"],
                    "required_searches": ["search query"],
                    "confidence": "low",
                }
            ],
            "public_reasoning_summary": "Public summary only.",
        },
        "idea_reviews_patch.json": {
            "idea_reviews": [
                {
                    "id": "idea-review-id",
                    "idea_id": "known-idea-id",
                    "reviewer": "codex",
                    "status": "revise",
                    "novelty_judgment": "Judgment.",
                    "feasibility_judgment": "Judgment.",
                    "impact_judgment": "Judgment.",
                    "required_fixes": ["fix"],
                    "notes": "Notes.",
                }
            ],
            "public_reasoning_summary": "Public summary only.",
        },
        "agenda_patch.json": {
            "agenda": {
                "title": "Research agenda title",
                "summary": "Agenda fallback summary.",
                "next_actions": ["action"],
                "blocking_issues": ["issue"],
            },
            "public_reasoning_summary": "Public summary only.",
        },
    }


def _validation_rules_markdown() -> str:
    return """# Idea Codex Validation Rules

- Idea candidates must include `contribution_type`.
- Claimed paper IDs must already exist in GapForge project memory, idea evidence, or run state.
- Claimed evidence span IDs must resolve to known evidence spans.
- Fake citations are rejected.
- Strong novelty is rejected unless closest-prior-work gates are present.
- Generic ideas are rejected or downgraded before import.
- Results, performance claims, and invented findings are rejected.
- Outputs must include public reasoning summaries only.
"""


def _source_coverage_summary(program, run_states) -> dict[str, Any]:  # noqa: ANN001
    return {
        "corpus_paper_count": len(program.corpus_papers),
        "memory_record_count": len(program.memory_records),
        "run_count": len(run_states),
        "known_run_papers": sum(len(state.papers) for state in run_states),
        "known_evidence_spans": sum(len(state.evidence_spans) for state in run_states),
    }


def _normalize_task_type(task_type: str) -> str:
    if task_type not in IDEA_CODEX_TASK_TYPES:
        raise ValueError(f"Unsupported idea Codex task type: {task_type}. Expected one of: {', '.join(sorted(IDEA_CODEX_TASK_TYPES))}")
    return task_type


def _object_type(filename: str) -> str:
    return {
        "idea_candidates_patch.json": "idea_candidate",
        "idea_mutations_patch.json": "idea_mutation",
        "constructive_gaps_patch.json": "constructive_gap",
        "transfer_candidates_patch.json": "transfer_candidate",
        "idea_reviews_patch.json": "idea_review",
        "agenda_patch.json": "agenda_item",
    }[filename]


def _items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _claimed_paper_ids(item: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ["closest_prior_work_ids", "supporting_paper_ids", "counterevidence_paper_ids", "paper_ids"]:
        ids.update(_strings(item.get(key)))
    return ids


def _contains_result_claim(item: dict[str, Any]) -> bool:
    text = json.dumps(item, sort_keys=True).lower()
    return any(marker in text for marker in RESULT_CLAIM_MARKERS) or any(
        key in item for key in ["results", "result", "observed_results", "main_results", "performance_claim"]
    )


def _rejected_file(path: Path, reason: str) -> dict[str, str]:
    return {"type": "file", "id": path.name, "source_path": str(path), "reason": reason}


def _import_provenance(task: IdeaCodexTask, object_id: str) -> Provenance:
    return Provenance(
        created_by_skill="idea-codex-import",
        source_ids=[task.project_id, task.id, object_id],
        timestamp=utc_now_iso(),
        reasoning_summary="Imported a validated Codex idea-synthesis output. Evidence gates remain in force.",
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:8]
    readable = slugify(parts[-1])[:48] or "untitled"
    return f"{prefix}-{readable}-{digest}"
