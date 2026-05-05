"""Persistence helpers for project-level claim graphs."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.claims.graph import ClaimGraphBuilder, render_claim_graph_markdown
from gapforge.config import GapForgeConfig
from gapforge.models import ClaimEdge, ClaimGraph, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso


class ProjectClaimGraphManager:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def build(self, project_id: str) -> ClaimGraph:
        project_manager = ProjectMemoryManager(self.config)
        program = project_manager.load_project(project_id)
        runs = [ResearchStateManager(self.config).load_run(run_id) for run_id in program.run_ids]
        existing = self.load(project_id, required=False)
        graph = ClaimGraphBuilder().build(project_id=project_id, runs=runs, existing=existing)
        program.claim_graph = graph
        project_manager.save_project(program)
        self.save(project_id, graph)
        return graph

    def load(self, project_id: str, *, required: bool = True) -> ClaimGraph | None:
        path = self._json_path(project_id)
        if not path.exists():
            if required:
                raise FileNotFoundError(f"No claim graph found for project {project_id}")
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not raw:
            if required:
                raise FileNotFoundError(f"No claim graph found for project {project_id}")
            return None
        return from_dict(ClaimGraph, raw)

    def save(self, project_id: str, graph: ClaimGraph) -> None:
        root = self._project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        self._json_path(project_id).write_text(json.dumps(to_plain(graph), indent=2) + "\n", encoding="utf-8")
        self._markdown_path(project_id).write_text(render_claim_graph_markdown(graph), encoding="utf-8")

    def render(self, project_id: str) -> str:
        graph = self.load(project_id)
        assert graph is not None
        return render_claim_graph_markdown(graph)

    def resolve_contradiction(self, project_id: str, claim_a: str, claim_b: str, note: str) -> ClaimGraph:
        graph = self.load(project_id)
        assert graph is not None
        graph.edges.append(
            ClaimEdge(
                source_claim_id=claim_a,
                target_claim_id=claim_b,
                relation="refines",
                confidence="high",
                evidence=[f"Human resolution: {note}"],
                provenance=Provenance(
                    created_by_skill="human-claim-review",
                    source_ids=[claim_a, claim_b],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Human reviewer resolved or contextualized a project claim contradiction.",
                ),
            )
        )
        pair = set([claim_a, claim_b])
        graph.unresolved_contradictions = [
            item for item in graph.unresolved_contradictions if not all(claim_id in item for claim_id in pair)
        ]
        self.save(project_id, graph)
        return graph

    def _project_dir(self, project_id: str) -> Path:
        return self.config.project_root / project_id

    def _json_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "claim_graph.json"

    def _markdown_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "claim_graph.md"
