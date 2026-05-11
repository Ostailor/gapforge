"""v2.4 release gate for related-work remediation and publication readiness."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, from_dict
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v23 import V23ReleaseGateEnforcer, V23ReleaseGateResult, _has_synthetic_deployment_overclaim
from gapforge.selected_benchmark.positioning import PositioningReport
from gapforge.selected_benchmark.prior_work_refresh import SelectedBenchmarkPriorWorkDossier
from gapforge.selected_benchmark.related_work_completion import _is_real_paper
from gapforge.selected_benchmark.related_work_curation import RelatedWorkCurationReport
from gapforge.selected_benchmark.related_work_manuscript import SelectedPaperPackageV24, SelectedRelatedWorkManuscriptRevision
from gapforge.selected_benchmark.related_work_matrix_v2 import SelectedBenchmarkRelatedWorkMatrixV2
from gapforge.selected_benchmark.related_work_reading import RelatedWorkReadingStatus
from gapforge.selected_benchmark.related_work_search import RequiredRelatedWorkSearchCampaign
from gapforge.selected_benchmark.reviewer import PublicationReadinessReview
from gapforge.state import ResearchStateManager

V24_OUTCOMES = {"publication_candidate", "workshop_candidate", "revise_related_work", "revise_benchmark", "no_go"}


@dataclass(slots=True)
class V24ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    decision_status: str = "revise_related_work"
    publication_readiness: str = ""
    novelty_status: str = ""
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V24ReleaseGateEnforcer:
    """Check whether v2.4 honestly remediated v2.3 related-work blockers."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)

    def evaluate(self) -> V24ReleaseGateResult:
        v23_result = V23ReleaseGateEnforcer(self.config).evaluate()
        project_id = v23_result.project_id
        benchmark_id = v23_result.benchmark_id
        project_root = self._project_root(project_id) if project_id else None
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        artifacts = _V24Artifacts.load(benchmark_dir, benchmark_id)
        paper_by_id = self._paper_by_id(project_id) if project_id else {}

        fake_citations = _fake_citations(artifacts, paper_by_id, benchmark_dir)
        hidden_missing = _hidden_missing_categories(artifacts)
        publication_ready_mismatch = _publication_ready_mismatch(artifacts)
        deployment_overclaim_paths = self._deployment_overclaim_paths(benchmark_dir)
        after_related_work_review = _after_related_work_review(artifacts)
        v23_passes_or_v24_overlay = _v23_passes_or_v24_overlay(v23_result)
        decision_status = _decision_status(artifacts, fake_citations=fake_citations, hidden_missing=hidden_missing)

        requirements = {
            "v23_release_gate_passes": v23_passes_or_v24_overlay,
            "related_work_search_campaign_exists": artifacts.search_campaign is not None,
            "category_curation_report_exists": artifacts.curation_report is not None,
            "related_work_reading_report_exists": bool(artifacts.reading_statuses) and artifacts.reading_report_exists,
            "closest_prior_work_dossier_refreshed": artifacts.prior_work_dossier is not None,
            "contribution_positioning_report_exists": artifacts.positioning_report is not None,
            "related_work_matrix_v2_exists": artifacts.matrix_v2 is not None,
            "publication_review_rerun_after_related_work_exists": artifacts.publication_review is not None and after_related_work_review,
            "manuscript_related_work_revision_exists": artifacts.manuscript_revision is not None,
            "no_fake_citations": not fake_citations,
            "no_hidden_missing_categories": not hidden_missing,
            "no_publication_ready_claim_unless_review_passes": not publication_ready_mismatch,
            "no_deployment_validity_claim_from_synthetic_evidence": not deployment_overclaim_paths,
        }
        blockers = _requirement_blockers(requirements)
        if not v23_passes_or_v24_overlay:
            blockers.extend(f"v2.3 gate blocker: {blocker}" for blocker in v23_result.blockers)
        blockers.extend(f"Fake citation or non-real paper reference: {item}" for item in fake_citations)
        blockers.extend(f"Missing category hidden across v2.4 artifacts: {item}" for item in hidden_missing)
        blockers.extend(f"Deployment-validity overclaim found in {path}" for path in deployment_overclaim_paths)
        if publication_ready_mismatch:
            blockers.append("Publication-ready claim is present even though the after-related-work review did not pass.")

        warnings = _warnings(artifacts, decision_status=decision_status)
        passed = all(requirements.values())
        return V24ReleaseGateResult(
            passed=passed,
            status="pass" if passed else "fail",
            recommended_next_version="v2.4" if passed else "v2.4-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            project_id=project_id,
            benchmark_id=benchmark_id,
            decision_status=decision_status,
            publication_readiness=artifacts.publication_review.readiness if artifacts.publication_review else "",
            novelty_status=artifacts.prior_work_dossier.novelty_status if artifacts.prior_work_dossier else "",
            artifact_paths=_artifact_paths(benchmark_dir, artifacts, v23_result),
        )

    def write_outputs(self, result: V24ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v24_release_gate_latest.json"
        data_md_path = self.release_dir / "v24-release-gate-latest.md"
        report = render_v24_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v24-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _project_root(self, project_id: str) -> Path:
        return Path(self.projects.load_project(project_id).project.root_dir)

    def _paper_by_id(self, project_id: str) -> dict[str, Paper]:
        program = self.projects.load_project(project_id)
        papers: dict[str, Paper] = {}
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                papers.setdefault(paper.id, paper)
        return papers

    def _deployment_overclaim_paths(self, benchmark_dir: Path | None) -> list[str]:
        if benchmark_dir is None:
            return []
        roots = [benchmark_dir / "main_manuscript", benchmark_dir / "paper_package_v24"]
        paths: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if _has_synthetic_deployment_overclaim(text):
                    paths.append(str(path))
        return paths


@dataclass(slots=True)
class _V24Artifacts:
    search_campaign: RequiredRelatedWorkSearchCampaign | None = None
    curation_report: RelatedWorkCurationReport | None = None
    reading_statuses: list[RelatedWorkReadingStatus] = field(default_factory=list)
    reading_report_exists: bool = False
    prior_work_dossier: SelectedBenchmarkPriorWorkDossier | None = None
    positioning_report: PositioningReport | None = None
    matrix_v2: SelectedBenchmarkRelatedWorkMatrixV2 | None = None
    publication_review: PublicationReadinessReview | None = None
    manuscript_revision: SelectedRelatedWorkManuscriptRevision | None = None
    paper_package: SelectedPaperPackageV24 | None = None

    @classmethod
    def load(cls, benchmark_dir: Path | None, benchmark_id: str) -> _V24Artifacts:
        if benchmark_dir is None:
            return cls()
        return cls(
            search_campaign=_read_dataclass(
                RequiredRelatedWorkSearchCampaign,
                benchmark_dir / "related_work_search" / "required_related_work_search_campaign.json",
                benchmark_id,
            ),
            curation_report=_read_dataclass(
                RelatedWorkCurationReport,
                benchmark_dir / "related_work_curation" / "related_work_curation_report.json",
                benchmark_id,
            ),
            reading_statuses=_read_statuses(
                benchmark_dir / "related_work_reading" / "related_work_reading_statuses.json",
                benchmark_id,
            ),
            reading_report_exists=(benchmark_dir / "related_work_reading" / "related_work_reading_report.md").exists(),
            prior_work_dossier=_read_dataclass(
                SelectedBenchmarkPriorWorkDossier,
                benchmark_dir / "prior_work_dossier" / "selected_prior_work_dossier.json",
                benchmark_id,
            ),
            positioning_report=_read_dataclass(
                PositioningReport,
                benchmark_dir / "positioning" / "positioning_report.json",
                benchmark_id,
            ),
            matrix_v2=_read_dataclass(
                SelectedBenchmarkRelatedWorkMatrixV2,
                benchmark_dir / "related_work_matrix_v2" / "related_work_matrix_v2.json",
                benchmark_id,
            ),
            publication_review=_read_dataclass(
                PublicationReadinessReview,
                benchmark_dir / "reviews" / "main_publication_review_after_related_work.json",
                benchmark_id,
            ),
            manuscript_revision=_read_dataclass(
                SelectedRelatedWorkManuscriptRevision,
                benchmark_dir / "main_manuscript" / "related_work_manuscript_revision_v24.json",
                benchmark_id,
            ),
            paper_package=_read_dataclass(
                SelectedPaperPackageV24,
                benchmark_dir / "paper_package_v24" / "selected_paper_package_v24.json",
                benchmark_id,
            ),
        )


def render_v24_release_gate_markdown(result: V24ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.4 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Selected project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Decision status: `{result.decision_status}`",
        f"- Publication readiness: `{result.publication_readiness or 'missing'}`",
        f"- Novelty status: `{result.novelty_status or 'missing'}`",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- v2.4 requires explicit related-work search, curation, reading, dossier, positioning, matrix, review, "
            "and manuscript artifacts.",
            "- Publication-candidate labels require the after-related-work publication review to pass.",
            "- Missing categories must remain visible across curation, matrix, manuscript revision, and paper package artifacts.",
            "- Fake citations, fallback-only citations, and unknown paper IDs block the gate.",
            "- Synthetic benchmark evidence must not be used to claim deployment validity.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _read_dataclass(model: type[Any], path: Path, benchmark_id: str) -> Any | None:
    if not path.exists():
        return None
    try:
        value = from_dict(model, json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if getattr(value, "benchmark_id", benchmark_id) == benchmark_id else None


def _read_statuses(path: Path, benchmark_id: str) -> list[RelatedWorkReadingStatus]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        statuses = [from_dict(RelatedWorkReadingStatus, item) for item in payload]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return [status for status in statuses if status.benchmark_id == benchmark_id]


def _after_related_work_review(artifacts: _V24Artifacts) -> bool:
    review = artifacts.publication_review
    if review is None:
        return False
    source_ids = set(review.provenance.source_ids)
    return bool(
        artifacts.prior_work_dossier
        and artifacts.positioning_report
        and artifacts.matrix_v2
        and artifacts.prior_work_dossier.id in source_ids
        and artifacts.positioning_report.id in source_ids
        and artifacts.matrix_v2.id in source_ids
    )


def _v23_passes_or_v24_overlay(v23_result: V23ReleaseGateResult) -> bool:
    if v23_result.passed:
        return True
    failed = {name for name, passed in v23_result.requirements.items() if not passed}
    return failed == {"evidence_is_not_mislabeled"} and v23_result.decision_status in {
        "publication_candidate",
        "workshop_candidate",
        "revise_benchmark",
        "no_go",
    }


def _fake_citations(artifacts: _V24Artifacts, paper_by_id: dict[str, Paper], benchmark_dir: Path | None) -> list[str]:
    referenced = set(_referenced_paper_ids(artifacts))
    if benchmark_dir is not None:
        referenced.update(_citation_tokens(benchmark_dir / "main_manuscript"))
        referenced.update(_citation_tokens(benchmark_dir / "paper_package_v24"))
    fake: list[str] = []
    for paper_id in sorted(referenced):
        paper = paper_by_id.get(paper_id)
        if paper is None:
            fake.append(f"{paper_id} (unknown)")
        elif not _is_real_paper(paper):
            fake.append(f"{paper_id} (fallback/non-real)")
    return fake


def _referenced_paper_ids(artifacts: _V24Artifacts) -> list[str]:
    ids: list[str] = []
    if artifacts.search_campaign:
        for search in artifacts.search_campaign.category_searches.values():
            ids.extend(search.accepted_paper_ids)
    if artifacts.curation_report:
        ids.extend(artifacts.curation_report.closest_prior_work_ids)
        for status in artifacts.curation_report.category_statuses.values():
            ids.extend(str(paper_id) for paper_id in status.get("accepted_paper_ids", []))
    if artifacts.reading_statuses:
        ids.extend(status.paper_id for status in artifacts.reading_statuses)
    if artifacts.prior_work_dossier:
        ids.extend(artifacts.prior_work_dossier.closest_prior_work_ids)
    if artifacts.positioning_report:
        for claim in artifacts.positioning_report.recommended_claims:
            ids.extend(_ids_from_text(" ".join([claim.revised_claim, *claim.evidence_basis, *claim.reasons])))
        ids.extend(_ids_from_text(" ".join(artifacts.positioning_report.citation_requirements)))
    if artifacts.matrix_v2:
        ids.extend(entry.paper_id for entry in artifacts.matrix_v2.entries)
        ids.extend(artifacts.matrix_v2.must_cite_ids)
        ids.extend(artifacts.matrix_v2.closest_prior_work_ids)
        ids.extend(artifacts.matrix_v2.baseline_source_ids)
    if artifacts.manuscript_revision:
        ids.extend(artifacts.manuscript_revision.must_cite_ids)
        ids.extend(artifacts.manuscript_revision.closest_prior_work_ids)
    if artifacts.paper_package:
        ids.extend(artifacts.paper_package.must_cite_ids)
    return _unique(ids)


def _citation_tokens(root: Path) -> list[str]:
    if not root.exists():
        return []
    tokens: list[str] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            tokens.extend(re.findall(r"\[@([A-Za-z0-9_.:-]+)\]", text))
    return tokens


def _ids_from_text(text: str) -> list[str]:
    return re.findall(r"\b(?:real|paper|arxiv|doi)-[A-Za-z0-9_.:-]+\b", text)


def _hidden_missing_categories(artifacts: _V24Artifacts) -> list[str]:
    curation_missing = set(artifacts.curation_report.missing_categories if artifacts.curation_report else [])
    matrix_missing = set(artifacts.matrix_v2.missing_categories if artifacts.matrix_v2 else [])
    revision_missing = set(artifacts.manuscript_revision.missing_categories if artifacts.manuscript_revision else [])
    package_missing = set(artifacts.paper_package.missing_categories if artifacts.paper_package else [])
    hidden: set[str] = set()
    hidden.update(category for category in curation_missing if category not in matrix_missing)
    hidden.update(category for category in curation_missing if artifacts.manuscript_revision and category not in revision_missing)
    hidden.update(category for category in curation_missing if artifacts.paper_package and category not in package_missing)
    if curation_missing and artifacts.publication_review and artifacts.publication_review.readiness == "publication_candidate":
        hidden.update(curation_missing)
    return sorted(hidden)


def _publication_ready_mismatch(artifacts: _V24Artifacts) -> bool:
    review_passed = bool(artifacts.publication_review and artifacts.publication_review.readiness == "publication_candidate")
    package_ready = bool(artifacts.paper_package and artifacts.paper_package.publication_ready)
    revision_ready = bool(artifacts.manuscript_revision and artifacts.manuscript_revision.publication_readiness == "publication_candidate")
    return (package_ready or revision_ready) and not review_passed


def _decision_status(
    artifacts: _V24Artifacts,
    *,
    fake_citations: list[str],
    hidden_missing: list[str],
) -> str:
    if not _required_related_work_artifacts_present(artifacts):
        return "revise_related_work"
    if fake_citations or hidden_missing:
        return "revise_related_work"
    if artifacts.matrix_v2 and any(entry.relationship == "directly solves" for entry in artifacts.matrix_v2.entries):
        return "no_go"
    if artifacts.prior_work_dossier and artifacts.prior_work_dossier.novelty_status == "duplicate":
        return "no_go"
    if artifacts.publication_review and artifacts.publication_review.readiness in V24_OUTCOMES:
        return artifacts.publication_review.readiness
    if artifacts.curation_report and artifacts.curation_report.missing_categories:
        return "revise_related_work"
    return "revise_benchmark"


def _required_related_work_artifacts_present(artifacts: _V24Artifacts) -> bool:
    return bool(
        artifacts.search_campaign
        and artifacts.curation_report
        and artifacts.reading_statuses
        and artifacts.reading_report_exists
        and artifacts.prior_work_dossier
        and artifacts.positioning_report
        and artifacts.matrix_v2
        and artifacts.manuscript_revision
    )


def _warnings(artifacts: _V24Artifacts, *, decision_status: str) -> list[str]:
    warnings = ["v2.4 accepts honest publication, workshop, revise, or no-go outcomes after related-work remediation."]
    if decision_status in {"workshop_candidate", "revise_related_work", "revise_benchmark", "no_go"}:
        warnings.append(f"v2.4 outcome is `{decision_status}`; do not label the package publication-ready unless review passed.")
    if artifacts.curation_report and artifacts.curation_report.missing_categories:
        warnings.append("Related-work categories remain incomplete and must stay visible.")
    if artifacts.prior_work_dossier and artifacts.prior_work_dossier.novelty_status in {"duplicate", "weak", "unknown"}:
        warnings.append(f"Novelty status is `{artifacts.prior_work_dossier.novelty_status}`.")
    return warnings


def _artifact_paths(
    benchmark_dir: Path | None,
    artifacts: _V24Artifacts,
    v23_result: V23ReleaseGateResult,
) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {
        "v23_release_gate": [str(Path("release_gate") / "v23_release_gate_latest.json")],
        "v23_artifacts": [item for values in v23_result.artifact_paths.values() for item in values],
    }
    if benchmark_dir is None:
        return paths
    candidates = {
        "related_work_search_campaign": benchmark_dir / "related_work_search" / "required_related_work_search_campaign.json",
        "category_curation_report": benchmark_dir / "related_work_curation" / "related_work_curation_report.json",
        "related_work_reading_statuses": benchmark_dir / "related_work_reading" / "related_work_reading_statuses.json",
        "related_work_reading_report": benchmark_dir / "related_work_reading" / "related_work_reading_report.md",
        "prior_work_dossier": benchmark_dir / "prior_work_dossier" / "selected_prior_work_dossier.json",
        "positioning_report": benchmark_dir / "positioning" / "positioning_report.json",
        "related_work_matrix_v2": benchmark_dir / "related_work_matrix_v2" / "related_work_matrix_v2.json",
        "publication_review": benchmark_dir / "reviews" / "main_publication_review_after_related_work.json",
        "manuscript_revision": benchmark_dir / "main_manuscript" / "related_work_manuscript_revision_v24.json",
        "paper_package_v24": benchmark_dir / "paper_package_v24" / "selected_paper_package_v24.json",
    }
    for key, path in candidates.items():
        if path.exists():
            paths[key] = [str(path)]
    return paths


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [
        f"`{name}` ({name.replace('_', ' ')}) is required for the v2.4 release gate." for name, passed in requirements.items() if not passed
    ]


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
