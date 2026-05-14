"""Revision workflow driven by drastic reviewer-panel output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import ExperimentCodeTask, Provenance, SearchQueryRecord, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reviewers.drastic_panel import DrasticReviewPanel, DrasticReviewPanelBuilder
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class DrasticRevisionPlan:
    id: str
    manuscript_id: str
    review_panel_id: str
    fatal_fixes: list[str] = field(default_factory=list)
    major_fixes: list[str] = field(default_factory=list)
    optional_fixes: list[str] = field(default_factory=list)
    new_experiments_required: list[str] = field(default_factory=list)
    new_related_work_required: list[str] = field(default_factory=list)
    claim_softening_required: list[str] = field(default_factory=list)
    manuscript_rewrites_required: list[str] = field(default_factory=list)
    artifact_updates_required: list[str] = field(default_factory=list)
    status: str = "blocked"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="drastic-revision-plan"))


class DrasticRevisionManager:
    """Convert harsh reviewer objections into concrete manuscript revision tasks."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscripts = ManuscriptManager(config)
        self.projects = ProjectMemoryManager(config)

    def build(self, manuscript_id: str) -> DrasticRevisionPlan:
        panel = _load_or_build_panel(self.config, manuscript_id)
        plan = _plan_from_panel(manuscript_id, panel)
        self._write_plan(plan)
        self._create_project_requests(plan)
        self._mark_claims_for_softening(plan)
        self._downgrade_publication_candidate_if_blocked(plan)
        return plan

    def apply(self, manuscript_id: str, *, dry_run: bool = False) -> DrasticRevisionPlan:
        panel = _load_or_build_panel(self.config, manuscript_id)
        plan = _plan_from_panel(manuscript_id, panel)
        if dry_run:
            return plan
        self._write_plan(plan)
        self._create_project_requests(plan)
        self._mark_claims_for_softening(plan)
        self._downgrade_publication_candidate_if_blocked(plan)
        return plan

    def load(self, manuscript_id: str) -> DrasticRevisionPlan:
        path = self._plan_path(manuscript_id)
        if not path.exists():
            return self.build(manuscript_id)
        return from_dict(DrasticRevisionPlan, json.loads(path.read_text(encoding="utf-8")))

    def status(self, manuscript_id: str) -> str:
        plan = self.load(manuscript_id)
        self._downgrade_publication_candidate_if_blocked(plan)
        return render_drastic_revision_status(plan)

    def render_markdown(self, plan: DrasticRevisionPlan) -> str:
        return render_drastic_revision_plan(plan)

    def _write_plan(self, plan: DrasticRevisionPlan) -> None:
        root = self.manuscripts.manuscript_root(plan.manuscript_id)
        drastic_dir = root / "reviews" / "drastic"
        drastic_dir.mkdir(parents=True, exist_ok=True)
        (drastic_dir / "drastic_revision_plan.json").write_text(json.dumps(to_plain(plan), indent=2) + "\n", encoding="utf-8")
        (drastic_dir / "drastic_revision_plan.md").write_text(render_drastic_revision_plan(plan), encoding="utf-8")
        (drastic_dir / "drastic_revision_status.md").write_text(render_drastic_revision_status(plan), encoding="utf-8")

    def _plan_path(self, manuscript_id: str) -> Path:
        return self.manuscripts.manuscript_root(manuscript_id) / "reviews" / "drastic" / "drastic_revision_plan.json"

    def _create_project_requests(self, plan: DrasticRevisionPlan) -> None:
        state = self.manuscripts.load_state(plan.manuscript_id)
        program = self.projects.load_project(state.manuscript.project_id)
        for request in plan.new_related_work_required:
            record = SearchQueryRecord(
                id=f"search-drastic-revision-{slugify(plan.manuscript_id)}-{slugify(request)[:32]}",
                query=_search_query_from_fix(request),
                purpose="drastic_revision_related_work",
                max_results=20,
                provenance=Provenance(
                    created_by_skill="drastic-revision-plan",
                    source_ids=[plan.id, plan.review_panel_id, plan.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created related-work search request from drastic reviewer blocker.",
                ),
            )
            if record.id not in {item.id for item in program.revision_search_requests}:
                program.revision_search_requests.append(record)
        for request in plan.new_experiments_required:
            task = ExperimentCodeTask(
                id=f"experiment-task-drastic-{slugify(plan.manuscript_id)}-{slugify(request)[:28]}",
                campaign_id="",
                direction_id=state.manuscript.direction_id,
                experiment_protocol_id="",
                task_type="drastic_revision_experiment",
                instructions=request,
                expected_outputs=[
                    "new result artifact or explicit failed-run record",
                    "updated manuscript limitation if evidence remains missing",
                ],
                validation_commands=["gapforge parse-results --execution-id <execution-id>"],
                status="planned",
                provenance=Provenance(
                    created_by_skill="drastic-revision-plan",
                    source_ids=[plan.id, plan.review_panel_id, plan.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created experiment request from drastic reviewer blocker.",
                ),
            )
            if task.id not in {item.id for item in program.experiment_code_tasks}:
                program.experiment_code_tasks.append(task)
        self.projects.save_project(program)

    def _mark_claims_for_softening(self, plan: DrasticRevisionPlan) -> None:
        if not plan.claim_softening_required:
            return
        state = self.manuscripts.load_state(plan.manuscript_id)
        changed = False
        for claim_use in state.claim_uses:
            if claim_use.support_status == "unsupported" or _claim_matches_softening(claim_use.claim_text, plan):
                claim_use.requires_softening = True
                changed = True
        if changed:
            state.provenance.append(
                Provenance(
                    created_by_skill="drastic-revision-plan",
                    source_ids=[plan.id, plan.review_panel_id, plan.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Marked overstrong or unsupported manuscript claims for softening after drastic review.",
                )
            )
            self.manuscripts._save_state(state)

    def _downgrade_publication_candidate_if_blocked(self, plan: DrasticRevisionPlan) -> None:
        if not plan.fatal_fixes and plan.status not in {"blocked", "fatal_blockers_open"}:
            return
        state = self.manuscripts.load_state(plan.manuscript_id)
        if state.manuscript.status in {"submission_ready", "camera_ready", "publication_candidate"}:
            state.manuscript.status = "review_ready"
            state.provenance.append(
                Provenance(
                    created_by_skill="drastic-revision-plan",
                    source_ids=[plan.id, plan.review_panel_id, plan.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Revoked publication-candidate readiness because drastic review fatal blockers remain.",
                )
            )
            self.manuscripts._save_state(state)


def render_drastic_revision_plan(plan: DrasticRevisionPlan) -> str:
    lines = [
        f"# Drastic Revision Plan `{plan.manuscript_id}`",
        "",
        "This plan creates fixes and evidence requests. It does not invent rebuttal answers or excuse real blockers.",
        "",
        f"- Status: `{plan.status}`",
        f"- Review panel: `{plan.review_panel_id}`",
        "",
        "## Fatal Fixes",
        "",
        *[f"- {item}" for item in (plan.fatal_fixes or ["none"])],
        "",
        "## Major Fixes",
        "",
        *[f"- {item}" for item in (plan.major_fixes or ["none"])],
        "",
        "## Optional Fixes",
        "",
        *[f"- {item}" for item in (plan.optional_fixes or ["none"])],
        "",
        "## New Experiments Required",
        "",
        *[f"- {item}" for item in (plan.new_experiments_required or ["none"])],
        "",
        "## New Related Work Required",
        "",
        *[f"- {item}" for item in (plan.new_related_work_required or ["none"])],
        "",
        "## Claim Softening Required",
        "",
        *[f"- {item}" for item in (plan.claim_softening_required or ["none"])],
        "",
        "## Manuscript Rewrites Required",
        "",
        *[f"- {item}" for item in (plan.manuscript_rewrites_required or ["none"])],
        "",
        "## Artifact Updates Required",
        "",
        *[f"- {item}" for item in (plan.artifact_updates_required or ["none"])],
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_drastic_revision_status(plan: DrasticRevisionPlan) -> str:
    return (
        f"# Drastic Revision Status `{plan.manuscript_id}`\n\n"
        f"- Status: `{plan.status}`\n"
        f"- Fatal fixes open: {len(plan.fatal_fixes)}\n"
        f"- Major fixes open: {len(plan.major_fixes)}\n"
        f"- Publication candidate allowed: {str(not plan.fatal_fixes).lower()}\n"
        f"- New experiments required: {len(plan.new_experiments_required)}\n"
        f"- New related-work searches required: {len(plan.new_related_work_required)}\n"
        f"- Claim softening required: {len(plan.claim_softening_required)}\n"
    )


def drastic_revision_plan_json(plan: DrasticRevisionPlan) -> str:
    return json.dumps(to_plain(plan), indent=2) + "\n"


def _load_or_build_panel(config: GapForgeConfig, manuscript_id: str) -> DrasticReviewPanel:
    root = ManuscriptManager(config).manuscript_root(manuscript_id)
    path = root / "reviews" / "drastic" / "drastic_review_panel.json"
    if path.exists():
        return from_dict(DrasticReviewPanel, json.loads(path.read_text(encoding="utf-8")))
    return DrasticReviewPanelBuilder(config).review_manuscript(manuscript_id)


def _plan_from_panel(manuscript_id: str, panel: DrasticReviewPanel) -> DrasticRevisionPlan:
    fatal_fixes = _unique([*_prefix_fixes("fatal", panel.fatal_flaws)])
    major_fixes = _unique([*_review_required_fixes(panel), *_major_weakness_fixes(panel)])
    optional_fixes = _unique([question for review in panel.reviewer_reports for question in review.questions])
    all_fixes = _unique([*fatal_fixes, *major_fixes, *optional_fixes])
    experiments = _unique([item for item in all_fixes if _experiment_like(item)])
    related_work = _unique([item for item in all_fixes if _related_work_like(item)])
    softening = _unique([item for item in all_fixes if _softening_like(item)])
    rewrites = _unique([item for item in all_fixes if _rewrite_like(item)])
    artifacts = _unique([item for item in all_fixes if _artifact_like(item)])
    status = "fatal_blockers_open" if fatal_fixes else "needs_revision" if major_fixes else "ready"
    return DrasticRevisionPlan(
        id=f"drastic-revision-plan-{slugify(manuscript_id)}",
        manuscript_id=manuscript_id,
        review_panel_id=panel.id,
        fatal_fixes=fatal_fixes,
        major_fixes=major_fixes,
        optional_fixes=optional_fixes,
        new_experiments_required=experiments,
        new_related_work_required=related_work,
        claim_softening_required=softening,
        manuscript_rewrites_required=rewrites,
        artifact_updates_required=artifacts,
        status=status,
        provenance=Provenance(
            created_by_skill="drastic-revision-plan",
            source_ids=[manuscript_id, panel.id, *[review.reviewer_id for review in panel.reviewer_reports]],
            timestamp=utc_now_iso(),
            reasoning_summary=(
                "Converted drastic review output into concrete revision tasks without treating rebuttal as a blocker bypass."
            ),
        ),
    )


def _prefix_fixes(prefix: str, fixes: list[str]) -> list[str]:
    return [f"{prefix}:{fix}" if not fix.startswith(f"{prefix}:") else fix for fix in fixes]


def _review_required_fixes(panel: DrasticReviewPanel) -> list[str]:
    return _unique([fix for review in panel.reviewer_reports for fix in review.required_fixes])


def _major_weakness_fixes(panel: DrasticReviewPanel) -> list[str]:
    fixes = []
    for review in panel.reviewer_reports:
        for weakness in review.weaknesses:
            fixes.append(f"address:{review.reviewer_id}:{weakness}")
    return fixes


def _experiment_like(value: str) -> bool:
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in [
            "experiment",
            "benchmark_results",
            "result_artifacts",
            "result artifact",
            "baseline",
            "ablation",
            "uncertainty",
            "power",
            "low-fpr",
            "negative samples",
        ]
    )


def _related_work_like(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ["related_work", "related-work", "prior work", "closest prior", "must-read", "citation"])


def _softening_like(value: str) -> bool:
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in ["unsupported_claim", "unsupported claim", "overclaim", "soften", "sota", "first/", "solves", "claim"]
    )


def _rewrite_like(value: str) -> bool:
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in ["section:", "introduction", "method", "results", "limitations", "related_work", "claims", "manuscript"]
    )


def _artifact_like(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ["artifact", "package", "replication", "workspace"])


def _claim_matches_softening(claim_text: str, plan: DrasticRevisionPlan) -> bool:
    lowered = claim_text.lower()
    if any(marker in lowered for marker in ["definitively", "solves", "state-of-the-art", "first"]):
        return True
    return any(claim.lower() in lowered or lowered in claim.lower() for claim in plan.claim_softening_required)


def _search_query_from_fix(fix: str) -> str:
    cleaned = fix.replace("fatal:", "").replace("address:", "").replace("section:", "").replace("missing:", "")
    return f"closest prior work and benchmark evidence for {cleaned[:160]}"


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        result.append(normalized)
        seen.add(normalized)
    return result
