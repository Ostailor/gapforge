"""v2.5 release gate for real benchmark grounding, venue style, and harsh review calibration."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v24 import V24ReleaseGateEnforcer

V25_OUTCOMES = {"conference_candidate", "workshop_candidate", "revise_for_reviews", "benchmark_no_fit", "no_go"}
FAKE_CITATION_RE = re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)? et al\.?,?\s+(?:19|20)\d{2}\b|\[\d+\]|\bdoi:\s*\S+")


@dataclass(slots=True)
class V25ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    manuscript_id: str = ""
    v24_status: str = ""
    drastic_review_status: str = ""
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V25ReleaseGateEnforcer:
    """Validate v2.5 publication-style artifacts without bypassing evidence gates."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)

    def evaluate(self) -> V25ReleaseGateResult:
        v24 = self._v24_snapshot()
        project_id = v24.get("project_id", "")
        benchmark_id = v24.get("benchmark_id", "")
        project_root = self._project_root(project_id)
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        manuscript_root = self._manuscript_root(project_root)
        manuscript_id = manuscript_root.name if manuscript_root else ""

        artifacts = _V25Artifacts.load(self.config, benchmark_dir, manuscript_root)
        no_fit = _explicit_no_fit(artifacts.mapping_report)
        mapped = _has_supported_mapping(artifacts.mapping_report)
        fake_hits = _fake_citation_or_result_hits(project_root, artifacts)
        copied_hits = _copied_prose_hits(project_root, artifacts)
        drastic_fatal = bool(artifacts.drastic_panel.get("fatal_flaws"))
        publication_claim_with_fatal = drastic_fatal and _has_publication_ready_claim(manuscript_root, artifacts)

        requirements = {
            "v24_release_gate_passes": bool(v24.get("passed")),
            "vetted_benchmark_registry_exists": bool(artifacts.vetted_records),
            "selected_idea_mapped_or_no_fit_justified": mapped or no_fit,
            "vetted_benchmark_adapter_or_no_fit_report_exists": bool(artifacts.adapters) or no_fit,
            "venue_profile_selected": bool(artifacts.venue_profile),
            "style_corpus_allowed_or_synthetic": _style_corpus_allowed(artifacts.style_papers),
            "venue_style_analysis_generated": bool(artifacts.style_profiles),
            "manuscript_rewritten_for_venue": bool(artifacts.venue_rewrite_report),
            "openreview_fixture_ingested": _openreview_fixture_ingested(artifacts.review_datasets),
            "review_taxonomy_labels_generated": bool(artifacts.taxonomy_reports),
            "reviewer_evaluation_calibration_report_generated": bool(artifacts.reviewer_evaluations)
            and bool(artifacts.reviewer_calibration_reports),
            "drastic_reviewer_panel_generated": bool(artifacts.drastic_panel),
            "drastic_revision_plan_generated": bool(artifacts.drastic_revision_plan),
            "fake_citations_results_blocked": not fake_hits and _reviewer_hallucination_blocked(artifacts.reviewer_evaluations),
            "no_copied_paper_prose": not copied_hits,
            "no_publication_ready_claim_if_drastic_fatal_blockers": not publication_claim_with_fatal,
        }
        blockers = _requirement_blockers(requirements)
        blockers.extend(f"Fake citation/result signal: {hit}" for hit in fake_hits)
        blockers.extend(f"Copied prose signal: {hit}" for hit in copied_hits)
        if publication_claim_with_fatal:
            blockers.append("Drastic review has fatal blockers while a publication-ready claim remains visible.")

        status = _decision_status(
            requirements=requirements,
            v24=v24,
            no_fit=no_fit,
            drastic_fatal=drastic_fatal,
            publication_claim_with_fatal=publication_claim_with_fatal,
            blockers=blockers,
            artifacts=artifacts,
        )
        passed = status in {"conference_candidate", "workshop_candidate", "benchmark_no_fit"}
        return V25ReleaseGateResult(
            passed=passed,
            status=status,
            recommended_next_version="v2.6" if passed else "v2.5-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_warnings(artifacts, no_fit=no_fit, drastic_fatal=drastic_fatal),
            project_id=project_id,
            benchmark_id=benchmark_id,
            manuscript_id=manuscript_id,
            v24_status=str(v24.get("status", "")),
            drastic_review_status="fatal_blockers" if drastic_fatal else "no_fatal_blockers",
            artifact_paths=_artifact_paths(artifacts),
        )

    def write_outputs(self, result: V25ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v25_release_gate_latest.json"
        data_md_path = self.release_dir / "v25-release-gate-latest.md"
        report = render_v25_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v25-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _v24_snapshot(self) -> dict[str, Any]:
        path = self.release_dir / "v24_release_gate_latest.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        result = V24ReleaseGateEnforcer(self.config).evaluate()
        return result.to_dict()

    def _project_root(self, project_id: str) -> Path | None:
        if project_id:
            try:
                return Path(self.projects.load_project(project_id).project.root_dir)
            except FileNotFoundError:
                pass
        projects = sorted(self.config.project_root.glob("*"))
        return projects[-1] if projects else None

    def _manuscript_root(self, project_root: Path | None) -> Path | None:
        if project_root is None:
            return None
        manuscripts = sorted((project_root / "manuscripts").glob("*"))
        return manuscripts[-1] if manuscripts else None


@dataclass(slots=True)
class _V25Artifacts:
    vetted_records: list[dict[str, Any]] = field(default_factory=list)
    adapters: list[dict[str, Any]] = field(default_factory=list)
    mapping_report: dict[str, Any] = field(default_factory=dict)
    venue_profile: dict[str, Any] = field(default_factory=dict)
    style_papers: list[dict[str, Any]] = field(default_factory=list)
    style_profiles: list[dict[str, Any]] = field(default_factory=list)
    venue_rewrite_report: dict[str, Any] = field(default_factory=dict)
    review_datasets: list[dict[str, Any]] = field(default_factory=list)
    taxonomy_reports: list[dict[str, Any]] = field(default_factory=list)
    reviewer_evaluations: list[dict[str, Any]] = field(default_factory=list)
    reviewer_calibration_reports: list[Path] = field(default_factory=list)
    drastic_panel: dict[str, Any] = field(default_factory=dict)
    drastic_revision_plan: dict[str, Any] = field(default_factory=dict)
    paths: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, config: GapForgeConfig, benchmark_dir: Path | None, manuscript_root: Path | None) -> _V25Artifacts:
        artifacts = cls()
        artifacts.vetted_records = _read_json_glob(config.data_dir / "vetted_benchmarks" / "records", "*.record.json")
        artifacts.adapters = _read_json_glob(config.data_dir / "vetted_benchmarks" / "adapters", "*.adapter.json")
        artifacts.style_papers = _read_json_glob(config.data_dir / "style_corpus" / "papers", "style-paper-*.json")
        artifacts.style_profiles = _read_json_glob(config.data_dir / "style_corpus" / "analysis", "*.style_profile.json")
        artifacts.review_datasets = _read_json_glob(config.data_dir / "review_training" / "datasets", "*/dataset.json")
        artifacts.taxonomy_reports = _read_json_glob(
            config.data_dir / "review_training" / "datasets", "*/taxonomy/review_taxonomy_report.json"
        )
        artifacts.reviewer_evaluations = _read_json_glob(config.data_dir / "review_training" / "datasets", "*/reviewer_evaluation.json")
        artifacts.reviewer_calibration_reports = sorted(
            (config.data_dir / "review_training" / "datasets").glob("*/reviewer_calibration_report.md")
        )
        if benchmark_dir is not None:
            artifacts.mapping_report = _read_first_json(
                [
                    benchmark_dir / "vetted_mappings" / "selected_vetted_benchmark_mapping_report.json",
                    benchmark_dir / "vetted_mapping" / "selected_vetted_benchmark_mapping_report.json",
                ]
            )
        if manuscript_root is not None:
            artifacts.venue_profile = _read_json(manuscript_root / "submission" / "venue_profile.json")
            artifacts.venue_rewrite_report = _read_json(manuscript_root / "submission" / "venue_style_revision_report.json")
            artifacts.drastic_panel = _read_json(manuscript_root / "reviews" / "drastic" / "drastic_review_panel.json")
            artifacts.drastic_revision_plan = _read_json(manuscript_root / "reviews" / "drastic" / "drastic_revision_plan.json")
        artifacts.paths = _paths(config, benchmark_dir, manuscript_root)
        return artifacts


