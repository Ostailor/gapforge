"""Project-level memory persistence for multi-run research programs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import (
    BaselineCandidate,
    Claim,
    ClaimGraph,
    CorpusPaperRecord,
    ExperimentPlan,
    ExperimentProtocol,
    Gap,
    HumanReviewRecord,
    ProjectMemoryRecord,
    ProjectTopic,
    Provenance,
    RejectedIdea,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchProject,
    ResearchRunState,
    ReviewerObjection,
    ReviewPanel,
    ReviewQueue,
    from_dict,
    to_plain,
)
from gapforge.redaction import redact_text
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

PROJECT_ARTIFACTS = [
    "project.json",
    "topics.json",
    "corpus_papers.json",
    "memory_records.json",
    "research_directions.json",
    "related_work_matrices.json",
    "related_work_matrix.md",
    "experiment_protocols.json",
    "experiment_protocols.md",
    "baseline_candidates.json",
    "baseline_candidates.md",
    "review_panels.json",
    "review_panel.md",
    "rebuttal_plan.md",
    "meta_review.md",
    "review_queue.json",
    "review_queue.md",
    "claim_graph.json",
    "claim_graph.md",
    "project_report.md",
]


class ProjectMemoryManager:
    """Durable manager for v0.3 project-level memory."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def create_project(self, name: str, description: str = "") -> ResearchProgramState:
        project_slug = slugify(name)
        project_id = project_slug
        root_dir = self.config.project_root / project_id
        suffix = 2
        while root_dir.exists():
            project_id = f"{project_slug}-{suffix}"
            root_dir = self.config.project_root / project_id
            suffix += 1
        root_dir.mkdir(parents=True, exist_ok=False)
        (root_dir / "runs").mkdir(parents=True, exist_ok=True)
        (root_dir / "reports").mkdir(parents=True, exist_ok=True)
        now = utc_now_iso()
        project = ResearchProject(
            id=project_id,
            name=name,
            description=description,
            root_dir=str(root_dir),
            created_at=now,
            updated_at=now,
            corpus_id=f"{project_id}-corpus",
            provenance=_project_provenance("init-project", [], "Project memory root initialized."),
        )
        program = ResearchProgramState(project=project, run_ids=[])
        self.save_project(program)
        return program

    def list_projects(self) -> list[ResearchProject]:
        projects: list[ResearchProject] = []
        if not self.config.project_root.exists():
            return projects
        for path in sorted(self.config.project_root.iterdir()):
            project_path = path / "project.json"
            if path.is_dir() and project_path.exists():
                projects.append(from_dict(ResearchProject, json.loads(project_path.read_text(encoding="utf-8"))))
        return projects

    def use_project(self, project_id: str) -> ResearchProject:
        program = self.load_project(project_id)
        active_path = self._active_project_path()
        active_path.parent.mkdir(parents=True, exist_ok=True)
        active_path.write_text(json.dumps({"project_id": program.project.id}, indent=2) + "\n", encoding="utf-8")
        return program.project

    def active_project_id(self) -> str:
        active_path = self._active_project_path()
        if not active_path.exists():
            return ""
        raw = json.loads(active_path.read_text(encoding="utf-8"))
        return str(raw.get("project_id", ""))

    def load_project(self, project_id: str) -> ResearchProgramState:
        root_dir = self._project_dir(project_id)
        project_path = root_dir / "project.json"
        if not project_path.exists():
            raise FileNotFoundError(f"No project found for {project_id}")
        project = from_dict(ResearchProject, json.loads(project_path.read_text(encoding="utf-8")))
        topics = _load_list(root_dir / "topics.json", ProjectTopic)
        corpus_papers = _load_list(root_dir / "corpus_papers.json", CorpusPaperRecord)
        memory_records = _load_list(root_dir / "memory_records.json", ProjectMemoryRecord)
        research_directions = _load_list(root_dir / "research_directions.json", ResearchDirection)
        related_work_matrices = _load_list(root_dir / "related_work_matrices.json", RelatedWorkMatrix)
        experiment_protocols = _load_list(root_dir / "experiment_protocols.json", ExperimentProtocol)
        baseline_candidates = _load_list(root_dir / "baseline_candidates.json", BaselineCandidate)
        review_panels = _load_list(root_dir / "review_panels.json", ReviewPanel)
        review_queue = None
        review_queue_path = root_dir / "review_queue.json"
        if review_queue_path.exists():
            raw_review_queue = json.loads(review_queue_path.read_text(encoding="utf-8"))
            review_queue = from_dict(ReviewQueue, raw_review_queue) if raw_review_queue else None
        claim_graph = None
        claim_graph_path = root_dir / "claim_graph.json"
        if claim_graph_path.exists():
            raw_claim_graph = json.loads(claim_graph_path.read_text(encoding="utf-8"))
            claim_graph = from_dict(ClaimGraph, raw_claim_graph) if raw_claim_graph else None
        run_ids = list(project.run_ids)
        return ResearchProgramState(
            project=project,
            topics=topics,
            corpus_papers=corpus_papers,
            memory_records=memory_records,
            research_directions=research_directions,
            related_work_matrices=related_work_matrices,
            experiment_protocols=experiment_protocols,
            baseline_candidates=baseline_candidates,
            review_panels=review_panels,
            review_queue=review_queue,
            claim_graph=claim_graph,
            run_ids=run_ids,
        )

    def save_project(self, program: ResearchProgramState) -> None:
        root_dir = Path(program.project.root_dir or self._project_dir(program.project.id))
        root_dir.mkdir(parents=True, exist_ok=True)
        (root_dir / "runs").mkdir(parents=True, exist_ok=True)
        (root_dir / "reports").mkdir(parents=True, exist_ok=True)
        program.project.root_dir = str(root_dir)
        program.project.run_ids = _unique(program.run_ids or program.project.run_ids)
        program.project.active_topic_ids = _unique(program.project.active_topic_ids)
        program.project.updated_at = utc_now_iso()
        self._write_json(root_dir / "project.json", program.project)
        self._write_json(root_dir / "topics.json", program.topics)
        self._write_json(root_dir / "corpus_papers.json", program.corpus_papers)
        self._write_json(root_dir / "memory_records.json", program.memory_records)
        self._write_json(root_dir / "research_directions.json", program.research_directions)
        self._write_json(root_dir / "related_work_matrices.json", program.related_work_matrices)
        self._write_json(root_dir / "experiment_protocols.json", program.experiment_protocols)
        self._write_json(root_dir / "baseline_candidates.json", program.baseline_candidates)
        self._write_json(root_dir / "review_panels.json", program.review_panels)
        self._write_json(root_dir / "review_queue.json", program.review_queue)
        self._write_json(root_dir / "claim_graph.json", program.claim_graph)
        self._write_related_work_matrix_markdown(program, root_dir)
        self._write_experiment_protocols_markdown(program, root_dir)
        self._write_baseline_candidates_markdown(program, root_dir)
        self._write_review_panel_markdown(program, root_dir)
        self._write_review_queue_markdown(program, root_dir)
        if program.claim_graph is not None:
            from gapforge.claims.graph import render_claim_graph_markdown

            (root_dir / "claim_graph.md").write_text(render_claim_graph_markdown(program.claim_graph), encoding="utf-8")
        elif not (root_dir / "claim_graph.md").exists():
            (root_dir / "claim_graph.md").write_text("# Project Claim Graph\n\nNo claim graph built yet.\n", encoding="utf-8")
        self.write_project_report(program)

    def attach_run(self, project_id: str, run_id: str) -> ResearchProgramState:
        program = self.load_project(project_id)
        state = ResearchStateManager(self.config).load_run(run_id)
        if run_id not in program.run_ids:
            program.run_ids.append(run_id)
        if run_id not in program.project.run_ids:
            program.project.run_ids.append(run_id)
        topic = self._topic_from_run(program.project.id, state)
        if topic.id not in {item.id for item in program.topics}:
            program.topics.append(topic)
            if topic.id not in program.project.active_topic_ids:
                program.project.active_topic_ids.append(topic.id)
        self._write_run_pointer(program, state)
        self.save_project(program)
        return program

    def sync_project_memory(self, project_id: str) -> ResearchProgramState:
        program = self.load_project(project_id)
        state_manager = ResearchStateManager(self.config)
        loaded_runs = [state_manager.load_run(run_id) for run_id in program.run_ids]
        program.corpus_papers = self._sync_corpus_papers(program, loaded_runs)
        program.memory_records = self._sync_memory_records(program, loaded_runs)
        program.research_directions = self._sync_research_directions(program, loaded_runs)
        for state in loaded_runs:
            topic = self._topic_from_run(program.project.id, state)
            if topic.id not in {item.id for item in program.topics}:
                program.topics.append(topic)
        self.save_project(program)
        return program

    def write_project_report(self, program: ResearchProgramState) -> Path:
        root_dir = Path(program.project.root_dir or self._project_dir(program.project.id))
        report_path = root_dir / "project_report.md"
        rejected = [record for record in program.memory_records if record.status == "rejected" or record.record_type == "rejected_idea"]
        decisions = [record for record in program.memory_records if record.record_type == "decision"]
        locked = [record for record in decisions if "lock" in record.text.lower()]
        directions = sorted(program.research_directions, key=lambda item: item.readiness_score, reverse=True)
        lines = [
            f"# GapForge Project Report: {program.project.name}",
            "",
            f"- Project ID: `{program.project.id}`",
            f"- Status: {program.project.status}",
            f"- Runs attached: {len(program.run_ids)}",
            f"- Topics: {len(program.topics)}",
            f"- Corpus papers: {len(program.corpus_papers)}",
            f"- Memory records: {len(program.memory_records)}",
            f"- Research directions: {len(program.research_directions)}",
            f"- Experiment protocols: {len(program.experiment_protocols)}",
            "",
            "## Topics",
            "",
        ]
        lines.extend([f"- `{topic.id}` {topic.text} [{topic.status}]" for topic in program.topics] or ["- none"])
        lines.extend(["", "## Corpus Summary", ""])
        lines.extend(
            [
                f"- `{record.paper_id}` {record.canonical_title} (seen in {len(record.seen_run_ids)} run(s), trust={record.trust_level})"
                for record in program.corpus_papers[:20]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Research Directions", ""])
        lines.extend(
            [
                f"- `{direction.id}` {direction.title} [{direction.maturity}, readiness={direction.readiness_score:.2f}]"
                for direction in directions[:20]
            ]
            or ["- none"]
        )
        top_direction = next((direction for direction in directions if direction.maturity != "rejected"), None)
        lines.extend(["", "## Top Mature Direction", ""])
        if top_direction is None:
            lines.append("- No non-rejected research direction is ready to recommend across runs.")
        else:
            lines.extend(
                [
                    f"- `{top_direction.id}` {top_direction.title}",
                    f"- Maturity: {top_direction.maturity}",
                    f"- Readiness score: {top_direction.readiness_score:.2f}",
                    f"- Blocking issues: {'; '.join(top_direction.blocking_issues) or 'none'}",
                    f"- Next actions: {'; '.join(top_direction.next_actions) or 'none'}",
                ]
            )
        lines.extend(["", "## Related Work Matrices", ""])
        lines.extend(
            [
                f"- `{matrix.direction_id}` entries={len(matrix.entries)}, "
                f"must-read={len(matrix.must_read_paper_ids)}, baselines={len(matrix.baseline_paper_ids)}"
                for matrix in program.related_work_matrices[:20]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Experiment Protocols", ""])
        lines.extend(
            [
                f"- `{protocol.id}` direction={protocol.direction_id}, experiment={protocol.linked_experiment_plan_id}, "
                f"baselines={len(protocol.baselines)}, metrics={len(protocol.metrics)}"
                for protocol in program.experiment_protocols[:20]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Review Panels", ""])
        lines.extend(
            [
                f"- `{panel.experiment_or_direction_id}` risk={panel.decision_risk}, "
                f"reviews={len(panel.reviewer_reviews)}, required_changes={len(panel.required_changes)}"
                for panel in program.review_panels[:20]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Review Queue", ""])
        open_queue_items = [item for item in (program.review_queue.items if program.review_queue else []) if item.status == "open"]
        lines.extend(
            [
                f"- `{item.id}` {item.priority} `{item.object_type}:{item.object_id}`"
                + (f" run={item.run_id}" if item.run_id else "")
                + f": {item.reason}"
                for item in open_queue_items[:20]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Rejected Ideas", ""])
        lines.extend([f"- `{record.id}` {record.text}" for record in rejected[:20]] or ["- none"])
        lines.extend(["", "## Human Decisions", ""])
        lines.extend([f"- `{record.id}` {record.text}" for record in decisions[:20]] or ["- none"])
        lines.extend(["", "## Locked Objects", ""])
        lines.extend([f"- `{record.id}` {record.text}" for record in locked[:20]] or ["- none"])
        lines.extend(["", "## Claim Graph", ""])
        if program.claim_graph is None:
            lines.append("- No project claim graph built yet.")
        else:
            contradiction_count = len(program.claim_graph.unresolved_contradictions)
            lines.extend(
                [
                    f"- Claim nodes: {len(program.claim_graph.nodes)}",
                    f"- Claim edges: {len(program.claim_graph.edges)}",
                    f"- Unresolved contradictions: {contradiction_count}",
                ]
            )
            lines.extend([f"- {item}" for item in program.claim_graph.unresolved_contradictions[:10]] or ["- none"])
        lines.extend(
            [
                "",
                "## Caveats",
                "",
                "- Project memory is context, not proof. Current-run reports must still check source coverage, evidence, and novelty.",
                "- Rejected ideas and human decisions are preserved to prevent accidental rediscovery.",
                "- Deliberate revisiting should use explicit revision notes rather than silent overwrite.",
            ]
        )
        report_path.write_text(redact_text("\n".join(lines).rstrip() + "\n"), encoding="utf-8")
        reports_dir = root_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "project_report.md").write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
        return report_path

    def _write_related_work_matrix_markdown(self, program: ResearchProgramState, root_dir: Path) -> None:
        path = root_dir / "related_work_matrix.md"
        if not program.related_work_matrices:
            path.write_text("# Related Work Matrix\n\nNo related-work matrices generated yet.\n", encoding="utf-8")
            return
        from gapforge.related_work.renderer import render_related_work_matrices_markdown

        path.write_text(render_related_work_matrices_markdown(program.related_work_matrices), encoding="utf-8")

    def _write_experiment_protocols_markdown(self, program: ResearchProgramState, root_dir: Path) -> None:
        path = root_dir / "experiment_protocols.md"
        if not program.experiment_protocols:
            path.write_text("# Experiment Protocols\n\nNo experiment protocols generated yet.\n", encoding="utf-8")
            return
        from gapforge.experiments.protocol import render_protocols_markdown

        path.write_text(render_protocols_markdown(program.experiment_protocols), encoding="utf-8")

    def _write_baseline_candidates_markdown(self, program: ResearchProgramState, root_dir: Path) -> None:
        path = root_dir / "baseline_candidates.md"
        if not program.baseline_candidates:
            path.write_text("# Baseline Candidates\n\nNo baseline candidates generated yet.\n", encoding="utf-8")
            return
        from gapforge.experiments.baselines import render_baseline_candidates_markdown

        path.write_text(render_baseline_candidates_markdown(program.baseline_candidates), encoding="utf-8")

    def _write_review_panel_markdown(self, program: ResearchProgramState, root_dir: Path) -> None:
        from gapforge.reviewers.panel import render_review_panel_markdown
        from gapforge.reviewers.rebuttal import render_meta_review_markdown, render_rebuttal_plans_markdown

        panel_path = root_dir / "review_panel.md"
        rebuttal_path = root_dir / "rebuttal_plan.md"
        meta_path = root_dir / "meta_review.md"
        if not program.review_panels:
            panel_path.write_text("# Review Panel\n\nNo review panel generated yet.\n", encoding="utf-8")
            rebuttal_path.write_text("# Rebuttal Plan\n\nNo review panel generated yet.\n", encoding="utf-8")
            meta_path.write_text("# Meta Review\n\nNo review panel generated yet.\n", encoding="utf-8")
            return
        panel_path.write_text(
            "\n\n".join(render_review_panel_markdown(panel).rstrip() for panel in program.review_panels) + "\n",
            encoding="utf-8",
        )
        rebuttal_path.write_text(render_rebuttal_plans_markdown(program.review_panels), encoding="utf-8")
        meta_path.write_text(render_meta_review_markdown(program.review_panels), encoding="utf-8")

    def _write_review_queue_markdown(self, program: ResearchProgramState, root_dir: Path) -> None:
        from gapforge.review.queue import render_review_queue_markdown

        (root_dir / "review_queue.md").write_text(render_review_queue_markdown(program.review_queue), encoding="utf-8")

    def _sync_corpus_papers(
        self,
        program: ResearchProgramState,
        loaded_runs: list[ResearchRunState],
    ) -> list[CorpusPaperRecord]:
        records_by_key: dict[str, CorpusPaperRecord] = {}
        for existing in program.corpus_papers:
            records_by_key[_corpus_key_from_record(existing)] = existing
        for state in loaded_runs:
            artifacts_by_paper: dict[str, list[str]] = {}
            for artifact in state.paper_artifacts:
                artifacts_by_paper.setdefault(artifact.paper_id, []).append(artifact.id)
            for paper in state.papers:
                key = _paper_key(paper.doi, paper.arxiv_id, paper.title)
                record = records_by_key.get(key)
                if record is None:
                    record = CorpusPaperRecord(
                        paper_id=f"corpus-paper-{len(records_by_key) + 1}",
                        canonical_title=paper.title,
                        canonical_doi=paper.doi.lower(),
                        canonical_arxiv_id=paper.arxiv_id,
                        first_seen_run_id=state.run_id,
                        provenance=_project_provenance(
                            "sync-project-memory",
                            [state.run_id, paper.id],
                            "Paper added to project corpus from an attached run.",
                        ),
                    )
                    records_by_key[key] = record
                record.seen_run_ids = _unique([*record.seen_run_ids, state.run_id])
                record.source_paper_ids = _unique([*record.source_paper_ids, paper.id])
                record.local_artifact_ids = _unique([*record.local_artifact_ids, *artifacts_by_paper.get(paper.id, [])])
                record.role_tags = _unique([*record.role_tags, *paper.roles])
                record.last_updated = utc_now_iso()
        return sorted(records_by_key.values(), key=lambda item: (item.canonical_title.lower(), item.paper_id))

    def _sync_memory_records(
        self,
        program: ResearchProgramState,
        loaded_runs: list[ResearchRunState],
    ) -> list[ProjectMemoryRecord]:
        records: dict[str, ProjectMemoryRecord] = {record.id: record for record in program.memory_records}
        for state in loaded_runs:
            for claim in state.claims:
                record = _record_from_claim(program.project.id, state.run_id, claim)
                records[record.id] = _merge_memory(records.get(record.id), record)
            for gap in state.gaps:
                record = _record_from_gap(program.project.id, state.run_id, gap)
                records[record.id] = _merge_memory(records.get(record.id), record)
            for idea in state.rejected_ideas:
                record = _record_from_rejected_idea(program.project.id, state.run_id, idea)
                records[record.id] = _merge_memory(records.get(record.id), record)
            for experiment in state.experiments:
                record = _record_from_experiment(program.project.id, state.run_id, experiment)
                records[record.id] = _merge_memory(records.get(record.id), record)
            for objection in state.reviewer_objections:
                record = _record_from_reviewer_objection(program.project.id, state.run_id, objection)
                records[record.id] = _merge_memory(records.get(record.id), record)
            for review in state.human_reviews:
                record = _record_from_human_review(program.project.id, state.run_id, review)
                records[record.id] = _merge_memory(records.get(record.id), record)
        return sorted(records.values(), key=lambda item: (item.record_type, item.id))

    def _sync_research_directions(
        self,
        program: ResearchProgramState,
        loaded_runs: list[ResearchRunState],
    ) -> list[ResearchDirection]:
        directions: dict[str, ResearchDirection] = {direction.id: direction for direction in program.research_directions}
        rejected_gap_ids = {
            review.object_id
            for state in loaded_runs
            for review in state.human_reviews
            if review.object_type == "gap" and review.action == "reject"
        }
        for state in loaded_runs:
            experiments_by_gap: dict[str, list[ExperimentPlan]] = {}
            for experiment in state.experiments:
                for gap_id in experiment.linked_gap_ids:
                    experiments_by_gap.setdefault(gap_id, []).append(experiment)
            dossiers_by_target = {dossier.target_id: dossier for dossier in state.novelty_dossiers}
            for gap in state.gaps:
                direction_id = f"direction-{_stable_id(program.project.id, gap.id)}"
                linked_experiments = experiments_by_gap.get(gap.id, [])
                dossier = dossiers_by_target.get(gap.id)
                maturity = _direction_maturity(gap, linked_experiments, bool(dossier), gap.id in rejected_gap_ids)
                direction = directions.get(direction_id)
                if direction is None:
                    direction = ResearchDirection(
                        id=direction_id,
                        project_id=program.project.id,
                        title=gap.title or gap.description[:80] or gap.id,
                        summary=gap.description,
                        linked_gap_ids=[gap.id],
                        provenance=_project_provenance(
                            "sync-project-memory",
                            [state.run_id, gap.id],
                            "Research direction initialized from a synced gap.",
                        ),
                    )
                direction.linked_gap_ids = _unique([*direction.linked_gap_ids, gap.id])
                direction.linked_experiment_ids = _unique([*direction.linked_experiment_ids, *[item.id for item in linked_experiments]])
                direction.linked_novelty_dossier_ids = _unique(
                    [*direction.linked_novelty_dossier_ids, *([dossier.target_id] if dossier else [])]
                )
                direction.supporting_paper_ids = _unique(
                    [*direction.supporting_paper_ids, *gap.supporting_paper_ids, *gap.linked_paper_ids]
                )
                direction.counterevidence_paper_ids = _unique(
                    [
                        *direction.counterevidence_paper_ids,
                        *[
                            claim.source_paper_ids[0]
                            for claim in state.claims
                            if claim.id in gap.counterevidence_claim_ids and claim.source_paper_ids
                        ],
                    ]
                )
                direction.maturity = maturity
                direction.readiness_score = _readiness_score(gap, linked_experiments, bool(dossier), maturity)
                direction.blocking_issues = _direction_blockers(gap, linked_experiments, dossier is not None)
                direction.next_actions = _direction_next_actions(direction.blocking_issues, maturity)
                directions[direction_id] = direction
        return sorted(directions.values(), key=lambda item: (item.maturity, -item.readiness_score, item.title))

    def _topic_from_run(self, project_id: str, state: ResearchRunState) -> ProjectTopic:
        topic_id = f"topic-{state.topic.slug}"
        return ProjectTopic(
            id=topic_id,
            project_id=project_id,
            text=state.topic.text,
            slug=state.topic.slug,
            created_at=state.topic.created_at,
            provenance=_project_provenance("attach-run", [state.run_id], "Topic linked from an attached run."),
        )

    def _write_run_pointer(self, program: ResearchProgramState, state: ResearchRunState) -> None:
        root_dir = Path(program.project.root_dir)
        pointer = {
            "run_id": state.run_id,
            "run_dir": state.run_dir,
            "attached_at": utc_now_iso(),
        }
        self._write_json(root_dir / "runs" / f"{state.run_id}.json", pointer)

    def _project_dir(self, project_id: str) -> Path:
        return self.config.project_root / project_id

    def _active_project_path(self) -> Path:
        return self.config.data_dir / "active_project.json"

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def _load_list(path: Path, model: type[Any]) -> list[Any]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(model, item) for item in raw]


def _record_from_claim(project_id: str, run_id: str, claim: Claim) -> ProjectMemoryRecord:
    status = "active"
    if claim.status in {"falsified", "contested"}:
        status = "rejected" if claim.status == "falsified" else "active"
    return ProjectMemoryRecord(
        id=f"memory-claim-{_stable_id(run_id, claim.id)}",
        project_id=project_id,
        record_type="claim",
        text=claim.text,
        linked_run_ids=[run_id],
        linked_object_ids=[claim.id],
        linked_paper_ids=claim.source_paper_ids,
        status=status,
        confidence=claim.confidence,
        created_at=claim.provenance.timestamp,
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, claim.id], "Claim synced from attached run."),
    )


def _record_from_gap(project_id: str, run_id: str, gap: Gap) -> ProjectMemoryRecord:
    return ProjectMemoryRecord(
        id=f"memory-gap-{_stable_id(run_id, gap.id)}",
        project_id=project_id,
        record_type="gap",
        text=gap.title or gap.description,
        linked_run_ids=[run_id],
        linked_object_ids=[gap.id],
        linked_paper_ids=_unique([*gap.supporting_paper_ids, *gap.linked_paper_ids]),
        status="active" if gap.novelty_status != "likely_not_new" else "rejected",
        confidence=gap.confidence,
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, gap.id], "Gap synced from attached run."),
    )


def _record_from_rejected_idea(project_id: str, run_id: str, idea: RejectedIdea) -> ProjectMemoryRecord:
    return ProjectMemoryRecord(
        id=f"memory-rejected-idea-{_stable_id(run_id, idea.id)}",
        project_id=project_id,
        record_type="rejected_idea",
        text=f"{idea.idea} | Reason: {idea.reason}",
        linked_run_ids=[run_id],
        linked_object_ids=[idea.id],
        status="rejected",
        confidence="medium",
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, idea.id], "Rejected idea synced from attached run."),
    )


def _record_from_experiment(project_id: str, run_id: str, experiment: ExperimentPlan) -> ProjectMemoryRecord:
    return ProjectMemoryRecord(
        id=f"memory-experiment-{_stable_id(run_id, experiment.id)}",
        project_id=project_id,
        record_type="experiment",
        text=experiment.title,
        linked_run_ids=[run_id],
        linked_object_ids=[experiment.id, *experiment.linked_gap_ids],
        linked_paper_ids=[],
        status="active",
        confidence=experiment.confidence,
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, experiment.id], "Experiment synced from attached run."),
    )


