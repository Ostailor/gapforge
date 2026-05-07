"""Manuscript revision plan integration with search and experiment systems."""

from __future__ import annotations

import json

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import RevisionPlan
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager, render_rebuttal_plan_markdown
from gapforge.models import ExperimentCodeTask, Provenance, SearchQueryRecord, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso


class ManuscriptRevisionManager:
    """Create revision plans and project-level requests from rebuttal items."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.rebuttal_manager = ManuscriptRebuttalManager(config)

    def build(self, manuscript_id: str) -> RevisionPlan:
        revision = self.rebuttal_manager.build(manuscript_id)
        self._create_project_requests(revision)
        self._write_revision_status(revision)
        return revision

    def status(self, manuscript_id: str) -> str:
        revision = self.rebuttal_manager.load_revision(manuscript_id)
        self._enforce_camera_ready_boundary(revision)
        return render_revision_status_markdown(revision)

    def render_markdown(self, revision: RevisionPlan) -> str:
        return render_revision_plan_markdown(revision)

    def _create_project_requests(self, revision: RevisionPlan) -> None:
        state = self.manuscript_manager.load_state(revision.manuscript_id)
        program = self.project_manager.load_project(state.manuscript.project_id)
        for search in revision.required_searches:
            record = SearchQueryRecord(
                id=f"search-revision-{slugify(revision.manuscript_id)}-{slugify(search)[:32]}",
                query=search,
                purpose="manuscript_revision",
                max_results=20,
                executed_at="",
                provenance=Provenance(
                    created_by_skill="manuscript-revisions",
                    source_ids=[revision.id, revision.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created manuscript revision search/citation request from reviewer feedback.",
                ),
            )
            if record.id not in {item.id for item in program.revision_search_requests}:
                program.revision_search_requests.append(record)
        for experiment in revision.required_experiments:
            task = ExperimentCodeTask(
                id=f"experiment-task-revision-{slugify(revision.manuscript_id)}-{slugify(experiment)[:28]}",
                campaign_id="",
                direction_id=state.manuscript.direction_id,
                experiment_protocol_id="",
                task_type="manuscript_revision_experiment",
                instructions=experiment,
                expected_outputs=["updated result artifact or explicit failed-run record"],
                validation_commands=["gapforge parse-results --execution-id <execution-id>"],
                status="planned",
                provenance=Provenance(
                    created_by_skill="manuscript-revisions",
                    source_ids=[revision.id, revision.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created manuscript revision experiment request from reviewer feedback.",
                ),
            )
            if task.id not in {item.id for item in program.experiment_code_tasks}:
                program.experiment_code_tasks.append(task)
        self.project_manager.save_project(program)

    def _write_revision_status(self, revision: RevisionPlan) -> None:
        root = self.manuscript_manager.manuscript_root(revision.manuscript_id)
        reviews_dir = root / "reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        (reviews_dir / "revision_plan.md").write_text(render_revision_plan_markdown(revision), encoding="utf-8")
        (reviews_dir / "revision_status.md").write_text(render_revision_status_markdown(revision), encoding="utf-8")

    def _enforce_camera_ready_boundary(self, revision: RevisionPlan) -> None:
        manuscript_state = self.manuscript_manager.load_state(revision.manuscript_id)
        if manuscript_state.manuscript.status == "camera_ready" and revision.status != "addressed":
            manuscript_state.manuscript.status = "review_ready"
            manuscript_state.provenance.append(
                Provenance(
                    created_by_skill="manuscript-revisions",
                    source_ids=[revision.id, revision.manuscript_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Blocked camera_ready because required rebuttal/revision items remain open.",
                )
            )
            self.manuscript_manager._save_state(manuscript_state)


def render_revision_plan_markdown(revision: RevisionPlan) -> str:
    lines = [
        f"# Revision Plan `{revision.manuscript_id}`",
        "",
        f"- Status: `{revision.status}`",
        "",
        "## Section Edits",
        "",
    ]
    lines.extend([f"- {item}" for item in revision.section_edits] or ["- none"])
    lines.extend(["", "## Required Experiments", ""])
    lines.extend([f"- {item}" for item in revision.required_experiments] or ["- none"])
    lines.extend(["", "## Required Searches", ""])
    lines.extend([f"- {item}" for item in revision.required_searches] or ["- none"])
    lines.extend(["", "## Required Citations", ""])
    lines.extend([f"- {item}" for item in revision.required_citations] or ["- none"])
    lines.extend(["", render_rebuttal_plan_markdown(revision).rstrip()])
    return "\n".join(lines).rstrip() + "\n"


def render_revision_status_markdown(revision: RevisionPlan) -> str:
    open_items = [item for item in revision.rebuttal_items if item.status == "open"]
    lines = [
        f"# Revision Status `{revision.manuscript_id}`",
        "",
        f"- Status: `{revision.status}`",
        f"- Open rebuttal items: {len(open_items)}",
        f"- Camera-ready allowed: {str(revision.status == 'addressed').lower()}",
        "",
    ]
    if open_items:
        lines.extend(["## Open Items", ""])
        lines.extend(f"- `{item.id}` from `{item.reviewer_id}`: {item.objection}" for item in open_items)
    return "\n".join(lines).rstrip() + "\n"


def revision_json(revision: RevisionPlan) -> str:
    return json.dumps(to_plain(revision), indent=2) + "\n"
