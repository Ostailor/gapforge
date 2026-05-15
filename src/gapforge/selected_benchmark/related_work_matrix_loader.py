"""Recovery and robust loading for selected benchmark related-work matrices."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import Paper, Provenance, RelatedWorkEntry, RelatedWorkMatrix, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.renderer import render_related_work_matrix_markdown
from gapforge.selected_benchmark.related_work import (
    REQUIRED_RELATED_WORK_CATEGORIES,
    SelectedRelatedWorkMatrix,
)
from gapforge.selected_benchmark.related_work_completion import _is_fallback_paper, _is_real_paper
from gapforge.selected_benchmark.related_work_matrix_v2 import (
    SelectedBenchmarkRelatedWorkMatrixV2,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


@dataclass(slots=True)
class RelatedWorkMatrixLoadResult:
    id: str
    benchmark_id: str
    manuscript_id: str
    candidate_paths: list[str] = field(default_factory=list)
    selected_path: str = ""
    status: str = "missing"
    matrix_id: str = ""
    entry_count: int = 0
    must_cite_count: int = 0
    closest_prior_work_count: int = 0
    missing_categories: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-matrix-loader"))


@dataclass(slots=True)
class RelatedWorkMatrixRepairRecord:
    id: str
    benchmark_id: str
    manuscript_id: str
    source_matrix_ids: list[str] = field(default_factory=list)
    repaired_matrix_id: str = ""
    repair_actions: list[str] = field(default_factory=list)
    status: str = "blocked"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-matrix-loader"))


@dataclass(slots=True)
class _ParsedMatrix:
    matrix_id: str
    source_kind: str
    path: Path
    entries: list[RelatedWorkEntry] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    must_cite_ids: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    baseline_paper_ids: list[str] = field(default_factory=list)
    category_coverage: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class RelatedWorkMatrixLoader:
    """Find, validate, repair, and expose selected-benchmark related-work matrices."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.runs = ResearchStateManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)
        self.manuscripts = ManuscriptManager(config)

    def load(self, benchmark_id: str, *, write_report: bool = True) -> RelatedWorkMatrixLoadResult:
        context = self._context(benchmark_id)
        parsed, invalid = self._first_valid_matrix(context)
        if parsed is None:
            result = self._missing_or_invalid_result(context, invalid)
        else:
            repaired_path = self._repaired_matrix_path(context)
            status = "repaired" if parsed.path == repaired_path else "loaded"
            result = RelatedWorkMatrixLoadResult(
                id=f"related-work-matrix-load-{slugify(benchmark_id)}",
                benchmark_id=benchmark_id,
                manuscript_id=context["manuscript_id"],
                candidate_paths=[str(path) for path in context["candidate_paths"]],
                selected_path=str(parsed.path),
                status=status,
                matrix_id=parsed.matrix_id,
                entry_count=len(parsed.entries),
                must_cite_count=len(parsed.must_cite_ids),
                closest_prior_work_count=len(parsed.closest_prior_work_ids),
                missing_categories=list(parsed.missing_categories),
                warnings=parsed.warnings,
                blockers=parsed.blockers,
                provenance=Provenance(
                    created_by_skill="selected-related-work-matrix-loader",
                    source_ids=[benchmark_id, context["manuscript_id"], parsed.matrix_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Loaded an auditable selected-benchmark related-work matrix from known artifact locations.",
                ),
            )
        if write_report:
            self._write_load_result(result)
        return result

    def repair(self, benchmark_id: str) -> RelatedWorkMatrixRepairRecord:
        context = self._context(benchmark_id)
        parsed, invalid = self._first_valid_matrix(context, allow_repaired=False)
        if parsed is None:
            result = self._missing_or_invalid_result(context, invalid)
            self._write_load_result(result)
            record = RelatedWorkMatrixRepairRecord(
                id=f"related-work-matrix-repair-{slugify(benchmark_id)}",
                benchmark_id=benchmark_id,
                manuscript_id=context["manuscript_id"],
                source_matrix_ids=[],
                repaired_matrix_id="",
                repair_actions=[*result.blockers, *_next_commands(benchmark_id, result.missing_categories)],
                status="blocked",
                provenance=Provenance(
                    created_by_skill="selected-related-work-matrix-loader",
                    source_ids=[benchmark_id, context["manuscript_id"]],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Could not repair selected related-work matrix because no valid source matrix was loadable.",
                ),
            )
            self._write_repair_record(record)
            return record

        repaired = self._to_related_work_matrix(parsed, context)
        repaired_path = self._repaired_matrix_path(context)
        repaired_path.parent.mkdir(parents=True, exist_ok=True)
        repaired_path.write_text(json.dumps(to_plain(repaired), indent=2) + "\n", encoding="utf-8")
        repaired_path.with_suffix(".md").write_text(render_related_work_matrix_markdown(repaired), encoding="utf-8")
        self._attach_repaired_matrix_to_project(repaired, context["project_id"])
        repaired_id = _repaired_matrix_id(benchmark_id)
        record = RelatedWorkMatrixRepairRecord(
            id=f"related-work-matrix-repair-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            manuscript_id=context["manuscript_id"],
            source_matrix_ids=[parsed.matrix_id],
            repaired_matrix_id=repaired_id,
            repair_actions=[
                f"Loaded `{parsed.matrix_id}` from `{parsed.path}`.",
                f"Projected source matrix into manuscript direction `{repaired.direction_id}`.",
                f"Wrote repaired matrix artifact `{repaired_path}`.",
                "Attached repaired matrix to project related-work matrix state for reviewer consumption.",
            ],
            status="repaired",
            provenance=Provenance(
                created_by_skill="selected-related-work-matrix-loader",
                source_ids=[benchmark_id, context["manuscript_id"], parsed.matrix_id, repaired_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Repaired selected related-work matrix load path without promoting fallback-only or fake records.",
            ),
        )
        self._write_repair_record(record)
        self._write_load_result(self.load(benchmark_id, write_report=False))
        return record

    def status_report(self, benchmark_id: str) -> str:
        result = self.load(benchmark_id)
        report = render_related_work_matrix_load_result(result)
        self._load_result_path(benchmark_id).with_suffix(".md").write_text(report, encoding="utf-8")
        return report

    def load_consumable_matrix(self, benchmark_id: str) -> RelatedWorkMatrix | None:
        context = self._context(benchmark_id)
        parsed, _invalid = self._first_valid_matrix(context)
        if parsed is None:
            return None
        return self._to_related_work_matrix(parsed, context)

    def _context(self, benchmark_id: str) -> dict[str, Any]:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        benchmark_dir = Path(program.project.root_dir) / "selected_benchmark"
        manuscript_id = self._manuscript_id_for_project(spec.project_id, benchmark_id)
        manuscript_root = self._manuscript_root(manuscript_id)
        candidate_paths = _dedupe_paths(
            [
                benchmark_dir / "related_work_matrix_loader" / "repaired_related_work_matrix.json",
                benchmark_dir / "related_work_matrix_v2" / "related_work_matrix_v2.json",
                benchmark_dir / "related_work" / "selected_related_work_matrix.json",
                Path(program.project.root_dir) / "related_work_matrices.json",
                Path(program.project.root_dir) / "related_work_matrix.json",
                *(Path(program.project.root_dir) / "reports").glob("*related*matrix*.json"),
                *(benchmark_dir / "reports").glob("*related*matrix*.json"),
                *(benchmark_dir / "dashboard").glob("**/*related*matrix*.json"),
                *((manuscript_root / "bibliography").glob("*.json") if manuscript_root else []),
                *[
                    Path(run.run_dir) / "related_work_matrix.json"
                    for run in [self.runs.load_run(run_id) for run_id in program.run_ids if self._run_exists(run_id)]
                ],
            ]
        )
        return {
            "benchmark_id": benchmark_id,
            "project_id": spec.project_id,
            "project_root": Path(program.project.root_dir),
            "benchmark_dir": benchmark_dir,
            "manuscript_id": manuscript_id,
            "manuscript_root": manuscript_root,
            "direction_id": self._direction_id_for_manuscript(manuscript_id, benchmark_id),
            "candidate_paths": candidate_paths,
            "paper_by_id": self._paper_by_id(spec.project_id),
        }

    def _run_exists(self, run_id: str) -> bool:
        try:
            self.runs.load_run(run_id)
        except FileNotFoundError:
            return False
        return True

    def _first_valid_matrix(
        self,
        context: dict[str, Any],
        *,
        allow_repaired: bool = True,
    ) -> tuple[_ParsedMatrix | None, list[_ParsedMatrix]]:
        invalid: list[_ParsedMatrix] = []
        repaired_path = self._repaired_matrix_path(context)
        for path in context["candidate_paths"]:
            if not allow_repaired and path == repaired_path:
                continue
            if not path.exists() or not path.is_file():
                continue
            parsed = self._parse_candidate(path, context)
            if parsed is None:
                continue
            self._validate(parsed, context["paper_by_id"])
            if parsed.blockers:
                invalid.append(parsed)
                continue
            return parsed, invalid
        return None, invalid

    def _parse_candidate(self, path: Path, context: dict[str, Any]) -> _ParsedMatrix | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _invalid_candidate(path, f"Invalid JSON: {exc}")
        if path.name == "related_work_matrix_v2.json":
            return self._parse_matrix_v2(path, raw)
        if path.name == "selected_related_work_matrix.json":
            return self._parse_selected_matrix(path, raw)
        if path.name == "repaired_related_work_matrix.json":
            return self._parse_generic_matrix(path, raw, context["direction_id"])
        if path.name == "related_work_matrices.json":
            if not isinstance(raw, list):
                return _invalid_candidate(path, "Project related_work_matrices.json is not a list.")
            for item in raw:
                if not isinstance(item, dict):
                    continue
                if item.get("direction_id") == context["direction_id"]:
                    return self._parse_generic_matrix(path, item, context["direction_id"])
            return _invalid_candidate(path, f"No matrix matches manuscript direction `{context['direction_id']}`.")
        if path.name == "related_work_matrix.json":
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and item.get("direction_id") == context["direction_id"]:
                        return self._parse_generic_matrix(path, item, context["direction_id"])
                return _invalid_candidate(path, f"No run matrix matches manuscript direction `{context['direction_id']}`.")
            if isinstance(raw, dict):
                return self._parse_generic_matrix(path, raw, context["direction_id"])
        if path.parent.name == "bibliography":
            return _invalid_candidate(
                path,
                "Bibliography records contain citations but no related-work matrix categories or reviewer-risk fields.",
            )
        if isinstance(raw, dict) and "related_work_matrix_v2" in raw and isinstance(raw["related_work_matrix_v2"], dict):
            return self._parse_matrix_v2(path, raw["related_work_matrix_v2"])
        if isinstance(raw, dict) and "selected_related_work_matrix" in raw and isinstance(raw["selected_related_work_matrix"], dict):
            return self._parse_selected_matrix(path, raw["selected_related_work_matrix"])
        if isinstance(raw, dict) and "direction_id" in raw and "entries" in raw:
            return self._parse_generic_matrix(path, raw, context["direction_id"])
        return _invalid_candidate(path, "JSON file is not a recognized related-work matrix artifact.")

    def _parse_matrix_v2(self, path: Path, raw: Any) -> _ParsedMatrix:
        try:
            matrix = from_dict(SelectedBenchmarkRelatedWorkMatrixV2, raw)
        except (TypeError, ValueError) as exc:
            return _invalid_candidate(path, f"Matrix-v2 schema error: {exc}")
        entries = [
            RelatedWorkEntry(
                direction_id=entry.benchmark_id,
                paper_id=entry.paper_id,
                relationship=entry.relationship,
                relevance_score=entry.relevance_score,
                evidence_span_ids=list(entry.evidence_span_ids),
                what_it_contributes=f"{entry.category}: {entry.title}",
                what_it_does_not_solve=entry.notes,
                must_cite=entry.must_cite,
                baseline_candidate=entry.baseline_source,
                reviewer_risk_if_omitted=entry.reviewer_omission_risk,
                provenance=entry.provenance,
            )
            for entry in matrix.entries
        ]
        closest = list(matrix.closest_prior_work_ids)
        if not closest:
            closest = [entry.paper_id for entry in matrix.entries if entry.relationship in {"directly solves", "adjacent benchmark"}]
        return _ParsedMatrix(
            matrix_id=matrix.id,
            source_kind="selected_matrix_v2",
            path=path,
            entries=entries,
            missing_categories=list(matrix.missing_categories),
            must_cite_ids=list(matrix.must_cite_ids),
            closest_prior_work_ids=_dedupe(closest),
            baseline_paper_ids=list(matrix.baseline_source_ids),
            category_coverage=matrix.category_coverage,
        )

    def _parse_selected_matrix(self, path: Path, raw: Any) -> _ParsedMatrix:
        try:
            matrix = from_dict(SelectedRelatedWorkMatrix, raw)
        except (TypeError, ValueError) as exc:
            return _invalid_candidate(path, f"Selected related-work matrix schema error: {exc}")
        entries = [
            RelatedWorkEntry(
                direction_id=matrix.benchmark_id,
                paper_id=entry.paper_id,
                relationship=entry.relationship,
                relevance_score=entry.relevance_score,
                what_it_contributes=f"{entry.category}: {entry.title}",
                what_it_does_not_solve=entry.positioning_note,
                must_cite=entry.closest_prior_work,
                baseline_candidate="baseline" in entry.relationship.lower() or "baseline" in entry.category.lower(),
                reviewer_risk_if_omitted=entry.reviewer_risk_if_omitted,
                provenance=entry.provenance,
            )
            for entry in matrix.entries
        ]
        closest = list(matrix.closest_prior_work_ids) or [entry.paper_id for entry in matrix.entries if entry.closest_prior_work]
        must = closest or [entry.paper_id for entry in matrix.entries[:3]]
        return _ParsedMatrix(
            matrix_id=matrix.id,
            source_kind="selected_matrix_v1",
            path=path,
            entries=entries,
            missing_categories=list(matrix.missing_categories),
            must_cite_ids=_dedupe(must),
            closest_prior_work_ids=_dedupe(closest),
            baseline_paper_ids=[entry.paper_id for entry in entries if entry.baseline_candidate],
        )

    def _parse_generic_matrix(self, path: Path, raw: Any, direction_id: str) -> _ParsedMatrix:
        try:
            matrix = from_dict(RelatedWorkMatrix, raw)
        except (TypeError, ValueError) as exc:
            return _invalid_candidate(path, f"RelatedWorkMatrix schema error: {exc}")
        if matrix.direction_id and matrix.direction_id != direction_id and path.name == "repaired_related_work_matrix.json":
            return _invalid_candidate(path, f"Repaired matrix direction `{matrix.direction_id}` does not match `{direction_id}`.")
        closest = list(matrix.must_read_paper_ids)
        return _ParsedMatrix(
            matrix_id=f"related-work-matrix-{matrix.direction_id}",
            source_kind="generic_related_work_matrix",
            path=path,
            entries=list(matrix.entries),
            missing_categories=list(matrix.missing_categories),
            must_cite_ids=list(matrix.must_read_paper_ids),
            closest_prior_work_ids=closest,
            baseline_paper_ids=list(matrix.baseline_paper_ids),
        )

    def _validate(self, parsed: _ParsedMatrix, paper_by_id: dict[str, Paper]) -> None:
        paper_ids = _dedupe(
            [
                *[entry.paper_id for entry in parsed.entries],
                *parsed.must_cite_ids,
                *parsed.closest_prior_work_ids,
                *parsed.baseline_paper_ids,
            ]
        )
        unknown = [paper_id for paper_id in paper_ids if paper_id not in paper_by_id]
        if unknown:
            parsed.blockers.append(
                "Unknown related-work paper IDs are not loadable real records: "
                + ", ".join(unknown)
                + ". Attach real records before rerunning matrix load."
            )
        fallback = [paper_id for paper_id in paper_ids if paper_id in paper_by_id and _is_fallback_paper(paper_by_id[paper_id])]
        if fallback:
            parsed.blockers.append(
                "Fallback-only related-work records cannot satisfy matrix loading: "
                + ", ".join(fallback)
                + ". Run real related-work search and attach traceable papers."
            )
        non_real = [
            paper_id
            for paper_id in paper_ids
            if paper_id in paper_by_id and not _is_real_paper(paper_by_id[paper_id]) and paper_id not in fallback
        ]
        if non_real:
            parsed.blockers.append(
                "Related-work paper IDs lack real traceable source metadata: "
                + ", ".join(non_real)
                + ". Add DOI, arXiv, OpenReview, Semantic Scholar, URL, or other source metadata."
            )
        if not parsed.entries:
            parsed.blockers.append("Related-work matrix has no entries.")
        if not parsed.must_cite_ids:
            parsed.blockers.append("Related-work matrix has no must-cite or must-read papers.")
        if not parsed.closest_prior_work_ids:
            parsed.blockers.append("Related-work matrix has no closest-prior-work papers.")
        missing_in_coverage = [
            category
            for category, coverage in parsed.category_coverage.items()
            if coverage.get("status") == "missing" and category not in parsed.missing_categories
        ]
        if missing_in_coverage:
            parsed.blockers.append(
                "Missing related-work categories are not explicit in matrix.missing_categories: " + ", ".join(missing_in_coverage)
            )
        if parsed.missing_categories:
            parsed.warnings.append(
                "Missing related-work categories remain explicit blockers for publication readiness: "
                + ", ".join(parsed.missing_categories)
            )
        direct = [entry.paper_id for entry in parsed.entries if entry.relationship == "directly solves"]
        if direct:
            parsed.warnings.append("Directly-solving prior work remains visible and may require no-go/revise: " + ", ".join(direct))
        parsed.warnings = _dedupe(parsed.warnings)
        parsed.blockers = _dedupe(parsed.blockers)

    def _missing_or_invalid_result(
        self,
        context: dict[str, Any],
        invalid: list[_ParsedMatrix],
    ) -> RelatedWorkMatrixLoadResult:
        candidate_paths = [str(path) for path in context["candidate_paths"]]
        if not invalid:
            blockers = [
                "No loadable related-work matrix artifact was found in selected benchmark, project, run, manuscript, "
                "v2.4, or dashboard/report locations.",
                *_next_commands(context["benchmark_id"], REQUIRED_RELATED_WORK_CATEGORIES),
            ]
            return RelatedWorkMatrixLoadResult(
                id=f"related-work-matrix-load-{slugify(context['benchmark_id'])}",
                benchmark_id=context["benchmark_id"],
                manuscript_id=context["manuscript_id"],
                candidate_paths=candidate_paths,
                status="missing",
                missing_categories=list(REQUIRED_RELATED_WORK_CATEGORIES),
                blockers=blockers,
                provenance=Provenance(
                    created_by_skill="selected-related-work-matrix-loader",
                    source_ids=[context["benchmark_id"], context["manuscript_id"]],
                    timestamp=utc_now_iso(),
                    reasoning_summary="No selected benchmark related-work matrix was found in known artifact locations.",
                ),
            )
        first = invalid[0]
        warnings = _dedupe([warning for item in invalid for warning in item.warnings])
        blockers = _dedupe([blocker for item in invalid for blocker in item.blockers])
        if not blockers:
            blockers = ["Related-work matrix candidates were found but none validated."]
        blockers.extend(_next_commands(context["benchmark_id"], first.missing_categories or REQUIRED_RELATED_WORK_CATEGORIES))
        return RelatedWorkMatrixLoadResult(
            id=f"related-work-matrix-load-{slugify(context['benchmark_id'])}",
            benchmark_id=context["benchmark_id"],
            manuscript_id=context["manuscript_id"],
            candidate_paths=candidate_paths,
            selected_path=str(first.path),
            status="invalid",
            matrix_id=first.matrix_id,
            entry_count=len(first.entries),
            must_cite_count=len(first.must_cite_ids),
            closest_prior_work_count=len(first.closest_prior_work_ids),
            missing_categories=list(first.missing_categories),
            warnings=warnings,
            blockers=_dedupe(blockers),
            provenance=Provenance(
                created_by_skill="selected-related-work-matrix-loader",
                source_ids=[context["benchmark_id"], context["manuscript_id"], first.matrix_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Found related-work matrix candidates, but validation blocked loading.",
            ),
        )

    def _to_related_work_matrix(self, parsed: _ParsedMatrix, context: dict[str, Any]) -> RelatedWorkMatrix:
        direction_id = context["direction_id"]
        entries = [
            RelatedWorkEntry(
                direction_id=direction_id,
                paper_id=entry.paper_id,
                relationship=entry.relationship,
                relevance_score=entry.relevance_score,
                evidence_span_ids=list(entry.evidence_span_ids),
                what_it_contributes=entry.what_it_contributes,
                what_it_does_not_solve=entry.what_it_does_not_solve,
                must_cite=entry.paper_id in parsed.must_cite_ids or entry.must_cite,
                baseline_candidate=entry.paper_id in parsed.baseline_paper_ids or entry.baseline_candidate,
                reviewer_risk_if_omitted=entry.reviewer_risk_if_omitted,
                provenance=entry.provenance,
            )
            for entry in parsed.entries
        ]
        return RelatedWorkMatrix(
            direction_id=direction_id,
            entries=entries,
            coverage_summary=(
                f"Recovered selected benchmark related-work matrix `{parsed.matrix_id}` from `{parsed.source_kind}`. "
                "Fallback-only or unknown paper records are not promoted."
            ),
            missing_categories=list(parsed.missing_categories),
            must_read_paper_ids=list(parsed.must_cite_ids),
            baseline_paper_ids=list(parsed.baseline_paper_ids),
            provenance=Provenance(
                created_by_skill="selected-related-work-matrix-loader",
                source_ids=[context["benchmark_id"], context["manuscript_id"], parsed.matrix_id, *parsed.must_cite_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Projected selected benchmark matrix into manuscript-consumable RelatedWorkMatrix format.",
            ),
        )

    def _attach_repaired_matrix_to_project(self, matrix: RelatedWorkMatrix, project_id: str) -> None:
        program = self.projects.load_project(project_id)
        program.related_work_matrices = [
            *[item for item in program.related_work_matrices if item.direction_id != matrix.direction_id],
            matrix,
        ]
        self.projects.save_project(program)

    def _manuscript_id_for_project(self, project_id: str, benchmark_id: str) -> str:
        spec = self.benchmarks.load_spec(benchmark_id)
        target_direction_ids = {benchmark_id, f"selected-benchmark-{slugify(benchmark_id)}"}
        try:
            program = self.projects.load_project(project_id)
        except FileNotFoundError:
            return f"manuscript-{slugify(spec.title)}"
        manuscripts_dir = Path(program.project.root_dir) / "manuscripts"
        if manuscripts_dir.exists():
            matches: list[str] = []
            for state_path in sorted(manuscripts_dir.glob("*/manuscript.json")):
                try:
                    raw = json.loads(state_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                manuscript = raw.get("manuscript", {}) if isinstance(raw, dict) else {}
                direction_id = str(manuscript.get("direction_id", ""))
                title = str(manuscript.get("title", "")).lower()
                if direction_id in target_direction_ids or slugify(spec.title) in slugify(title):
                    matches.append(str(manuscript.get("id") or state_path.parent.name))
            if matches:
                return matches[0]
        return f"manuscript-{slugify(spec.title)}"

    def _direction_id_for_manuscript(self, manuscript_id: str, benchmark_id: str) -> str:
        if manuscript_id:
            try:
                return self.manuscripts.load_state(manuscript_id).manuscript.direction_id
            except FileNotFoundError:
                pass
        return f"selected-benchmark-{slugify(benchmark_id)}"

    def _manuscript_root(self, manuscript_id: str) -> Path | None:
        if not manuscript_id:
            return None
        try:
            return self.manuscripts.manuscript_root(manuscript_id)
        except FileNotFoundError:
            return None

    def _paper_by_id(self, project_id: str) -> dict[str, Paper]:
        program = self.projects.load_project(project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            try:
                state = self.runs.load_run(run_id)
            except FileNotFoundError:
                continue
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _repaired_matrix_path(self, context: dict[str, Any]) -> Path:
        return context["benchmark_dir"] / "related_work_matrix_loader" / "repaired_related_work_matrix.json"

    def _load_result_path(self, benchmark_id: str) -> Path:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "related_work_matrix_loader" / "related_work_matrix_load_result.json"

    def _repair_record_path(self, benchmark_id: str) -> Path:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        return (
            Path(program.project.root_dir) / "selected_benchmark" / "related_work_matrix_loader" / "related_work_matrix_repair_record.json"
        )

    def _write_load_result(self, result: RelatedWorkMatrixLoadResult) -> None:
        path = self._load_result_path(result.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_related_work_matrix_load_result(result), encoding="utf-8")

    def _write_repair_record(self, record: RelatedWorkMatrixRepairRecord) -> None:
        path = self._repair_record_path(record.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_related_work_matrix_repair_record(record), encoding="utf-8")


def render_related_work_matrix_load_result(result: RelatedWorkMatrixLoadResult) -> str:
    lines = [
        "# Related-Work Matrix Load Result",
        "",
        f"- Benchmark ID: `{result.benchmark_id}`",
        f"- Manuscript ID: `{result.manuscript_id}`",
        f"- Status: `{result.status}`",
        f"- Selected path: `{result.selected_path or 'none'}`",
        f"- Matrix ID: `{result.matrix_id or 'none'}`",
        f"- Entries: {result.entry_count}",
        f"- Must-cite papers: {result.must_cite_count}",
        f"- Closest prior-work papers: {result.closest_prior_work_count}",
        f"- Missing categories: {', '.join(result.missing_categories) or 'none'}",
        "",
        "## Candidate Paths",
        "",
    ]
    lines.extend([f"- `{path}`" for path in result.candidate_paths] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Loaded means the matrix is auditable and parseable; it does not prove exhaustive related work.",
            "- Fallback-only and unknown paper records are blockers, not evidence.",
            "- Missing categories remain publication-readiness blockers unless explicitly resolved or dropped.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_related_work_matrix_repair_record(record: RelatedWorkMatrixRepairRecord) -> str:
    lines = [
        "# Related-Work Matrix Repair Record",
        "",
        f"- Benchmark ID: `{record.benchmark_id}`",
        f"- Manuscript ID: `{record.manuscript_id}`",
        f"- Status: `{record.status}`",
        f"- Repaired matrix ID: `{record.repaired_matrix_id or 'none'}`",
        f"- Source matrix IDs: {', '.join(record.source_matrix_ids) or 'none'}",
        "",
        "## Repair Actions",
        "",
    ]
    lines.extend([f"- {action}" for action in record.repair_actions] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- Repair only rewires or projects existing audited matrix state.",
            "- Repair does not create new citations, paper records, or novelty evidence.",
            "- Fallback-only records remain blocked.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _invalid_candidate(path: Path, blocker: str) -> _ParsedMatrix:
    return _ParsedMatrix(matrix_id=f"invalid:{path.name}", source_kind="invalid", path=path, blockers=[blocker])


def _next_commands(benchmark_id: str, categories: list[str]) -> list[str]:
    commands = [
        f"Run `gapforge selected-related-work-search-plan --benchmark-id {benchmark_id}` if category search plans are missing.",
        f"Run `gapforge selected-related-work-search-run --benchmark-id {benchmark_id}` to collect real candidate papers.",
        "Attach real papers with `gapforge attach-related-paper --benchmark-id "
        f"{benchmark_id} --category <category> --paper-id <paper-id> --relationship closest_prior_work`.",
        f"Run `gapforge selected-related-work-matrix-v2 --benchmark-id {benchmark_id}` after curation.",
    ]
    if categories:
        commands.append("Unresolved categories: " + ", ".join(categories))
    return commands


def _repaired_matrix_id(benchmark_id: str) -> str:
    return f"repaired-related-work-matrix-{slugify(benchmark_id)}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result