def _record_from_reviewer_objection(project_id: str, run_id: str, objection: ReviewerObjection) -> ProjectMemoryRecord:
    target_ids = [item for item in [objection.id, objection.experiment_id, objection.target_id] if item]
    return ProjectMemoryRecord(
        id=f"memory-reviewer-objection-{_stable_id(run_id, objection.id)}",
        project_id=project_id,
        record_type="reviewer_objection",
        text=f"{objection.severity}/{objection.category}: {objection.objection}",
        linked_run_ids=[run_id],
        linked_object_ids=target_ids,
        status="active",
        confidence=objection.confidence,
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, objection.id], "Reviewer objection synced from attached run."),
    )


def _record_from_human_review(project_id: str, run_id: str, review: HumanReviewRecord) -> ProjectMemoryRecord:
    status = "rejected" if review.action == "reject" else "active"
    text = f"{review.action} {review.object_type}:{review.object_id}"
    if review.note:
        text = f"{text} | {review.note}"
    return ProjectMemoryRecord(
        id=f"memory-decision-{_stable_id(run_id, review.id)}",
        project_id=project_id,
        record_type="decision",
        text=text,
        linked_run_ids=[run_id],
        linked_object_ids=[review.object_id],
        status=status,
        confidence="high",
        created_at=review.timestamp,
        updated_at=utc_now_iso(),
        provenance=_project_provenance("sync-project-memory", [run_id, review.id], "Human review decision synced from attached run."),
    )


