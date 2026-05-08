"""Lock a v2 selected idea and convert it into a v2.1 research project."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaCandidate, IdeaScoreRecord, IdeaTournament
from gapforge.ideas.store import IdeaStore
from gapforge.models import ProjectMemoryRecord, Provenance, ResearchDirection, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso

SELECTED_IDEA_PROJECT_STATUSES = {
    "locked",
    "benchmark_spec_ready",
    "experiment_ready",
    "smoke_validated",
    "pilot_validated",
    "manuscript_ready",
}
CANONICAL_RESEARCH_QUESTION = "Can a sequential benchmark evaluate collusion monitors at operationally meaningful low false-positive rates?"
DEFAULT_CONTRIBUTION_STATEMENT = (
    "Define and smoke-validate a sequential specificity benchmark for low-FPR collusion audits, including honest-agent "
    "traffic, collusive scenarios, hard negatives, baseline monitors, sequential false-alarm metrics, and artifact-backed "
    "analysis that separates smoke evidence from scientific claims."
)


@dataclass(slots=True)
class SelectedIdeaProject:
    id: str
    project_id: str
    source_idea_id: str
    title: str
    research_question: str
    contribution_statement: str
    target_contribution_type: str
    status: str = "locked"
    locked_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-idea-project"))


@dataclass(slots=True)
class SelectedIdeaLock:
    id: str
    idea_id: str
    locked_by: str
    lock_reason: str
    accepted_review_ids: list[str] = field(default_factory=list)
    blocked_mutations: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-idea-lock"))


class SelectedIdeaProjectManager:
    """Manage the frozen v2 idea that becomes the v2.1 research target."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.idea_store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)

    def lock_selected_idea(
        self,
        idea_id: str,
        *,
        locked_by: str = "human",
        lock_reason: str = "Freeze the v2 selected idea as the canonical v2.1 research target.",
        force: bool = False,
    ) -> SelectedIdeaLock:
        state, candidate = self.idea_store.load_by_idea_id(idea_id)
        lock_path = self._source_lock_path(candidate.project_id)
        existing = self._load_lock(lock_path)
        if existing is not None and existing.idea_id != idea_id and not force:
            raise ValueError(f"Selected idea is already locked to {existing.idea_id}; use --force only after recording an explicit pivot.")
        if existing is not None and existing.idea_id == idea_id and not force:
            return existing

        now = utc_now_iso()
        lock = SelectedIdeaLock(
            id=_stable_id("selected-idea-lock", candidate.project_id, idea_id),
            idea_id=idea_id,
            locked_by=locked_by,
            lock_reason=lock_reason,
            accepted_review_ids=_accepted_review_ids(state, idea_id),
            blocked_mutations=_blocked_mutations(state, idea_id),
            created_at=now,
            provenance=Provenance(
                created_by_skill="selected-idea-lock",
                source_ids=[candidate.project_id, idea_id],
                timestamp=now,
                reasoning_summary=("Locked the selected v2 idea to prevent silent replacement during v2.1 execution planning."),
            ),
        )
        self._write_json(lock_path, lock)
        self._write_snapshot(candidate.project_id, lock, candidate)
        self._record_source_project_memory(candidate.project_id, lock, candidate, force=force)
        return lock

    def create_selected_project(
        self,
        idea_id: str,
        *,
        locked_by: str = "human",
        lock_reason: str = "Freeze the v2 selected idea as the canonical v2.1 research target.",
        force: bool = False,
    ) -> SelectedIdeaProject:
        lock = self.lock_selected_idea(idea_id, locked_by=locked_by, lock_reason=lock_reason, force=force)
        _, candidate = self.idea_store.load_by_idea_id(idea_id)
        existing = self.find_selected_project(idea_id)
        if existing is not None and not force:
            return existing

        now = utc_now_iso()
        program = self.project_manager.create_project(
            f"v2.1 {candidate.title}",
            description=CANONICAL_RESEARCH_QUESTION,
        )
        selected_project = SelectedIdeaProject(
            id=_stable_id("selected-idea-project", program.project.id, idea_id),
            project_id=program.project.id,
            source_idea_id=idea_id,
            title=candidate.title,
            research_question=CANONICAL_RESEARCH_QUESTION,
            contribution_statement=_contribution_statement(candidate),
            target_contribution_type=candidate.contribution_type or "benchmark",
            status="locked",
            locked_at=lock.created_at or now,
            provenance=Provenance(
                created_by_skill="selected-idea-project",
                source_ids=[candidate.project_id, idea_id, lock.id],
                timestamp=now,
                reasoning_summary="Converted the frozen v2 selected idea into a dedicated v2.1 research project.",
            ),
        )
        project_root = Path(program.project.root_dir)
        selected_dir = self._selected_dir(program.project.id)
        self._write_json(selected_dir / "selected_idea_project.json", selected_project)
        self._write_json(selected_dir / "selected_idea_lock.json", lock)
        self._write_snapshot(program.project.id, lock, candidate, source_project_id=candidate.project_id)
        self._initialize_artifact_links(project_root)

        program = self.project_manager.load_project(program.project.id)
        program.memory_records.append(_selected_project_memory_record(selected_project, source_project_id=candidate.project_id))
        program.research_directions.append(_selected_project_direction(selected_project, candidate))
        self.project_manager.save_project(program)
        return selected_project

    def find_selected_project(self, idea_id: str) -> SelectedIdeaProject | None:
        for project in self.project_manager.list_projects():
            path = self._selected_project_path(project.id)
            if not path.exists():
                continue
            selected_project = from_dict(SelectedIdeaProject, json.loads(path.read_text(encoding="utf-8")))
            if selected_project.source_idea_id == idea_id:
                return selected_project
        return None

    def load_selected_project(self, project_id: str) -> SelectedIdeaProject:
        path = self._selected_project_path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"No selected idea project record found for {project_id}")
        return from_dict(SelectedIdeaProject, json.loads(path.read_text(encoding="utf-8")))

    def load_project_lock(self, project_id: str) -> SelectedIdeaLock:
        path = self._selected_dir(project_id) / "selected_idea_lock.json"
        lock = self._load_lock(path)
        if lock is None:
            raise FileNotFoundError(f"No selected idea lock found for {project_id}")
        return lock

    def render_status(self, project_id: str) -> str:
        selected_project = self.load_selected_project(project_id)
        lock = self.load_project_lock(project_id)
        source_state, candidate = self.idea_store.load_by_idea_id(selected_project.source_idea_id)
        score = _latest_score(source_state.tournaments, selected_project.source_idea_id)
        rejected = _rejected_ideas(source_state)
        project_root = Path(self.project_manager.load_project(project_id).project.root_dir)
        source_project_id = candidate.project_id

        lines = [
            "# Selected Idea Project Status",
            "",
            f"- Project ID: `{selected_project.project_id}`",
            f"- Status: `{selected_project.status}`",
            f"- Source idea ID: `{selected_project.source_idea_id}`",
            f"- Source project ID: `{source_project_id}`",
            f"- Title: {selected_project.title}",
            f"- Research question: {selected_project.research_question}",
            f"- Contribution type: `{selected_project.target_contribution_type}`",
            f"- Locked by: {lock.locked_by}",
            f"- Locked at: {lock.created_at or selected_project.locked_at}",
            f"- Lock reason: {lock.lock_reason}",
            "",
            "## Contribution Statement",
            "",
            selected_project.contribution_statement,
            "",
            "## Provenance",
            "",
            f"- Accepted review IDs: {', '.join(lock.accepted_review_ids) or 'none recorded'}",
            f"- Blocked mutations: {', '.join(lock.blocked_mutations) or 'none recorded'}",
            f"- Candidate maturity: `{candidate.maturity}`",
            f"- Candidate novelty status: `{candidate.novelty_status}`",
            f"- Closest prior work: {', '.join(candidate.closest_prior_work_ids) or 'none recorded'}",
            "",
            "## Tournament Snapshot",
            "",
        ]
        if score is None:
            lines.append("- No tournament score found for the selected idea.")
        else:
            lines.extend(
                [
                    f"- Total score: {score.total_score:.3f}",
                    f"- Evidence score: {score.evidence_score:.3f}",
                    f"- Novelty score: {score.novelty_score:.3f}",
                    f"- Experimentability score: {score.experimentability_score:.3f}",
                    f"- Blockers: {'; '.join(score.blockers) or 'none'}",
                ]
            )
        lines.extend(["", "## Preserved Rejected Ideas", ""])
        if rejected:
            lines.extend(f"- `{idea.id}` {idea.title}: {idea.rejection_reason or idea.maturity}" for idea in rejected[:20])
        else:
            lines.append("- none recorded")
        lines.extend(
            [
                "",
                "## Artifact Links",
                "",
                f"- Selected project record: `{_relative(project_root / 'ideas' / 'selected_idea_project.json', self.config.root)}`",
                f"- Lock record: `{_relative(project_root / 'ideas' / 'selected_idea_lock.json', self.config.root)}`",
                f"- Provenance snapshot: `{_relative(project_root / 'ideas' / 'selected_idea_snapshot.json', self.config.root)}`",
                f"- Campaign artifacts: `{_relative(project_root / 'campaigns', self.config.root)}`",
                f"- Benchmark artifacts: `{_relative(project_root / 'benchmark_suites', self.config.root)}`",
                f"- Experiment artifacts: `{_relative(project_root / 'experiment_workspaces', self.config.root)}`",
                f"- Manuscript artifacts: `{_relative(project_root / 'manuscripts', self.config.root)}`",
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    def write_status(self, project_id: str) -> str:
        status = self.render_status(project_id)
        reports_dir = self._selected_dir(project_id) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "selected_idea_status.md").write_text(status, encoding="utf-8")
        return status

    def _source_lock_path(self, project_id: str) -> Path:
        return self._selected_dir(project_id) / "selected_idea_lock.json"

    def _selected_project_path(self, project_id: str) -> Path:
        return self._selected_dir(project_id) / "selected_idea_project.json"

    def _selected_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        ideas_dir = Path(program.project.root_dir) / "ideas"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        return ideas_dir

    def _load_lock(self, path: Path) -> SelectedIdeaLock | None:
        if not path.exists():
            return None
        return from_dict(SelectedIdeaLock, json.loads(path.read_text(encoding="utf-8")))

    def _write_snapshot(
        self,
        project_id: str,
        lock: SelectedIdeaLock,
        candidate: IdeaCandidate,
        *,
        source_project_id: str = "",
    ) -> None:
        source_state = self.idea_store.load_state(source_project_id or candidate.project_id)
        snapshot = {
            "lock": to_plain(lock),
            "candidate": to_plain(candidate),
            "latest_tournament": to_plain(source_state.tournaments[-1]) if source_state.tournaments else None,
            "selected_score": to_plain(_latest_score(source_state.tournaments, candidate.id)),
            "rejected_ideas": to_plain(_rejected_ideas(source_state)),
            "idea_bank": to_plain(source_state.idea_bank),
        }
        self._write_json(self._selected_dir(project_id) / "selected_idea_snapshot.json", snapshot)

    def _record_source_project_memory(
        self,
        project_id: str,
        lock: SelectedIdeaLock,
        candidate: IdeaCandidate,
        *,
        force: bool = False,
    ) -> None:
        program = self.project_manager.load_project(project_id)
        record_id = f"selected-lock-{lock.id}"
        if force:
            program.memory_records = [record for record in program.memory_records if record.id != record_id]
        if any(record.id == record_id for record in program.memory_records):
            return
        program.memory_records.append(
            ProjectMemoryRecord(
                id=record_id,
                project_id=project_id,
                record_type="decision",
                text=f"Locked selected idea `{candidate.id}` for v2.1 execution: {candidate.title}",
                linked_object_ids=[candidate.id, lock.id],
                status="locked",
                confidence="high",
                created_at=lock.created_at,
                updated_at=lock.created_at,
                provenance=lock.provenance,
            )
        )
        self.project_manager.save_project(program)

    def _initialize_artifact_links(self, project_root: Path) -> None:
        for relative in ["campaigns", "benchmark_suites", "experiment_workspaces", "manuscripts", "ideas/reports"]:
            (project_root / relative).mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def validate_selected_idea_project_status(status: str) -> str:
    if status not in SELECTED_IDEA_PROJECT_STATUSES:
        raise ValueError(f"Unsupported selected idea project status: {status}")
    return status


def render_selected_idea_status(config: GapForgeConfig, project_id: str) -> str:
    return SelectedIdeaProjectManager(config).render_status(project_id)


def _accepted_review_ids(state: Any, idea_id: str) -> list[str]:
    review_ids = [review.id for review in state.reviews if review.idea_id == idea_id and review.status == "accepted"]
    feedback_ids = [feedback.id for feedback in state.feedback_records if feedback.idea_id == idea_id and feedback.action == "accept"]
    return _unique([*review_ids, *feedback_ids])


def _blocked_mutations(state: Any, idea_id: str) -> list[str]:
    blocked: list[str] = []
    rejected_ids = set(state.idea_bank.rejected_candidate_ids if state.idea_bank is not None else [])
    for mutation in state.mutations:
        if mutation.source_idea_id == idea_id:
            blocked.append(mutation.id)
        if mutation.mutated_idea_id in rejected_ids:
            blocked.append(mutation.id)
    for candidate in state.candidates:
        if candidate.id != idea_id and (candidate.maturity == "rejected" or candidate.rejection_reason):
            blocked.append(candidate.id)
    for tournament in state.tournaments:
        blocked.extend(tournament.rejected_candidate_ids)
    return _unique(blocked)


def _latest_score(tournaments: list[IdeaTournament], idea_id: str) -> IdeaScoreRecord | None:
    for tournament in reversed(tournaments):
        for score in tournament.score_records:
            if score.idea_id == idea_id:
                return score
    return None


def _rejected_ideas(state: Any) -> list[IdeaCandidate]:
    rejected_ids = set(state.idea_bank.rejected_candidate_ids if state.idea_bank is not None else [])
    rejected: list[IdeaCandidate] = []
    for candidate in state.candidates:
        if candidate.id in rejected_ids or candidate.maturity == "rejected" or candidate.rejection_reason:
            rejected.append(candidate)
    return rejected


def _contribution_statement(candidate: IdeaCandidate) -> str:
    if candidate.core_claim:
        return f"{DEFAULT_CONTRIBUTION_STATEMENT} Candidate claim to preserve: {candidate.core_claim}"
    return DEFAULT_CONTRIBUTION_STATEMENT


def _selected_project_memory_record(selected_project: SelectedIdeaProject, *, source_project_id: str) -> ProjectMemoryRecord:
    now = utc_now_iso()
    return ProjectMemoryRecord(
        id=f"selected-project-{selected_project.id}",
        project_id=selected_project.project_id,
        record_type="decision",
        text=(
            f"Created dedicated v2.1 research project for frozen idea `{selected_project.source_idea_id}` from "
            f"source project `{source_project_id}`."
        ),
        linked_object_ids=[selected_project.source_idea_id, selected_project.id, source_project_id],
        status="locked",
        confidence="high",
        created_at=now,
        updated_at=now,
        provenance=selected_project.provenance,
    )


def _selected_project_direction(selected_project: SelectedIdeaProject, candidate: IdeaCandidate) -> ResearchDirection:
    return ResearchDirection(
        id=f"direction-{slugify(selected_project.source_idea_id)}",
        project_id=selected_project.project_id,
        title=selected_project.title,
        summary=selected_project.research_question,
        supporting_paper_ids=list(candidate.supporting_paper_ids),
        counterevidence_paper_ids=list(candidate.counterevidence_paper_ids),
        maturity="candidate",
        readiness_score=0.35,
        blocking_issues=[
            "benchmark specification not yet release-gate ready",
            "smoke run not yet validated",
            "manuscript package not yet updated",
        ],
        next_actions=[
            "write benchmark specification",
            "define threat model and observability assumptions",
            "create runnable benchmark smoke path",
            "update manuscript package from result artifacts",
        ],
        provenance=selected_project.provenance,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "::".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    readable = slugify(parts[-1])[:48] or "selected"
    return f"{prefix}-{readable}-{digest}"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
