"""Programmatic API for notebooks, scripts, and UI adapters.

The functions in this module are intentionally thin wrappers over the same
managers and skills used by the CLI. They provide a stable import surface
without asking callers to shell out to ``gapforge`` commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.ingest import ManualIngestor
from gapforge.models import (
    IndexManifest,
    Paper,
    PaperArtifact,
    PaperPackage,
    PaperSection,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
)
from gapforge.orchestrator import Orchestrator
from gapforge.project_memory import ProjectMemoryManager
from gapforge.reporting import write_final_report
from gapforge.retrieval import build_project_index, build_run_index
from gapforge.state import ResearchStateManager


@dataclass(slots=True)
class AddPdfResult:
    state: ResearchRunState
    paper: Paper
    artifact: PaperArtifact


@dataclass(slots=True)
class ParseFullTextResult:
    state: ResearchRunState
    sections: list[PaperSection]


@dataclass(slots=True)
class ReportResult:
    state: ResearchRunState
    path: Path


def create_project(
    name: str,
    *,
    description: str = "",
    config: GapForgeConfig | None = None,
) -> ResearchProgramState:
    """Create a project-memory workspace."""

    return ProjectMemoryManager(_config(config)).create_project(name, description=description)


def create_run(
    topic: str,
    *,
    project_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Create a durable research run, optionally attaching it to a project."""

    cfg = _config(config)
    state = Orchestrator(cfg).init_topic(topic)
    if project_id:
        state.config["project_id"] = project_id
        ResearchStateManager(cfg).save_run(state)
        ProjectMemoryManager(cfg).attach_run(project_id, state.run_id)
        state = ResearchStateManager(cfg).load_run(state.run_id)
    return state