def _merge_memory(existing: ProjectMemoryRecord | None, new: ProjectMemoryRecord) -> ProjectMemoryRecord:
    if existing is None:
        return new
    existing.linked_run_ids = _unique([*existing.linked_run_ids, *new.linked_run_ids])
    existing.linked_object_ids = _unique([*existing.linked_object_ids, *new.linked_object_ids])
    existing.linked_paper_ids = _unique([*existing.linked_paper_ids, *new.linked_paper_ids])
    existing.updated_at = utc_now_iso()
    if existing.status != "rejected":
        existing.status = new.status
    return existing


def _paper_key(doi: str, arxiv_id: str, title: str) -> str:
    if doi.strip():
        return f"doi:{doi.strip().lower()}"
    if arxiv_id.strip():
        return f"arxiv:{arxiv_id.strip().lower()}"
    return f"title:{_normalize_title(title)}"


def _corpus_key_from_record(record: CorpusPaperRecord) -> str:
    return _paper_key(record.canonical_doi, record.canonical_arxiv_id, record.canonical_title)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def _project_provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill=skill,
        source_ids=source_ids,
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )


def _direction_maturity(gap: Gap, experiments: list[ExperimentPlan], has_dossier: bool, rejected: bool) -> str:
    if rejected or gap.novelty_status == "likely_not_new":
        return "rejected"
    if any(experiment.paper_ready for experiment in experiments):
        return "manuscript_ready"
    if experiments:
        return "experiment_ready"
    if has_dossier and gap.confidence in {"medium", "high"}:
        return "validated_gap"
    if gap.confidence in {"medium", "high"}:
        return "candidate"
    return "seed"


