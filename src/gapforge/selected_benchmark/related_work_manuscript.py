"""V2.4 related-work manuscript revision and paper package for the selected benchmark."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.positioning import PositioningReport, SelectedBenchmarkPositioningManager
from gapforge.selected_benchmark.prior_work_refresh import (
    SelectedBenchmarkPriorWorkDossier,
    SelectedBenchmarkPriorWorkRefreshManager,
    render_selected_prior_work_dossier,
)
from gapforge.selected_benchmark.related_work_completion import _is_real_paper
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationManager, RelatedWorkCurationReport
from gapforge.selected_benchmark.related_work_matrix_v2 import (
    SelectedBenchmarkRelatedWorkMatrixV2,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    render_must_cite_report,
    render_related_work_matrix_v2,
)
from gapforge.selected_benchmark.reviewer import (
    PublicationReadinessReview,
    SelectedBenchmarkReviewerPanelBuilder,
    render_publication_readiness_review,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


@dataclass(slots=True)
class SelectedRelatedWorkManuscriptRevision:
    id: str
    benchmark_id: str
    related_work_section_path: str
    positioning_section_path: str
    prior_work_dossier_path: str
    related_work_matrix_path: str
    must_cite_ids: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    publication_readiness: str = "not_reviewed"
    claims_softened: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-manuscript"))


@dataclass(slots=True)
class SelectedPaperPackageV24:
    id: str
    benchmark_id: str
    package_dir: str
    revision_id: str
    publication_readiness: str
    publication_ready: bool = False
    files: list[str] = field(default_factory=list)
    must_cite_ids: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-paper-package-v24"))


class SelectedBenchmarkRelatedWorkManuscriptManager:
    """Revise selected benchmark manuscript artifacts after v2.4 related-work completion."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.curation_manager = RelatedWorkCurationManager(config)
        self.matrix_manager = SelectedBenchmarkRelatedWorkMatrixV2Manager(config)
        self.prior_work_manager = SelectedBenchmarkPriorWorkRefreshManager(config)
        self.positioning_manager = SelectedBenchmarkPositioningManager(config)
        self.reviewer_builder = SelectedBenchmarkReviewerPanelBuilder(config)

    def revise_related_work(self, benchmark_id: str) -> SelectedRelatedWorkManuscriptRevision:
        context = self._context(benchmark_id, include_review=False)
        revision = self._write_revision(context)
        self._write_revision_json(revision)
        return revision

    def update_positioning(self, benchmark_id: str) -> SelectedRelatedWorkManuscriptRevision:
        context = self._context(benchmark_id, include_review=False)
        revision = self._write_revision(context)
        self._write_revision_json(revision)
        return revision

    def paper_package_v24(self, benchmark_id: str) -> SelectedPaperPackageV24:
        review = self.reviewer_builder.publication_review(benchmark_id, after_related_work=True)
        context = self._context(benchmark_id, include_review=True, review=review)
        revision = self._write_revision(context)
        self._write_revision_json(revision)

        package_dir = self._benchmark_dir(context.spec.project_id) / "paper_package_v24"
        package_dir.mkdir(parents=True, exist_ok=True)
        files = self._write_package_files(package_dir, revision, context)
        package = SelectedPaperPackageV24(
            id=f"selected-paper-package-v24-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            package_dir=str(package_dir),
            revision_id=revision.id,
            publication_readiness=review.readiness,
            publication_ready=review.readiness == "publication_candidate",
            files=[path.name for path in files],
            must_cite_ids=list(context.matrix.must_cite_ids),
            missing_categories=list(context.matrix.missing_categories),
            blockers=[*review.fatal_blockers, *review.major_blockers],
            warnings=_package_warnings(context),
            provenance=Provenance(
                created_by_skill="selected-paper-package-v24",
                source_ids=[
                    benchmark_id,
                    revision.id,
                    context.matrix.id,
                    context.dossier.id,
                    context.positioning.id,
                    review.id,
                ],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Exported v2.4 selected benchmark paper package with completed related-work, softened claims, "
                    "and after-related-work publication-readiness status."
                ),
            ),
        )
        package_path = package_dir / "selected_paper_package_v24.json"
        package_path.write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def _context(
        self,
        benchmark_id: str,
        *,
        include_review: bool,
        review: PublicationReadinessReview | None = None,
    ) -> _RelatedWorkManuscriptContext:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        papers = self._paper_by_id(benchmark_id)
        matrix = self.matrix_manager.load_or_build(benchmark_id)
        dossier = self.prior_work_manager.load_or_refresh(benchmark_id)
        positioning = self.positioning_manager.load_or_build(benchmark_id)
        curation_report = self.curation_manager.report(benchmark_id)
        self._validate_known_real_citations(
            benchmark_id,
            papers,
            [
                *[entry.paper_id for entry in matrix.entries],
                *matrix.must_cite_ids,
                *matrix.closest_prior_work_ids,
                *matrix.baseline_source_ids,
                *dossier.closest_prior_work_ids,
            ],
        )
        readiness_review = review
        if include_review and readiness_review is None:
            readiness_review = self.reviewer_builder.publication_review(benchmark_id, after_related_work=True)
        return _RelatedWorkManuscriptContext(
            spec=spec,
            papers=papers,
            curation_report=curation_report,
            matrix=matrix,
            dossier=dossier,
            positioning=positioning,
            review=readiness_review,
        )

    def _validate_known_real_citations(self, benchmark_id: str, papers: dict[str, Paper], paper_ids: list[str]) -> None:
        unknown = sorted({paper_id for paper_id in paper_ids if paper_id and paper_id not in papers})
        fallback = sorted({paper_id for paper_id in paper_ids if paper_id in papers and not _is_real_paper(papers[paper_id])})
        if unknown or fallback:
            details: list[str] = []
            if unknown:
                details.append(f"unknown paper IDs: {', '.join(unknown)}")
            if fallback:
                details.append(f"fallback/non-real paper IDs: {', '.join(fallback)}")
            raise ValueError(f"Selected benchmark v2.4 manuscript contains fake citations for `{benchmark_id}` ({'; '.join(details)}).")

    def _write_revision(self, context: _RelatedWorkManuscriptContext) -> SelectedRelatedWorkManuscriptRevision:
        manuscript_dir = self._manuscript_dir(context.spec.project_id)
        sections_dir = manuscript_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)

        related_work_path = sections_dir / "02_related_work_v24.md"
        positioning_path = sections_dir / "03_positioning_v24.md"
        dossier_path = sections_dir / "04_prior_work_dossier_v24.md"
        matrix_path = sections_dir / "05_related_work_matrix_v2.md"

        related_work_path.write_text(render_related_work_section_v24(context), encoding="utf-8")
        positioning_path.write_text(render_positioning_update_v24(context), encoding="utf-8")
        dossier_path.write_text(render_selected_prior_work_dossier(context.dossier), encoding="utf-8")
        matrix_path.write_text(render_related_work_matrix_v2(context.matrix), encoding="utf-8")

        revision = SelectedRelatedWorkManuscriptRevision(
            id=f"selected-related-work-manuscript-revision-{slugify(context.spec.id)}",
            benchmark_id=context.spec.id,
            related_work_section_path=str(related_work_path),
            positioning_section_path=str(positioning_path),
            prior_work_dossier_path=str(dossier_path),
            related_work_matrix_path=str(matrix_path),
            must_cite_ids=list(context.matrix.must_cite_ids),
            missing_categories=list(context.matrix.missing_categories),
            closest_prior_work_ids=list(context.dossier.closest_prior_work_ids),
            publication_readiness=context.review.readiness if context.review else "not_reviewed",
            claims_softened=any(claim.claim_softening_required for claim in context.positioning.recommended_claims),
            blockers=_revision_blockers(context),
            warnings=_revision_warnings(context),
            provenance=Provenance(
                created_by_skill="selected-related-work-manuscript",
                source_ids=[context.spec.id, context.matrix.id, context.dossier.id, context.positioning.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Revised selected benchmark manuscript related-work and contribution-positioning sections from curated real papers."
                ),
            ),
        )
        return revision

    def _write_revision_json(self, revision: SelectedRelatedWorkManuscriptRevision) -> None:
        path = Path(revision.related_work_section_path).parents[1] / "related_work_manuscript_revision_v24.json"
        path.write_text(json.dumps(to_plain(revision), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_selected_related_work_manuscript_revision(revision), encoding="utf-8")

    def _write_package_files(
        self,
        package_dir: Path,
        revision: SelectedRelatedWorkManuscriptRevision,
        context: _RelatedWorkManuscriptContext,
    ) -> list[Path]:
        files: list[Path] = []
        file_payloads = {
            "README.md": render_selected_paper_package_v24_readme(revision, context),
            "related_work_v24.md": Path(revision.related_work_section_path).read_text(encoding="utf-8"),
            "positioning_v24.md": Path(revision.positioning_section_path).read_text(encoding="utf-8"),
            "prior_work_dossier_v24.md": render_selected_prior_work_dossier(context.dossier),
            "related_work_matrix_v2.md": render_related_work_matrix_v2(context.matrix),
            "must_cite_v24.md": render_must_cite_report(context.matrix),
            "publication_readiness_v24.md": render_publication_readiness_review(context.review)
            if context.review
            else "# Publication Readiness Review\n\n- Status: `not_reviewed`\n",
        }
        for name, text in file_payloads.items():
            path = package_dir / name
            path.write_text(text, encoding="utf-8")
            files.append(path)

        bibliography_path = package_dir / "must_cite_paper_ids.json"
        bibliography_path.write_text(json.dumps(context.matrix.must_cite_ids, indent=2) + "\n", encoding="utf-8")
        files.append(bibliography_path)

        manifest_path = package_dir / "package_manifest_v24.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "benchmark_id": context.spec.id,
                    "revision_id": revision.id,
                    "publication_readiness": context.review.readiness if context.review else "not_reviewed",
                    "publication_ready": bool(context.review and context.review.readiness == "publication_candidate"),
                    "files": sorted(path.name for path in files),
                    "must_cite_ids": context.matrix.must_cite_ids,
                    "missing_categories": context.matrix.missing_categories,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        files.append(manifest_path)

        source_revision_json = Path(revision.related_work_section_path).parents[1] / "related_work_manuscript_revision_v24.json"
        if source_revision_json.exists():
            target = package_dir / source_revision_json.name
            shutil.copyfile(source_revision_json, target)
            files.append(target)
        return files

    def _paper_by_id(self, benchmark_id: str) -> dict[str, Paper]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _manuscript_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "main_manuscript"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(slots=True)
class _RelatedWorkManuscriptContext:
    spec: SequentialSpecificityBenchmarkSpec
    papers: dict[str, Paper]
    curation_report: RelatedWorkCurationReport
    matrix: SelectedBenchmarkRelatedWorkMatrixV2
    dossier: SelectedBenchmarkPriorWorkDossier
    positioning: PositioningReport
    review: PublicationReadinessReview | None = None


def render_related_work_section_v24(context: _RelatedWorkManuscriptContext) -> str:
    lines = [
        "# Related Work",
        "",
        (
            "This section cites only known real paper records attached to the selected benchmark related-work campaign. "
            "Fallback records are not counted as completed related work."
        ),
        "",
        "## Category Coverage",
        "",
    ]
    for category, coverage in context.matrix.category_coverage.items():
        paper_ids = list(coverage.get("paper_ids", []))
        status = str(coverage.get("status", "missing"))
        citation_text = ", ".join(_citation(paper_id) for paper_id in paper_ids) or "no accepted real paper"
        lines.append(f"- {category}: `{status}`; {citation_text}.")

    lines.extend(["", "## Related Work by Relationship", ""])
    if context.matrix.entries:
        for entry in context.matrix.entries:
            paper = context.papers[entry.paper_id]
            lines.append(
                f"- {_citation(entry.paper_id)} {paper.title} ({paper.year}) is used as a {entry.relationship} "
                f"for `{entry.category}`. Notes: {entry.notes or 'none'}."
            )
    else:
        lines.append("- No accepted real related-work papers are attached yet.")

    lines.extend(["", "## Closest Prior Work Comparison", ""])
    if context.dossier.closest_prior_work_ids:
        lines.append(f"- Closest prior work: {', '.join(_citation(paper_id) for paper_id in context.dossier.closest_prior_work_ids)}.")
    else:
        lines.append("- Closest prior work has not been marked explicitly.")
    lines.extend([f"- New/claimed difference: {item}" for item in context.dossier.what_is_new] or ["- New/claimed difference: none"])
    lines.extend([f"- Not new: {item}" for item in context.dossier.what_is_not_new] or ["- Not new: none"])
    lines.extend(
        [f"- Decisive difference needed: {item}" for item in context.dossier.decisive_difference_needed]
        or ["- Decisive difference needed: none"]
    )

    lines.extend(["", "## Must-cite coverage", ""])
    lines.extend([f"- {_citation(paper_id)}" for paper_id in context.matrix.must_cite_ids] or ["- none"])

    lines.extend(["", "## Missing related-work categories", ""])
    lines.extend([f"- {category}" for category in context.matrix.missing_categories] or ["- none"])

    lines.extend(["", "## Synthetic Benchmark Limitation", ""])
    lines.append(
        "The selected benchmark remains synthetic-only evidence. It supports benchmark/protocol positioning, not real-world "
        "deployment-validity claims."
    )
    return "\n".join(lines).rstrip() + "\n"


def render_positioning_update_v24(context: _RelatedWorkManuscriptContext) -> str:
    lines = [
        "# Contribution Positioning Update",
        "",
        "## Publication-safe claims",
        "",
    ]
    for claim in context.positioning.recommended_claims:
        lines.extend(
            [
                f"- Contribution type: `{claim.contribution_type}`",
                f"- Novelty strength: `{claim.novelty_strength}`",
                f"- Revised claim: {claim.revised_claim}",
                f"- Evidence basis: {'; '.join(claim.evidence_basis) or 'none'}",
                "",
            ]
        )
    lines.extend(["## Claims to avoid", ""])
    lines.extend([f"- {item}" for item in context.positioning.claims_to_avoid] or ["- none"])
    lines.extend(["", "## Citation requirements", ""])
    lines.extend([f"- {item}" for item in context.positioning.citation_requirements] or ["- none"])
    lines.extend(["", "## Preserved limitations", ""])
    lines.append("- Synthetic data does not establish real-world deployment validity.")
    lines.append("- Publication-ready status requires an after-related-work publication review pass.")
    return "\n".join(lines).rstrip() + "\n"


def render_selected_related_work_manuscript_revision(revision: SelectedRelatedWorkManuscriptRevision) -> str:
    lines = [
        "# Selected Benchmark Related-Work Manuscript Revision",
        "",
        f"- Benchmark ID: `{revision.benchmark_id}`",
        f"- Publication readiness: `{revision.publication_readiness}`",
        f"- Claims softened: `{revision.claims_softened}`",
        f"- Must-cite IDs: {', '.join(revision.must_cite_ids) or 'none'}",
        f"- Missing categories: {', '.join(revision.missing_categories) or 'none'}",
        f"- Related-work section: `{revision.related_work_section_path}`",
        f"- Positioning section: `{revision.positioning_section_path}`",
        f"- Prior-work dossier: `{revision.prior_work_dossier_path}`",
        f"- Related-work matrix: `{revision.related_work_matrix_path}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in revision.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in revision.warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_selected_paper_package_v24(package: SelectedPaperPackageV24) -> str:
    lines = [
        "# Selected Paper Package V2.4",
        "",
        f"- Package ID: `{package.id}`",
        f"- Benchmark ID: `{package.benchmark_id}`",
        f"- Publication readiness: `{package.publication_readiness}`",
        f"- Publication ready: `{package.publication_ready}`",
        "- Publication-ready status requires publication review pass.",
        f"- Package directory: `{package.package_dir}`",
        f"- Must-cite IDs: {', '.join(package.must_cite_ids) or 'none'}",
        f"- Missing categories: {', '.join(package.missing_categories) or 'none'}",
        "",
        "## Files",
        "",
    ]
    lines.extend([f"- `{filename}`" for filename in package.files] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in package.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in package.warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_selected_paper_package_v24_readme(
    revision: SelectedRelatedWorkManuscriptRevision,
    context: _RelatedWorkManuscriptContext,
) -> str:
    review = context.review
    lines = [
        "# Selected Benchmark Paper Package V2.4",
        "",
        f"- Benchmark ID: `{context.spec.id}`",
        f"- Revision ID: `{revision.id}`",
        f"- Publication readiness: `{review.readiness if review else 'not_reviewed'}`",
        f"- Publication ready: `{bool(review and review.readiness == 'publication_candidate')}`",
        "- Publication-ready status requires publication review pass.",
        "- No fake citations: all citations in the related-work section resolve to known real paper records.",
        "- Synthetic limitations preserved: no real-world deployment-validity claim is made.",
        "",
        "## Included Artifacts",
        "",
        "- `related_work_v24.md`",
        "- `positioning_v24.md`",
        "- `prior_work_dossier_v24.md`",
        "- `related_work_matrix_v2.md`",
        "- `must_cite_v24.md`",
        "- `publication_readiness_v24.md`",
        "- `must_cite_paper_ids.json`",
        "- `package_manifest_v24.json`",
        "",
        "## Missing Categories",
        "",
    ]
    lines.extend([f"- {category}" for category in context.matrix.missing_categories] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _citation(paper_id: str) -> str:
    return f"[@{paper_id}]"


def _revision_blockers(context: _RelatedWorkManuscriptContext) -> list[str]:
    blockers = [f"Missing related-work category: {category}" for category in context.matrix.missing_categories]
    if context.review:
        blockers.extend(context.review.fatal_blockers)
        blockers.extend(context.review.major_blockers)
    return _dedupe(blockers)


def _revision_warnings(context: _RelatedWorkManuscriptContext) -> list[str]:
    warnings = list(context.matrix.reviewer_omission_risks)
    warnings.extend(context.positioning.reviewer_risks)
    warnings.append("Synthetic-only evidence must remain visible in all manuscript claims.")
    return _dedupe(warnings)


def _package_warnings(context: _RelatedWorkManuscriptContext) -> list[str]:
    warnings = _revision_warnings(context)
    if not context.review or context.review.readiness != "publication_candidate":
        warnings.append("Publication-ready status is false until the after-related-work reviewer returns publication_candidate.")
    return _dedupe(warnings)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