def search_papers(
    run_id: str,
    *,
    query: str | None = None,
    max_results: int = 20,
    sources: list[str] | None = None,
    newest_first: bool = True,
    date_from: str | None = None,
    date_to: str | None = None,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Search configured sources for an existing run and persist papers."""

    cfg = _config(config)
    orchestrator = Orchestrator(cfg)
    state = orchestrator.state_store.load_run(run_id)
    search_query = query or state.topic.text
    papers, failures = orchestrator._search_sources(
        state=state,
        query=search_query,
        max_results=max_results,
        source_names=sources,
        newest_first=newest_first,
        purpose="initial_topic" if not state.search_queries else "manual",
        date_from=date_from,
        date_to=date_to,
    )
    for failure in failures:
        orchestrator._log(state, "warning", "api-search", failure)
    state.papers = orchestrator._merge_ranked_papers(state, papers, search_query, max_results)
    orchestrator._refresh_coverage(state)
    orchestrator.state_store.save_run(state)
    return state


def add_pdf(
    run_id: str,
    pdf_path: str | Path,
    *,
    title: str = "",
    authors: list[str] | None = None,
    year: int = 0,
    parse: bool = False,
    config: GapForgeConfig | None = None,
) -> AddPdfResult:
    """Add a local PDF to a run without using the CLI."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    path = Path(pdf_path)
    paper, artifact = ManualIngestor(cfg).add_pdf(
        state,
        path,
        title=title or path.stem,
        authors=authors or [],
        year=year,
        parse=parse,
    )
    manager.save_run(state)
    return AddPdfResult(state=state, paper=paper, artifact=artifact)


def parse_fulltext(
    run_id: str,
    *,
    paper_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> ParseFullTextResult:
    """Parse available PDF artifacts into paper sections."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    sections = FullTextParser().parse_for_state(state, paper_id=paper_id)
    manager.save_run(state)
    return ParseFullTextResult(state=state, sections=sections)


def build_index(
    *,
    run_id: str | None = None,
    project_id: str | None = None,
    config: GapForgeConfig | None = None,
) -> IndexManifest:
    """Build a persisted hybrid retrieval index for exactly one run or project."""

    cfg = _config(config)
    _require_one_scope(run_id=run_id, project_id=project_id)
    if run_id:
        manager = ResearchStateManager(cfg)
        state = manager.load_run(run_id)
        manifest = build_run_index(state)
        manager.save_run(state)
        return manifest
    program = ProjectMemoryManager(cfg).load_project(project_id or "")
    return build_project_index(program)


def mine_gaps(
    run_id: str,
    *,
    mode: str = "deterministic",
    min_confidence: str = "low",
    include_low_confidence: bool = True,
    fake: bool = False,
    dry_run_prompts: bool = False,
    force: bool = False,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Run deterministic or optional LLM-backed gap mining for a run."""

    orchestrator = Orchestrator(_config(config))
    if mode == "deterministic":
        return orchestrator.mine_gaps(
            run_id=run_id,
            min_confidence=min_confidence,
            include_low_confidence=include_low_confidence,
            force=force,
        )
    if mode == "llm":
        return orchestrator.mine_gaps_llm(
            run_id=run_id,
            dry_run_prompts=dry_run_prompts,
            fake=fake,
            force=force,
        )
    raise ValueError("mode must be 'deterministic' or 'llm'")


def novelty_check(
    run_id: str,
    *,
    gap_id: str | None = None,
    deep: bool = False,
    config: GapForgeConfig | None = None,
) -> ResearchRunState:
    """Run the deterministic novelty gate for a run."""

    return Orchestrator(_config(config)).novelty_check(run_id=run_id, gap_id=gap_id, deep=deep)


def create_direction(
    project_id: str,
    gap_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ResearchDirection:
    """Create or fetch a project-level research direction for an attached-run gap."""

    return DirectionMaturationManager(_config(config)).create_direction(project_id, gap_id)


def mature_direction(
    project_id: str,
    direction_id: str,
    *,
    config: GapForgeConfig | None = None,
) -> ResearchDirection:
    """Evaluate maturity gates for a project-level research direction."""

    return DirectionMaturationManager(_config(config)).mature_direction(project_id, direction_id)


def export_paper_package(
    project_id: str,
    direction_id: str,
    *,
    allow_rejected: bool = False,
    config: GapForgeConfig | None = None,
) -> PaperPackage:
    """Export a conservative paper starter package for a project direction."""

    return PaperPackageExporter(_config(config)).export_project_direction(
        project_id,
        direction_id,
        allow_rejected=allow_rejected,
    )


def export_report(
    run_id: str,
    *,
    output_format: str = "markdown",
    strict: bool = False,
    config: GapForgeConfig | None = None,
) -> ReportResult:
    """Write ``final_report.md`` or ``final_report.json`` for a run."""

    cfg = _config(config)
    manager = ResearchStateManager(cfg)
    state = manager.load_run(run_id)
    path = write_final_report(state, output_format=output_format, strict=strict)
    return ReportResult(state=state, path=path)


def get_state(run_id: str, *, config: GapForgeConfig | None = None) -> ResearchRunState:
    """Load a persisted run state."""

    return ResearchStateManager(_config(config)).load_run(run_id)


def get_project(project_id: str, *, config: GapForgeConfig | None = None) -> ResearchProgramState:
    """Load a persisted project state."""

    return ProjectMemoryManager(_config(config)).load_project(project_id)


def _config(config: GapForgeConfig | None) -> GapForgeConfig:
    return config or GapForgeConfig.from_cwd()


def _require_one_scope(*, run_id: str | None, project_id: str | None) -> None:
    if bool(run_id) == bool(project_id):
        raise ValueError("Provide exactly one of run_id or project_id.")


__all__ = [
    "AddPdfResult",
    "ParseFullTextResult",
    "ReportResult",
    "add_pdf",
    "build_index",
    "create_direction",
    "create_project",
    "create_run",
    "export_paper_package",
    "export_report",
    "get_project",
    "get_state",
    "mature_direction",
    "mine_gaps",
    "novelty_check",
    "parse_fulltext",
    "search_papers",
]