def _readiness_score(gap: Gap, experiments: list[ExperimentPlan], has_dossier: bool, maturity: str) -> float:
    if maturity == "rejected":
        return 0.0
    score = {"low": 0.2, "medium": 0.45, "high": 0.65}.get(gap.confidence, 0.1)
    if has_dossier:
        score += 0.15
    if experiments:
        score += 0.15
    if any(experiment.paper_ready for experiment in experiments):
        score += 0.05
    return min(score, 1.0)


def _direction_blockers(gap: Gap, experiments: list[ExperimentPlan], has_dossier: bool) -> list[str]:
    blockers: list[str] = []
    if gap.confidence == "low":
        blockers.append("Gap confidence is low.")
    if gap.novelty_status in {"unchecked", "weak", "likely_not_new"}:
        blockers.append(f"Novelty status is {gap.novelty_status}.")
    if not has_dossier:
        blockers.append("No novelty dossier linked.")
    if not experiments:
        blockers.append("No experiment plan linked.")
    return blockers


def _direction_next_actions(blockers: list[str], maturity: str) -> list[str]:
    if maturity == "rejected":
        return ["Keep rejected direction in memory to prevent accidental rediscovery."]
    if not blockers:
        return ["Prepare manuscript skeleton with evidence-linked claims."]
    actions: list[str] = []
    for blocker in blockers:
        if "confidence" in blocker:
            actions.append("Collect more evidence or counterevidence for the gap.")
        elif "Novelty" in blocker or "dossier" in blocker:
            actions.append("Run closest-prior-work search and update novelty dossier.")
        elif "experiment" in blocker:
            actions.append("Design a falsifiable minimum viable experiment.")
    return _unique(actions)
