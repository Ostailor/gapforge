"""Dry-run planning for broad v0.5 real-literature campaigns."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

from gapforge.config import GapForgeConfig
from gapforge.models import RealLiteratureCampaignProfile
from gapforge.real_literature.profiles import get_real_literature_profile
from gapforge.search_strategy import plan_search_strategy
from gapforge.sources.policies import get_source_policy_profile
from gapforge.state import slugify, utc_now_compact


@dataclass(slots=True)
class RealCampaignBudgetEstimate:
    max_papers: int
    max_expanded_papers: int
    expected_source_checks: int
    planned_search_rounds: int
    planned_search_queries: int
    expected_codex_tasks: int
    expected_artifacts: int
    estimated_review_steps: int
    budget_label: str


@dataclass(slots=True)
class RealCampaignDryRunPlan:
    id: str
    profile_id: str
    topic: str
    source_profile: str
    expected_source_checks: list[str]
    planned_search_rounds: list[dict[str, object]]
    expected_codex_tasks: list[str]
    expected_artifacts: list[str]
    budget_estimate: RealCampaignBudgetEstimate
    likely_blockers: list[str] = field(default_factory=list)
    commands_to_run: list[str] = field(default_factory=list)
    acceptance_requirements: list[str] = field(default_factory=list)


def build_real_campaign_dry_run(
    config: GapForgeConfig,
    *,
    profile_id: str = "",
    topic: str = "",
    source_profile: str = "generic",
) -> RealCampaignDryRunPlan:
    """Build a deterministic no-network plan for a real-literature campaign."""

    profile = _profile_from_inputs(profile_id=profile_id, topic=topic, source_profile=source_profile)
    strategy = plan_search_strategy(config, profile.topic, source_profile=profile.source_profile)
    rounds = _planned_rounds(strategy)
    source_checks = _dedupe([*profile.required_live_sources, *profile.recommended_live_sources])
    codex_tasks = _codex_tasks_for_profile(profile)
    artifacts = _dedupe(
        [
            "live_source_diagnostic_latest.md",
            "search_strategy.md",
            "search_rounds.md",
            "paper_merge_report.md",
            "prior_work_recall_report.md",
            "real_literature_campaign_report.md",
            *profile.expected_artifacts,
        ]
    )
    likely_blockers = _likely_blockers(profile, source_checks)
    budget = RealCampaignBudgetEstimate(
        max_papers=profile.max_papers,
        max_expanded_papers=profile.max_expanded_papers,
        expected_source_checks=len(source_checks),
        planned_search_rounds=len(rounds),
        planned_search_queries=sum(len(_round_queries(round_item)) for round_item in rounds),
        expected_codex_tasks=len(codex_tasks),
        expected_artifacts=len(artifacts),
        estimated_review_steps=3,
        budget_label=_budget_label(profile.max_papers, len(codex_tasks)),
    )
    plan_id = f"real-campaign-dry-run-{slugify(profile.id or profile.topic)}-{utc_now_compact()}"
    return RealCampaignDryRunPlan(
        id=plan_id,
        profile_id=profile.id,
        topic=profile.topic,
        source_profile=profile.source_profile,
        expected_source_checks=source_checks,
        planned_search_rounds=rounds,
        expected_codex_tasks=codex_tasks,
        expected_artifacts=artifacts,
        budget_estimate=budget,
        likely_blockers=likely_blockers,
        commands_to_run=_commands(profile),
        acceptance_requirements=_acceptance_requirements(profile),
    )


def write_real_campaign_dry_run(config: GapForgeConfig, plan: RealCampaignDryRunPlan) -> tuple[Path, Path]:
    """Persist a dry-run report under ignored data artifacts."""

    out_dir = config.data_dir / "real_literature" / "dry_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{plan.id}.json"
    md_path = out_dir / f"{plan.id}.md"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"
    payload = json.dumps(asdict(plan), indent=2) + "\n"
    rendered = render_real_campaign_dry_run(plan)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(rendered, encoding="utf-8")
    latest_json.write_text(payload, encoding="utf-8")
    latest_md.write_text(rendered, encoding="utf-8")
    return latest_json, latest_md


def render_real_campaign_dry_run(plan: RealCampaignDryRunPlan) -> str:
    lines = [
        f"# Real Campaign Dry Run: {plan.topic}",
        "",
        f"- Dry-run ID: `{plan.id}`",
        f"- Profile: `{plan.profile_id}`",
        f"- Source profile: `{plan.source_profile}`",
        "",
        "## Expected Source Checks",
        "",
    ]
    lines.extend(f"- {source}" for source in plan.expected_source_checks)
    lines.extend(["", "## Planned Search Rounds", ""])
    for round_item in plan.planned_search_rounds:
        queries = _round_queries(round_item)
        sources = _round_sources(round_item)
        lines.extend(
            [
                f"- `{round_item['round_type']}`: {len(queries)} querie(s), "
                f"sources={', '.join(sources) or 'none'}, max_results={round_item['max_results']}",
            ]
        )
    lines.extend(["", "## Expected Codex Tasks", ""])
    lines.extend(f"- {task}" for task in plan.expected_codex_tasks)
    lines.extend(
        [
            "",
            "## Expected Artifacts",
            "",
            f"- Expected artifact count: {plan.budget_estimate.expected_artifacts}",
        ]
    )
    lines.extend(f"- {artifact}" for artifact in plan.expected_artifacts)
    lines.extend(
        [
            "",
            "## Estimated Budget",
            "",
            f"- Budget label: `{plan.budget_estimate.budget_label}`",
            f"- Max papers: {plan.budget_estimate.max_papers}",
            f"- Max expanded papers: {plan.budget_estimate.max_expanded_papers}",
            f"- Source checks: {plan.budget_estimate.expected_source_checks}",
            f"- Search rounds: {plan.budget_estimate.planned_search_rounds}",
            f"- Search queries: {plan.budget_estimate.planned_search_queries}",
            f"- Codex tasks: {plan.budget_estimate.expected_codex_tasks}",
            f"- Human review/attestation steps: {plan.budget_estimate.estimated_review_steps}",
            "",
            "## Likely Blockers",
            "",
        ]
    )
    lines.extend(f"- {blocker}" for blocker in plan.likely_blockers or ["none detected in dry-run inputs"])
    lines.extend(["", "## Commands To Run", ""])
    for command in plan.commands_to_run:
        lines.extend(["```bash", command, "```"])
    lines.extend(["", "## What Counts As Acceptance", ""])
    lines.extend(f"- {requirement}" for requirement in plan.acceptance_requirements)
    lines.extend(
        [
            "",
            "This is a dry run. It does not contact live sources, spend Codex budget, import outputs, or satisfy "
            "real-literature acceptance by itself.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _profile_from_inputs(*, profile_id: str, topic: str, source_profile: str) -> RealLiteratureCampaignProfile:
    if profile_id:
        return get_real_literature_profile(profile_id)
    if not topic:
        raise ValueError("Either --profile or --topic is required for real-campaign-dry-run.")
    policy = get_source_policy_profile(source_profile)
    return RealLiteratureCampaignProfile(
        id=f"custom_{slugify(topic)[:48]}",
        title=f"Custom real-literature campaign for {topic}",
        topic=topic,
        source_profile=policy.id,
        required_live_sources=policy.required_sources,
        recommended_live_sources=policy.recommended_sources,
        max_papers=max(policy.minimum_papers, 30),
        max_expanded_papers=20,
        min_real_papers=policy.minimum_papers,
        min_full_text_or_abstract_notes=policy.minimum_full_text_papers,
        min_closest_prior_work=2,
        expected_artifacts=[
            "live_source_diagnostic_latest.md",
            "search_strategy.md",
            "search_rounds.md",
            "prior_work_recall_report.md",
            "campaign_report.md",
            "real_literature_campaign_report.md",
        ],
        acceptance_criteria=[
            "Live source diagnostics meet the selected source policy.",
            "Prior-work recall gate completes before any novelty claim.",
            "Human quality review accepts or the campaign refuses recommendation for a documented reason.",
        ],
        known_risks=["Custom dry runs may need profile-specific acceptance criteria before release validation."],
    )


def _planned_rounds(strategy: Any) -> list[dict[str, object]]:
    source_names = list(strategy.expected_sources)
    return [
        _round("initial", strategy.primary_queries + strategy.recency_queries, source_names, 12),
        _round("survey", strategy.survey_queries, source_names, 8),
        _round("benchmark", strategy.benchmark_queries + strategy.dataset_queries, source_names, 8),
        _round("novelty", strategy.closest_prior_work_queries, source_names, 12),
        _round("adjacent_field", strategy.adjacent_field_queries, source_names, 8),
        _round("counterevidence", strategy.exclusion_queries, source_names, 8),
    ]


def _round(round_type: str, queries: list[str], sources: list[str], max_results: int) -> dict[str, object]:
    return {
        "round_type": round_type,
        "queries": _dedupe(queries),
        "sources": sources,
        "max_results": max_results,
    }


def _round_queries(round_item: dict[str, object]) -> list[str]:
    return cast(list[str], round_item.get("queries", []))


def _round_sources(round_item: dict[str, object]) -> list[str]:
    return cast(list[str], round_item.get("sources", []))


def _codex_tasks_for_profile(profile: RealLiteratureCampaignProfile) -> list[str]:
    tasks = [
        "research_synthesis",
        "novelty_reviewer",
        "related_work",
        "reviewer_panel",
    ]
    if profile.min_full_text_or_abstract_notes:
        tasks.insert(0, "deep_reader_batch")
    if any("experiment" in artifact for artifact in profile.expected_artifacts):
        tasks.append("experiment_architect")
    return tasks


def _likely_blockers(profile: RealLiteratureCampaignProfile, source_checks: list[str]) -> list[str]:
    blockers: list[str] = []
    if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
        blockers.append("GAPFORGE_DISABLE_NETWORK=1 is set; live source checks and real-literature acceptance will be blocked.")
    if "pubmed" in {source.lower() for source in source_checks}:
        blockers.append("PubMed is a policy requirement but GapForge currently records it as a placeholder/unavailable source.")
    if not profile.required_live_sources:
        blockers.append("No required live sources are specified; acceptance will rely on explicit human/source-policy review.")
    if profile.min_real_papers > profile.max_papers:
        blockers.append("Minimum real paper requirement exceeds max_papers.")
    blockers.extend(profile.known_risks[:3])
    return _dedupe(blockers)


def _commands(profile: RealLiteratureCampaignProfile) -> list[str]:
    return [
        f'gapforge live-source-diagnostic --topic "{profile.topic}" --source-profile {profile.source_profile} --write-report',
        f"gapforge real-literature-run --profile {profile.id}"
        if not profile.id.startswith("custom_")
        else (f'gapforge campaign-create "{profile.topic}" --project-id <project-id>'),
        "gapforge campaign-run --campaign-id <campaign-id> --real-literature --mode codex_task_pack",
        "gapforge research-synthesis-task --campaign-id <campaign-id>",
        "gapforge codex-handoff --task-id <task-id> --print-prompt",
        "gapforge validate-import-all --task-id <task-id>",
        'gapforge real-literature-review --campaign-id <campaign-id> --accept-quality --reviewer "<name>"',
        "gapforge v5-release-gate --write-report",
    ]


def _acceptance_requirements(profile: RealLiteratureCampaignProfile) -> list[str]:
    return _dedupe(
        [
            "Live source diagnostic passes or the campaign explicitly refuses recommendation due to insufficient coverage.",
            f"At least {profile.min_real_papers} real non-fallback papers are collected unless the profile is a refusal profile.",
            (
                f"At least {profile.min_full_text_or_abstract_notes} full-text or abstract notes are available "
                "when a direction is recommended."
            ),
            f"At least {profile.min_closest_prior_work} closest-prior-work item(s) are considered before novelty is strengthened.",
            "Prior-work recall gate is recorded and missing search rounds are visible.",
            "Codex outputs are validated/imported, attested when applicable, and human-reviewed.",
            "No fake citations, unsupported high-confidence claims, or overclaimed novelty appear in accepted outputs.",
            *profile.acceptance_criteria,
        ]
    )


def _budget_label(max_papers: int, codex_tasks: int) -> str:
    if max_papers <= 20 and codex_tasks <= 4:
        return "small"
    if max_papers <= 60 and codex_tasks <= 6:
        return "medium"
    return "large"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