def render_v25_release_gate_markdown(result: V25ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.5 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Manuscript: `{result.manuscript_id or 'missing'}`",
        f"- v2.4 status: `{result.v24_status or 'missing'}`",
        f"- Drastic review: `{result.drastic_review_status}`",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- v2.5 validates real benchmark grounding separately from synthetic benchmark protocol scaffolding.",
            "- Venue style artifacts must use structure and rhetorical features only, not copied paper prose.",
            "- Reviewer calibration is critique calibration, not truth generation.",
            "- Drastic reviews can downgrade readiness; fatal blockers cannot coexist with publication-ready claims.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _decision_status(
    *,
    requirements: dict[str, bool],
    v24: dict[str, Any],
    no_fit: bool,
    drastic_fatal: bool,
    publication_claim_with_fatal: bool,
    blockers: list[str],
    artifacts: _V25Artifacts,
) -> str:
    if publication_claim_with_fatal or not requirements["fake_citations_results_blocked"] or not requirements["no_copied_paper_prose"]:
        return "no_go"
    hard_required = dict(requirements)
    hard_required.pop("vetted_benchmark_adapter_or_no_fit_report_exists", None)
    if not all(hard_required.values()):
        return "no_go"
    if not requirements["vetted_benchmark_adapter_or_no_fit_report_exists"]:
        return "no_go"
    if no_fit:
        return "benchmark_no_fit"
    if drastic_fatal:
        return "revise_for_reviews"
    if blockers:
        return "no_go"
    if _venue_publication_ready(artifacts.venue_rewrite_report) and v24.get("decision_status") == "publication_candidate":
        return "conference_candidate"
    return "workshop_candidate"


