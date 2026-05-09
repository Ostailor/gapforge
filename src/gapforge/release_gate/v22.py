"""v2.2 release gate for selected-benchmark pilot maturity."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import from_dict
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v21 import V21ReleaseGateEnforcer, V21ReleaseGateResult
from gapforge.selected_benchmark.baselines import MonitorBaselineManager
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisResult
from gapforge.selected_benchmark.pilot_dataset import PilotTraceDataset
from gapforge.selected_benchmark.pilot_power import PilotPowerAssessment
from gapforge.selected_benchmark.pilot_run import REQUIRED_OUTPUT_KEYS, SelectedPilotExecution, SelectedPilotRunManifest
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec


@dataclass(slots=True)
class V22ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    pilot_dataset_id: str = ""
    pilot_manifest_id: str = ""
    pilot_execution_id: str = ""
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V22ReleaseGateEnforcer:
    """Machine-check whether v2.2 pilot benchmark artifacts are releasable."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)

    def evaluate(self) -> V22ReleaseGateResult:
        v21_result = self._v21_result()
        project_id = v21_result.project_id
        benchmark_id = v21_result.benchmark_id
        project_root = self._project_root(project_id) if project_id else None
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        dataset = self._latest_pilot_dataset(benchmark_dir, benchmark_id)
        manifest = self._latest_pilot_manifest(benchmark_dir, benchmark_id, dataset.id if dataset else "")
        execution = self._latest_pilot_execution(benchmark_dir, benchmark_id, manifest.id if manifest else "")
        analysis = self._latest_pilot_analysis(benchmark_dir, benchmark_id, execution.id if execution else "")
        power_assessment = self._latest_power_assessment(benchmark_dir, benchmark_id, dataset.id if dataset else "")
        claim_paths = self._claim_scan_paths(benchmark_dir)
        fake_paths = self._paths_with_disallowed_text(claim_paths, _has_fake_result_or_citation_marker)
        deployment_overclaim_paths = self._paths_with_disallowed_text(claim_paths, _has_synthetic_deployment_overclaim)
        alpha_001_powered = bool(power_assessment and "0.001" in power_assessment.alpha_targets_met)
        alpha_001_overclaim_paths = [] if alpha_001_powered else self._paths_with_disallowed_text(claim_paths, _has_alpha_001_overclaim)
        baseline_blockers = self._baseline_blockers(benchmark_id) if benchmark_id else ["Benchmark ID is missing."]

        requirements = {
            "v21_release_gate_passes": v21_result.passed,
            "pilot_power_plan_exists": self._path_exists(benchmark_dir, "pilot_power/pilot_power_plan.json"),
            "expanded_honest_null_distribution_exists": self._distribution_exists(benchmark_dir, "honest_null", "report.json"),
            "expanded_collusive_alternative_distribution_exists": self._distribution_exists(
                benchmark_dir,
                "collusive_alternatives",
                "report.json",
            ),
            "pilot_trace_dataset_exists": dataset is not None,
            "required_baselines_calibrated_and_run": not baseline_blockers,
            "pilot_manifest_exists": manifest is not None,
            "pilot_run_executed": execution is not None and execution.status == "complete",
            "pilot_result_artifacts_parsed": self._pilot_result_artifacts_parsed(execution),
            "pilot_analysis_generated": analysis is not None and self._analysis_outputs_exist(analysis),
            "prior_work_recall_attached": self._path_exists(benchmark_dir, "related_work/selected_prior_work_recall.json"),
            "related_work_matrix_attached": self._path_exists(benchmark_dir, "related_work/selected_related_work_matrix.json"),
            "pilot_reviewer_panel_generated": self._path_exists(benchmark_dir, "reviews/pilot_review_panel.json"),
            "pilot_manuscript_package_generated": self._pilot_manuscript_package_exists(benchmark_dir),
            "underpowered_alpha_targets_preserved": self._underpowered_alpha_targets_preserved(power_assessment, benchmark_dir),
            "no_alpha_001_claim_unless_powered": not alpha_001_overclaim_paths,
            "no_deployment_validity_claim_from_synthetic_pilot": not deployment_overclaim_paths,
            "no_fake_results_or_citations": not fake_paths and self._related_work_has_no_unknown_citations(benchmark_dir),
        }

        blockers = _requirement_blockers(requirements)
        if not v21_result.passed:
            blockers.extend(f"v2.1 gate blocker: {blocker}" for blocker in v21_result.blockers)
        blockers.extend(f"Pilot baseline blocker: {blocker}" for blocker in baseline_blockers)
        blockers.extend(f"Fake result/citation marker found in {path}" for path in fake_paths)
        blockers.extend(f"Deployment-validity overclaim found in {path}" for path in deployment_overclaim_paths)
        blockers.extend(f"alpha=0.001 overclaim found in {path}" for path in alpha_001_overclaim_paths)
        warnings = self._warnings(power_assessment)
        passed = all(requirements.values())
        return V22ReleaseGateResult(
            passed=passed,
            status="pass" if passed else "fail",
            recommended_next_version="v2.2" if passed else "v2.2-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            project_id=project_id,
            benchmark_id=benchmark_id,
            pilot_dataset_id=dataset.id if dataset else "",
            pilot_manifest_id=manifest.id if manifest else "",
            pilot_execution_id=execution.id if execution else "",
            artifact_paths=self._artifact_paths(v21_result, project_root, benchmark_dir, dataset, manifest, execution, analysis),
        )

    def write_outputs(self, result: V22ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v22_release_gate_latest.json"
        data_md_path = self.release_dir / "v22-release-gate-latest.md"
        report = render_v22_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v22-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _v21_result(self) -> V21ReleaseGateResult:
        return V21ReleaseGateEnforcer(self.config).evaluate()

    def _project_root(self, project_id: str) -> Path:
        return Path(self.projects.load_project(project_id).project.root_dir)

    def _load_spec(self, benchmark_id: str) -> SequentialSpecificityBenchmarkSpec | None:
        try:
            return self.benchmark_manager.load_spec(benchmark_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _latest_pilot_dataset(self, benchmark_dir: Path | None, benchmark_id: str) -> PilotTraceDataset | None:
        if benchmark_dir is None:
            return None
        root = benchmark_dir / "pilot_dataset"
        candidates = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            try:
                dataset = from_dict(PilotTraceDataset, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if dataset.benchmark_id == benchmark_id and dataset.split == "pilot":
                return dataset
        return None

    def _latest_pilot_manifest(
        self,
        benchmark_dir: Path | None,
        benchmark_id: str,
        dataset_id: str,
    ) -> SelectedPilotRunManifest | None:
        candidates: list[Path] = []
        for root_dir in self._candidate_benchmark_dirs(benchmark_dir):
            candidates.extend((root_dir / "pilot_runs" / "manifests").glob("*.json"))
        candidates = sorted(candidates, key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            try:
                manifest = from_dict(SelectedPilotRunManifest, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            manifest_matches = (
                manifest.benchmark_id == benchmark_id
                and manifest.run_type == "pilot"
                and (not dataset_id or manifest.dataset_id == dataset_id)
            )
            if manifest_matches:
                return manifest
        return None

    def _latest_pilot_execution(
        self,
        benchmark_dir: Path | None,
        benchmark_id: str,
        manifest_id: str,
    ) -> SelectedPilotExecution | None:
        candidates: list[Path] = []
        for root_dir in self._candidate_benchmark_dirs(benchmark_dir):
            candidates.extend((root_dir / "pilot_runs" / "executions").glob("*/execution.json"))
        candidates = sorted(candidates, key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            try:
                execution = from_dict(SelectedPilotExecution, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            execution_matches = (
                execution.benchmark_id == benchmark_id
                and execution.run_type == "pilot"
                and (not manifest_id or execution.manifest_id == manifest_id)
            )
            if execution_matches:
                return execution
        return None

    def _candidate_benchmark_dirs(self, primary: Path | None) -> list[Path]:
        dirs: list[Path] = []
        if primary is not None:
            dirs.append(primary)
        for project in self.projects.list_projects():
            path = Path(project.root_dir) / "selected_benchmark"
            if path.exists() and path not in dirs:
                dirs.append(path)
        return dirs

    def _latest_pilot_analysis(
        self,
        benchmark_dir: Path | None,
        benchmark_id: str,
        execution_id: str,
    ) -> PilotAnalysisResult | None:
        if benchmark_dir is None:
            return None
        root = benchmark_dir / "pilot_analysis"
        candidates = sorted(root.glob("*/analysis_result.json"), key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            try:
                analysis = from_dict(PilotAnalysisResult, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if analysis.benchmark_id == benchmark_id and (not execution_id or analysis.execution_id == execution_id):
                return analysis
        return None

    def _latest_power_assessment(
        self,
        benchmark_dir: Path | None,
        benchmark_id: str,
        dataset_id: str,
    ) -> PilotPowerAssessment | None:
        if benchmark_dir is None:
            return None
        root = benchmark_dir / "pilot_power"
        candidates = sorted(root.glob("pilot-power-assessment-*.json"), key=lambda path: path.stat().st_mtime)
        for path in reversed(candidates):
            try:
                assessment = from_dict(PilotPowerAssessment, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if assessment.benchmark_id == benchmark_id and (not dataset_id or assessment.dataset_id == dataset_id):
                return assessment
        return None

    def _baseline_blockers(self, benchmark_id: str) -> list[str]:
        try:
            return self.baseline_manager.pilot_readiness_blockers(benchmark_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return [f"Could not inspect pilot baseline readiness: {exc}"]

    def _pilot_result_artifacts_parsed(self, execution: SelectedPilotExecution | None) -> bool:
        if execution is None or execution.status != "complete":
            return False
        for key in REQUIRED_OUTPUT_KEYS:
            path_text = execution.output_paths.get(key)
            if not path_text:
                return False
            path = Path(path_text)
            if not path.exists():
                return False
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
        return True

    def _analysis_outputs_exist(self, analysis: PilotAnalysisResult) -> bool:
        required = [
            "pilot_metrics_json",
            "pilot_metrics_md",
            "pilot_baseline_comparison_json",
            "pilot_baseline_comparison_md",
            "pilot_error_analysis_json",
            "pilot_error_analysis_md",
            "pilot_low_fpr_report_json",
            "pilot_low_fpr_report_md",
            "pilot_limitations_md",
        ]
        return all(key in analysis.output_paths and Path(analysis.output_paths[key]).exists() for key in required)

    def _underpowered_alpha_targets_preserved(
        self,
        assessment: PilotPowerAssessment | None,
        benchmark_dir: Path | None,
    ) -> bool:
        if assessment is None:
            return False
        if not assessment.alpha_targets_underpowered:
            return True
        paths: list[Path] = []
        if benchmark_dir is not None:
            paths.extend((benchmark_dir / "pilot_power").glob("*.md"))
            paths.extend(
                [
                    benchmark_dir / "reviews" / "pilot_review_panel.md",
                    benchmark_dir / "pilot_manuscript" / "selected_pilot_manuscript.md",
                    benchmark_dir / "pilot_paper_package" / "selected_pilot_manuscript.md",
                ]
            )
        text = self._joined_text(paths).lower()
        for alpha in assessment.alpha_targets_underpowered:
            if f"alpha={alpha}" not in text:
                return False
            if not any(marker in text for marker in ["underpowered", "blocked", "main-scale"]):
                return False
        return True

    def _pilot_manuscript_package_exists(self, benchmark_dir: Path | None) -> bool:
        return bool(
            benchmark_dir
            and (benchmark_dir / "pilot_manuscript" / "selected_pilot_manuscript.json").exists()
            and (benchmark_dir / "pilot_paper_package" / "pilot_paper_package.json").exists()
            and (benchmark_dir / "pilot_paper_package" / "selected_pilot_manuscript.md").exists()
        )

    def _related_work_has_no_unknown_citations(self, benchmark_dir: Path | None) -> bool:
        if benchmark_dir is None:
            return False
        for path in [
            benchmark_dir / "related_work" / "selected_prior_work_recall.md",
            benchmark_dir / "related_work" / "selected_related_work_matrix.md",
            benchmark_dir / "pilot_paper_package" / "selected_related_work_matrix.md",
        ]:
            if path.exists() and "UNKNOWN PAPER" in path.read_text(encoding="utf-8", errors="ignore"):
                return False
        return True

    def _distribution_exists(self, benchmark_dir: Path | None, directory_name: str, file_name: str) -> bool:
        return bool(
            benchmark_dir
            and (benchmark_dir / directory_name / "scenarios.json").exists()
            and (benchmark_dir / directory_name / file_name).exists()
        )

    def _path_exists(self, benchmark_dir: Path | None, relative: str) -> bool:
        return bool(benchmark_dir and (benchmark_dir / relative).exists())

    def _claim_scan_paths(self, benchmark_dir: Path | None) -> list[Path]:
        roots = []
        if benchmark_dir is not None:
            roots.extend(
                [
                    benchmark_dir / "pilot_power",
                    benchmark_dir / "pilot_dataset",
                    benchmark_dir / "honest_null",
                    benchmark_dir / "collusive_alternatives",
                    benchmark_dir / "pilot_runs",
                    benchmark_dir / "pilot_analysis",
                    benchmark_dir / "related_work",
                    benchmark_dir / "reviews",
                    benchmark_dir / "pilot_manuscript",
                    benchmark_dir / "pilot_paper_package",
                ]
            )
        paths: list[Path] = []
        for root in roots:
            if root.exists():
                paths.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".json", ".md", ".txt"})
        return sorted(set(paths))

    def _paths_with_disallowed_text(self, paths: list[Path], predicate: Callable[[str], bool]) -> list[str]:
        matches: list[str] = []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if predicate(text):
                matches.append(str(path))
        return matches

    def _joined_text(self, paths: Iterable[Path]) -> str:
        texts = []
        for path in paths:
            if path.exists() and path.is_file():
                texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        return "\n".join(texts)

    def _warnings(self, assessment: PilotPowerAssessment | None) -> list[str]:
        warnings = [
            "v2.2 is a pilot benchmark release gate; it does not imply deployment validity or publication readiness.",
        ]
        if assessment and assessment.alpha_targets_underpowered:
            for alpha, payload in assessment.alpha_targets_underpowered.items():
                warnings.append(
                    f"alpha={alpha} remains blocked/underpowered: "
                    f"{payload['observed_negative_count']} observed / {payload['required_negative_count']} required."
                )
        return warnings

    def _artifact_paths(
        self,
        v21_result: V21ReleaseGateResult,
        project_root: Path | None,
        benchmark_dir: Path | None,
        dataset: PilotTraceDataset | None,
        manifest: SelectedPilotRunManifest | None,
        execution: SelectedPilotExecution | None,
        analysis: PilotAnalysisResult | None,
    ) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {
            "v21_release_gate": [str(self.release_dir / "v21_release_gate_latest.json")],
            "v21_artifacts": [item for values in v21_result.artifact_paths.values() for item in values],
        }
        if project_root is not None:
            paths["selected_project"] = [str(project_root / "ideas" / "selected_idea_project.json")]
        if benchmark_dir is not None:
            paths["pilot_inputs"] = [
                str(benchmark_dir / "pilot_power" / "pilot_power_plan.json"),
                str(benchmark_dir / "honest_null" / "report.json"),
                str(benchmark_dir / "collusive_alternatives" / "report.json"),
                str(benchmark_dir / "related_work" / "selected_prior_work_recall.json"),
                str(benchmark_dir / "related_work" / "selected_related_work_matrix.json"),
                str(benchmark_dir / "reviews" / "pilot_review_panel.json"),
                str(benchmark_dir / "pilot_paper_package" / "pilot_paper_package.json"),
            ]
        if dataset is not None:
            paths["pilot_dataset"] = [str(benchmark_dir / "pilot_dataset" / f"{dataset.id}.json")] if benchmark_dir else []
        if manifest is not None:
            paths["pilot_manifest"] = [str(benchmark_dir / "pilot_runs" / "manifests" / f"{manifest.id}.json")] if benchmark_dir else []
        if execution is not None:
            paths["pilot_execution"] = [str(Path(path)) for path in execution.output_paths.values()]
        if analysis is not None:
            paths["pilot_analysis"] = [str(Path(path)) for path in analysis.output_paths.values()]
        return paths


def render_v22_release_gate_markdown(result: V22ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.2 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Selected project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Pilot dataset: `{result.pilot_dataset_id or 'missing'}`",
        f"- Pilot manifest: `{result.pilot_manifest_id or 'missing'}`",
        f"- Pilot execution: `{result.pilot_execution_id or 'missing'}`",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- v2.2 requires actual selected-benchmark pilot artifacts, not only smoke evidence.",
            "- Low-FPR alpha claims are power-gated; alpha=0.001 stays blocked unless the negative count supports it.",
            "- Synthetic pilot data is not deployment-validity evidence.",
            "- Reviewer blockers and pilot limitations remain part of the release evidence.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [f"`{name}` is required for the v2.2 pilot benchmark release gate." for name, passed in requirements.items() if not passed]


def _has_fake_result_or_citation_marker(text: str) -> bool:
    lowered = _strip_allowed_claim_boundary_text(text.lower())
    return bool(
        re.search(r"\bfake result\b", lowered)
        or re.search(r"\bfaked result\b", lowered)
        or re.search(r"\bfabricated result\b", lowered)
        or re.search(r"\bplaceholder result\b", lowered)
        or re.search(r"\bfake citation\b", lowered)
        or re.search(r"\bfabricated citation\b", lowered)
        or re.search(r"\bpaper-fake\b", lowered)
    )


def _has_alpha_001_overclaim(text: str) -> bool:
    lowered = text.lower()
    if "alpha=0.001" not in lowered and "alpha 0.001" not in lowered:
        return False
    allowed_markers = ["blocked", "underpowered", "main-scale", "unless powered", "unless the negative count supports"]
    if any(marker in lowered for marker in allowed_markers):
        return False
    patterns = [
        r"alpha[= ]0\.001[^.\n]*(validates|validated|supports|supported|proves|proven|passes|achieved)",
        r"(validates|validated|supports|supported|proves|proven|passes|achieved)[^.\n]*alpha[= ]0\.001",
        r"alpha[= ]0\.001 operational specificity",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _has_synthetic_deployment_overclaim(text: str) -> bool:
    lowered = text.lower()
    if any(
        allowed in lowered
        for allowed in [
            "does not claim deployment validity",
            "do not claim deployment validity",
            "not deployment evidence",
            "not deployment-validity evidence",
            "before any field-validity claim",
        ]
    ):
        return False
    patterns = [
        r"synthetic[^.\n]*(establishes|established|validates|validated|proves|proven|confirms|confirmed)[^.\n]*deployment validity",
        r"deployment validity[^.\n]*(established|validated|proven|confirmed)[^.\n]*synthetic",
        r"valid for production deployment",
        r"synthetic traces represent real deployment",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _strip_allowed_claim_boundary_text(text: str) -> str:
    for phrase in [
        "no fake results",
        "no fake citations",
        "no fake results/citations",
        "no_fake_results_or_citations",
        "fake citation rejected",
        "fake-result marker",
    ]:
        text = text.replace(phrase, "")
    return text


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
