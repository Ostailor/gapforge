"""Integrate loadable v2.6 artifacts into selected benchmark manuscript state."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import ManuscriptSection
from gapforge.models import Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.artifact_package_loader import ArtifactPackageLoader
from gapforge.selected_benchmark.real_benchmark_experiment import (
    RealBenchmarkExperimentManager,
)
from gapforge.selected_benchmark.real_benchmark_search import RealBenchmarkSearchManager
from gapforge.selected_benchmark.related_work_matrix_loader import RelatedWorkMatrixLoader
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class VenueArtifactIntegrationReport:
    id: str
    manuscript_id: str
    related_work_matrix_status: str
    artifact_package_status: str
    real_benchmark_status: str
    integrated_sections: list[str] = field(default_factory=list)
    updated_citations: list[str] = field(default_factory=list)
    updated_artifact_links: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-venue-artifact-integration"))


class VenueArtifactIntegrationManager:
    """Attach loadable remediation artifacts to the venue-shaped manuscript."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)
        self.manuscripts = ManuscriptManager(config)
        self.related_work = RelatedWorkMatrixLoader(config)
        self.artifact_packages = ArtifactPackageLoader(config)
        self.real_search = RealBenchmarkSearchManager(config)
        self.real_experiments = RealBenchmarkExperimentManager(config)

    def integrate(self, benchmark_id: str) -> VenueArtifactIntegrationReport:
        spec = self.benchmarks.load_spec(benchmark_id)
        related = self.related_work.load(spec.id)
        artifact = self.artifact_packages.load(spec.id)
        real_status, real_links, real_warnings = self._real_benchmark_state(spec.id)
        manuscript_id = related.manuscript_id or artifact.manuscript_id
        blockers = _artifact_blockers(related.status, related.blockers, "related-work matrix")
        blockers.extend(_artifact_blockers(artifact.status, artifact.blockers, "artifact evaluation package"))
        if related.manuscript_id and artifact.manuscript_id and related.manuscript_id != artifact.manuscript_id:
            blockers.append(
                f"Related-work matrix manuscript `{related.manuscript_id}` does not match artifact package manuscript "
                f"`{artifact.manuscript_id}`."
            )
        try:
            state = self.manuscripts.load_state(manuscript_id)
        except FileNotFoundError:
            state = None
            blockers.append(f"Selected venue-shaped manuscript `{manuscript_id}` is not loadable.")

        integrated_sections: list[str] = []
        updated_citations: list[str] = []
        updated_artifact_links = _dedupe(
            [
                related.selected_path,
                related.matrix_id,
                artifact.selected_package_id,
                *real_links,
            ]
        )
        warnings = _dedupe(
            [
                *related.warnings,
                *artifact.warnings,
                *real_warnings,
                "Deployment-validity claims remain blocked; integration only links manuscript artifacts.",
            ]
        )
        if not blockers and state is not None:
            matrix = self.related_work.load_consumable_matrix(spec.id)
            package = self.artifact_packages.load_consumable_package(spec.id)
            if matrix is None:
                blockers.append("Related-work matrix reported loaded, but no consumable matrix could be opened.")
            if package is None:
                blockers.append("Artifact package reported loaded, but no consumable package could be opened.")
            if matrix is not None and package is not None:
                manuscript_root = self.manuscripts.manuscript_root(state.manuscript.id)
                updated_citations = list(matrix.must_read_paper_ids)
                related_section = self._write_related_work_section(
                    state.manuscript.id,
                    matrix_id=related.matrix_id,
                    matrix_path=related.selected_path,
                    citation_ids=updated_citations,
                    warnings=related.warnings,
                )
                artifact_section = self._write_artifact_appendix(
                    state.manuscript.id,
                    package_id=artifact.selected_package_id,
                    artifact_links=updated_artifact_links,
                    warnings=artifact.warnings,
                )
                limitations_section = self._write_limitations_update(
                    state.manuscript.id,
                    real_status=real_status,
                    related_status=related.status,
                    artifact_status=artifact.status,
                )
                self._write_submission_artifact_appendix(
                    manuscript_root,
                    related_status=related.status,
                    related_path=related.selected_path,
                    artifact_status=artifact.status,
                    artifact_package_id=artifact.selected_package_id,
                    real_status=real_status,
                    real_links=real_links,
                )
                integrated_sections = [related_section.id, artifact_section.id, limitations_section.id]

        report = VenueArtifactIntegrationReport(
            id=f"venue-artifact-integration-{slugify(spec.id)}",
            manuscript_id=manuscript_id,
            related_work_matrix_status=related.status,
            artifact_package_status=artifact.status,
            real_benchmark_status=real_status,
            integrated_sections=integrated_sections,
            updated_citations=updated_citations,
            updated_artifact_links=updated_artifact_links,
            warnings=warnings,
            blockers=_dedupe(blockers),
            provenance=Provenance(
                created_by_skill="selected-venue-artifact-integration",
                source_ids=_dedupe(
                    [
                        spec.id,
                        manuscript_id,
                        related.id,
                        related.matrix_id,
                        artifact.id,
                        artifact.selected_package_id,
                        *real_links,
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Integrated only loadable related-work and artifact-evaluation artifacts into manuscript state; "
                    "missing artifacts remain blockers."
                ),
            ),
        )
        self._write_report(spec.project_id, report)
        return report

    def report(self, benchmark_id: str) -> str:
        spec = self.benchmarks.load_spec(benchmark_id)
        path = self._report_path(spec.project_id)
        if not path.exists():
            report = self.integrate(spec.id)
        else:
            report = _report_from_path(path)
        markdown = render_venue_artifact_integration_report(report)
        path.with_suffix(".md").write_text(markdown, encoding="utf-8")
        return markdown

    def _real_benchmark_state(self, benchmark_id: str) -> tuple[str, list[str], list[str]]:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        root = Path(program.project.root_dir)
        search = self.real_search.load_or_search(benchmark_id)
        attempts = self.real_experiments.load_attempts(benchmark_id)
        if not attempts:
            attempts = self.real_experiments.plan(benchmark_id)
        experiment_report = self.real_experiments.report(benchmark_id)
        no_fit_report = self.real_search.render_no_fit_report(benchmark_id)
        links = [
            str(root / "selected_benchmark" / "real_benchmark_search" / "real_benchmark_no_fit_report.md"),
            str(root / "selected_benchmark" / "real_benchmark_experiments" / "real_benchmark_experiment_attempts.md"),
        ]
        warnings = [
            "Real public benchmark status is included as grounding/no-fit evidence, not deployment-validity evidence.",
        ]
        if "No candidate survived" in no_fit_report or search.status == "no_fit":
            status = "no_fit"
        elif any(attempt.status == "failed" for attempt in attempts):
            status = "failed"
        elif any(attempt.status == "complete" for attempt in attempts):
            status = "complete"
        elif any(attempt.status == "planned" for attempt in attempts):
            status = "planned"
        else:
            status = search.status
        if "Claim Support: `sanity_check`" in experiment_report:
            warnings.append("At least one real benchmark attempt is sanity-check only and cannot support primary validity.")
        return status, links, warnings

    def _write_related_work_section(
        self,
        manuscript_id: str,
        *,
        matrix_id: str,
        matrix_path: str,
        citation_ids: list[str],
        warnings: list[str],
    ) -> ManuscriptSection:
        section = self._ensure_section(manuscript_id, "related_work", "Related Work")
        section = self.manuscripts.update_section_links(
            manuscript_id=manuscript_id,
            section_id=section.id,
            source_paper_ids=citation_ids,
            source_artifact_ids=[matrix_id, matrix_path],
            status="needs_review",
            warnings=warnings,
        )
        root = self.manuscripts.manuscript_root(manuscript_id)
        _upsert_integration_block(root / section.content_path, _related_work_section_text(matrix_id, matrix_path, citation_ids, warnings))
        return section

    def _write_artifact_appendix(
        self,
        manuscript_id: str,
        *,
        package_id: str,
        artifact_links: list[str],
        warnings: list[str],
    ) -> ManuscriptSection:
        section = self._ensure_section(manuscript_id, "appendix", "Artifact Evaluation Appendix")
        section = self.manuscripts.update_section_links(
            manuscript_id=manuscript_id,
            section_id=section.id,
            source_artifact_ids=[package_id, *artifact_links],
            status="needs_review",
            warnings=warnings,
        )
        root = self.manuscripts.manuscript_root(manuscript_id)
        _upsert_integration_block(root / section.content_path, _artifact_appendix_text(package_id, artifact_links, warnings))
        return section

    def _write_limitations_update(
        self,
        manuscript_id: str,
        *,
        real_status: str,
        related_status: str,
        artifact_status: str,
    ) -> ManuscriptSection:
        section = self._ensure_section(manuscript_id, "limitations", "Limitations")
        limitation_warnings = [
            "No deployment-validity claim is introduced by venue artifact integration.",
            f"Real benchmark grounding status is `{real_status}` and must be stated explicitly.",
        ]
        section = self.manuscripts.update_section_links(
            manuscript_id=manuscript_id,
            section_id=section.id,
            source_artifact_ids=[
                f"related-work-matrix-status:{related_status}",
                f"artifact-package-status:{artifact_status}",
                f"real-benchmark-status:{real_status}",
            ],
            status="needs_review",
            warnings=limitation_warnings,
        )
        root = self.manuscripts.manuscript_root(manuscript_id)
        _upsert_integration_block(root / section.content_path, _limitations_text(real_status, related_status, artifact_status))
        return section

    def _write_submission_artifact_appendix(
        self,
        manuscript_root: Path,
        *,
        related_status: str,
        related_path: str,
        artifact_status: str,
        artifact_package_id: str,
        real_status: str,
        real_links: list[str],
    ) -> None:
        appendix = [
            "# Artifact Appendix",
            "",
            f"- Related-work matrix status: `{related_status}`",
            f"- Related-work matrix path: `{related_path}`",
            f"- Artifact package status: `{artifact_status}`",
            f"- Artifact package ID: `{artifact_package_id}`",
            f"- Real benchmark status: `{real_status}`",
            "",
            "## Real Benchmark / No-Fit Reports",
            "",
            *[f"- `{link}`" for link in real_links],
            "",
            "## Claim Boundary",
            "",
            "- These artifacts make the manuscript auditable for review; they do not claim acceptance or camera-ready readiness.",
            "- No deployment-validity claim is made by this appendix.",
        ]
        (manuscript_root / "submission" / "artifact_appendix.md").write_text("\n".join(appendix).rstrip() + "\n", encoding="utf-8")

    def _ensure_section(self, manuscript_id: str, section_type: str, title: str) -> ManuscriptSection:
        state = self.manuscripts.load_state(manuscript_id)
        for section in state.sections:
            if section.title == title or (section_type != "appendix" and section.section_type == section_type):
                return section
        return self.manuscripts.create_section(
            manuscript_id=manuscript_id,
            section_type=section_type,
            title=title,
            status="needs_review",
        )

    def _write_report(self, project_id: str, report: VenueArtifactIntegrationReport) -> None:
        path = self._report_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_venue_artifact_integration_report(report), encoding="utf-8")
        if report.manuscript_id:
            try:
                root = self.manuscripts.manuscript_root(report.manuscript_id)
            except FileNotFoundError:
                return
            (root / "submission" / "venue_artifact_integration_report.json").write_text(
                json.dumps(to_plain(report), indent=2) + "\n",
                encoding="utf-8",
            )
            (root / "submission" / "venue_artifact_integration_report.md").write_text(
                render_venue_artifact_integration_report(report),
                encoding="utf-8",
            )

    def _report_path(self, project_id: str) -> Path:
        program = self.projects.load_project(project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "venue_artifact_integration" / "report.json"


def render_venue_artifact_integration_report(report: VenueArtifactIntegrationReport) -> str:
    lines = [
        "# Venue Artifact Integration Report",
        "",
        f"- ID: `{report.id}`",
        f"- Manuscript ID: `{report.manuscript_id}`",
        f"- Related-work matrix status: `{report.related_work_matrix_status}`",
        f"- Artifact package status: `{report.artifact_package_status}`",
        f"- Real benchmark status: `{report.real_benchmark_status}`",
        f"- Integrated sections: {_fmt(report.integrated_sections)}",
        f"- Updated citations: {_fmt(report.updated_citations)}",
        f"- Updated artifact links: {_fmt(report.updated_artifact_links)}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in report.warnings] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in report.blockers] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Missing related-work matrix or artifact package blockers cannot be hidden by venue shaping.",
            "- Real benchmark no-fit evidence is allowed, but it does not validate deployment behavior.",
            "- This report does not claim acceptance, camera-ready status, or artifact badge eligibility.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _related_work_section_text(matrix_id: str, matrix_path: str, citation_ids: list[str], warnings: list[str]) -> str:
    lines = [
        "## Venue Artifact Integration",
        "",
        f"This section is linked to loadable related-work matrix `{matrix_id}`.",
        "",
        "## Auditable Matrix",
        "",
        f"- Matrix artifact: `{matrix_path}`",
        f"- Must-cite paper IDs: {_fmt(citation_ids)}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
    lines.extend(["", "This integration records citation state only; it does not add copied venue prose."])
    return "\n".join(lines).rstrip() + "\n"


def _artifact_appendix_text(package_id: str, artifact_links: list[str], warnings: list[str]) -> str:
    lines = [
        "## Artifact Evaluation Appendix",
        "",
        f"The manuscript references loadable artifact evaluation package `{package_id}`.",
        "",
        "## Linked Artifacts",
        "",
        *[f"- `{link}`" for link in artifact_links],
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- The package is loadable for review, but badge eligibility still requires separate checklist evidence.",
            "- Restricted data remains excluded by default.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _limitations_text(real_status: str, related_status: str, artifact_status: str) -> str:
    return (
        "## Venue Artifact Integration Limitations\n\n"
        f"- Related-work matrix integration status is `{related_status}`.\n"
        f"- Artifact evaluation package integration status is `{artifact_status}`.\n"
        f"- Real public benchmark grounding status is `{real_status}` and must be reported without upgrading synthetic evidence.\n"
        "- Synthetic selected-benchmark fixtures are not real collusion deployment validity evidence.\n"
        "- No deployment-validity claim is made by this venue artifact integration.\n"
    )


def _upsert_integration_block(path: Path, block: str) -> None:
    start = "<!-- gapforge:venue-artifact-integration:start -->"
    end = "<!-- gapforge:venue-artifact-integration:end -->"
    wrapped = f"{start}\n{block.rstrip()}\n{end}\n"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wrapped, encoding="utf-8")
        return
    existing = path.read_text(encoding="utf-8")
    if start in existing and end in existing:
        before, remainder = existing.split(start, 1)
        _old, after = remainder.split(end, 1)
        path.write_text(before.rstrip() + "\n\n" + wrapped + after.lstrip(), encoding="utf-8")
        return
    separator = "\n\n" if existing.strip() else ""
    path.write_text(existing.rstrip() + separator + wrapped, encoding="utf-8")


def _artifact_blockers(status: str, blockers: list[str], label: str) -> list[str]:
    if status in {"loaded", "repaired"} and not blockers:
        return []
    return [f"Loadable {label} is required before venue artifact integration can pass.", *blockers]


def _report_from_path(path: Path) -> VenueArtifactIntegrationReport:
    from gapforge.models import from_dict

    return from_dict(VenueArtifactIntegrationReport, json.loads(path.read_text(encoding="utf-8")))


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