def _has_supported_mapping(mapping_report: dict[str, Any]) -> bool:
    if not mapping_report:
        return False
    if mapping_report.get("primary_candidate_ids") or mapping_report.get("auxiliary_candidate_ids"):
        return True
    return any(
        mapping.get("mapping_type") in {"direct", "substrate", "auxiliary", "sanity_check"}
        for mapping in mapping_report.get("mappings", [])
    )


def _explicit_no_fit(mapping_report: dict[str, Any]) -> bool:
    if not mapping_report:
        return False
    if _has_supported_mapping(mapping_report):
        return False
    conclusion = str(mapping_report.get("conclusion", "")).lower()
    if any(marker in conclusion for marker in ["no registered vetted benchmark fits", "no vetted benchmarks are registered", "no fit"]):
        return True
    mappings = mapping_report.get("mappings", [])
    return bool(mappings) and all(mapping.get("mapping_type") == "rejected" for mapping in mappings)


def _style_corpus_allowed(papers: list[dict[str, Any]]) -> bool:
    if not papers:
        return False
    for paper in papers:
        status = str(paper.get("license_status", "")).lower()
        source_text = f"{paper.get('source_url', '')} {paper.get('local_source_path', '')} {paper.get('provenance', {})}".lower()
        if status == "allowed" or "synthetic" in source_text:
            continue
        return False
    return True


def _openreview_fixture_ingested(datasets: list[dict[str, Any]]) -> bool:
    return any(
        dataset.get("source") == "synthetic_fixture" and int(dataset.get("paper_count", 0)) > 0 and int(dataset.get("review_count", 0)) > 0
        for dataset in datasets
    )


def _reviewer_hallucination_blocked(evaluations: list[dict[str, Any]]) -> bool:
    if not evaluations:
        return False
    return all(float(evaluation.get("hallucination_rate", 1.0)) == 0.0 for evaluation in evaluations)


def _fake_citation_or_result_hits(project_root: Path | None, artifacts: _V25Artifacts) -> list[str]:
    roots = [project_root, Path(artifacts.paths.get("data_root", [""])[0]) if artifacts.paths.get("data_root") else None]
    hits: list[str] = []
    for root in roots:
        if root is None or not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if FAKE_CITATION_RE.search(text) or "invented result" in text.lower() or "unlinked result" in text.lower():
                hits.append(str(path))
    return _unique(hits)


def _copied_prose_hits(project_root: Path | None, artifacts: _V25Artifacts) -> list[str]:
    hits = []
    report = artifacts.venue_rewrite_report
    for warning in report.get("copied_text_warnings", []) if isinstance(report, dict) else []:
        hits.append(str(warning))
    if project_root and project_root.exists():
        for path in project_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"UNIQUE_[A-Z0-9_]*DO_NOT_COPY[A-Z0-9_]*", text):
                    hits.append(str(path))
    return _unique(hits)


def _has_publication_ready_claim(manuscript_root: Path | None, artifacts: _V25Artifacts) -> bool:
    if artifacts.venue_rewrite_report.get("publication_ready") is True:
        return True
    if manuscript_root is None:
        return False
    status_path = manuscript_root / "state.json"
    text = ""
    if status_path.exists():
        text += status_path.read_text(encoding="utf-8", errors="ignore")
    for path in [manuscript_root / "submission" / "venue_style_revision_report.json", manuscript_root / "submission" / "status.md"]:
        if path.exists():
            text += "\n" + path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()
    return "publication_candidate" in lowered or "camera_ready" in lowered or '"publication_ready": true' in lowered


def _venue_publication_ready(report: dict[str, Any]) -> bool:
    return report.get("publication_ready") is True or report.get("status") in {"publication_ready", "venue_shaped_needs_review"}


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [f"Requirement `{name}` is not satisfied." for name, passed in requirements.items() if not passed]


def _warnings(artifacts: _V25Artifacts, *, no_fit: bool, drastic_fatal: bool) -> list[str]:
    warnings = []
    if no_fit:
        warnings.append("No vetted benchmark fit is accepted; manuscript must preserve the new benchmark protocol boundary.")
    if drastic_fatal:
        warnings.append(
            "Drastic review has fatal blockers; readiness is downgraded to revise_for_reviews unless publication claims remain."
        )
    if len(artifacts.style_papers) < 3:
        warnings.append("Style corpus is small; venue-style recommendations should be treated as weak evidence.")
    return warnings


def _artifact_paths(artifacts: _V25Artifacts) -> dict[str, list[str]]:
    return {key: value for key, value in artifacts.paths.items() if value}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_first_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        data = _read_json(path)
        if data:
            return data
    return {}


def _read_json_glob(root: Path, pattern: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    results = []
    for path in sorted(root.glob(pattern)):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _paths(config: GapForgeConfig, benchmark_dir: Path | None, manuscript_root: Path | None) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {"data_root": [str(config.data_dir)]}
    paths["vetted_records"] = [str(path) for path in sorted((config.data_dir / "vetted_benchmarks" / "records").glob("*.json"))]
    paths["adapters"] = [str(path) for path in sorted((config.data_dir / "vetted_benchmarks" / "adapters").glob("*.json"))]
    paths["style_papers"] = [str(path) for path in sorted((config.data_dir / "style_corpus" / "papers").glob("*.json"))]
    paths["review_datasets"] = [str(path) for path in sorted((config.data_dir / "review_training" / "datasets").glob("*/dataset.json"))]
    if benchmark_dir is not None:
        paths["mapping_report"] = [
            str(benchmark_dir / "vetted_mappings" / "selected_vetted_benchmark_mapping_report.json"),
            str(benchmark_dir / "vetted_mapping" / "selected_vetted_benchmark_mapping_report.json"),
        ]
    if manuscript_root is not None:
        paths["venue_profile"] = [str(manuscript_root / "submission" / "venue_profile.json")]
        paths["venue_rewrite_report"] = [str(manuscript_root / "submission" / "venue_style_revision_report.json")]
        paths["drastic_review"] = [str(manuscript_root / "reviews" / "drastic" / "drastic_review_panel.json")]
        paths["drastic_revision"] = [str(manuscript_root / "reviews" / "drastic" / "drastic_revision_plan.json")]
    return paths


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
