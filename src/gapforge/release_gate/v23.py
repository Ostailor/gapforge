"""v2.3 release gate for selected-benchmark mature decisions."""

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
from gapforge.release_gate.v22 import V22ReleaseGateEnforcer, V22ReleaseGateResult
from gapforge.selected_benchmark.baselines import BaselineStrengthAssessment
from gapforge.selected_benchmark.go_no_go import SelectedBenchmarkGoNoGo
from gapforge.selected_benchmark.main_analysis import MainAnalysisResult
from gapforge.selected_benchmark.main_dataset import MainTraceDataset
from gapforge.selected_benchmark.main_manuscript import SelectedMainManuscript, SelectedMainPaperPackage
from gapforge.selected_benchmark.main_power import MainPowerDecision, MainPowerPlan
from gapforge.selected_benchmark.main_run import SelectedMainExecution
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisResult
from gapforge.selected_benchmark.related_work_completion import RelatedWorkCompletionStatus
from gapforge.selected_benchmark.reviewer import PublicationReadinessReview

PASSING_DECISION_STATUSES = {"publication_candidate", "workshop_candidate", "revise_benchmark", "no_go"}


@dataclass(slots=True)
class V23ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    decision_status: str = "unknown"
    go_no_go_decision: str = ""
    publication_readiness: str = ""
    manuscript_status: str = ""
    main_power_plan_id: str = ""
    alpha_001_decision_id: str = ""
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V23ReleaseGateEnforcer:
    """Check whether v2.3 reached an honest mature outcome."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)

    def evaluate(self) -> V23ReleaseGateResult:
        v22_result = self._v22_result()
        project_id = v22_result.project_id
        benchmark_id = v22_result.benchmark_id
        project_root = self._project_root(project_id) if project_id else None
        benchmark_dir = project_root / "selected_benchmark" if project_root else None

        benchmark_dirs = self._candidate_benchmark_dirs(benchmark_dir)
        artifacts = _V23Artifacts.load(benchmark_dirs, benchmark_id)
        claim_paths = self._claim_scan_paths(benchmark_dirs)
        alpha_powered = _alpha_001_powered(artifacts.alpha_decision, artifacts.main_analysis)
        deployment_overclaim_paths = self._paths_with_disallowed_text(claim_paths, _has_synthetic_deployment_overclaim)
        alpha_overclaim_paths = [] if alpha_powered else self._paths_with_disallowed_text(claim_paths, _has_alpha_001_overclaim)
        decision_status = _decision_status(artifacts)
        missing_related_hidden = _missing_related_work_hidden(artifacts)
        missing_baseline_hidden = _missing_baselines_hidden(artifacts)
        evidence_mislabeled = _evidence_mislabeled(artifacts, decision_status=decision_status, alpha_powered=alpha_powered)

        main_run_or_pilot_decision = artifacts.main_execution is not None or _explicit_pilot_only_decision(artifacts)
        analysis_exists = artifacts.main_analysis is not None or artifacts.pilot_analysis is not None
        manuscript_package_exists = artifacts.main_manuscript is not None and artifacts.main_paper_package is not None

        requirements = {
            "v22_release_gate_passes": v22_result.passed,
            "main_power_plan_exists": artifacts.main_power_plan is not None,
            "main_alpha_001_decision_exists": artifacts.alpha_decision is not None,
            "related_work_completion_status_exists": artifacts.related_work is not None,
            "baseline_strength_assessment_exists": artifacts.baseline_strength is not None,
            "main_dataset_or_feasibility_report_exists": artifacts.main_dataset is not None,
            "main_run_or_explicit_pilot_only_decision_exists": main_run_or_pilot_decision,
            "main_or_pilot_analysis_exists": analysis_exists,
            "go_no_go_decision_exists": artifacts.go_no_go is not None,
            "publication_readiness_review_exists": artifacts.publication_review is not None,
            "manuscript_package_exists": manuscript_package_exists,
            "mature_decision_exists": decision_status in PASSING_DECISION_STATUSES,
            "no_synthetic_deployment_validity_overclaim": not deployment_overclaim_paths,
            "no_alpha_overclaim": not alpha_overclaim_paths,
            "no_missing_real_related_work_hidden": not missing_related_hidden,
            "no_missing_required_baseline_hidden": not missing_baseline_hidden,
            "evidence_is_not_mislabeled": not evidence_mislabeled,
        }

        blockers = _requirement_blockers(requirements)
        if not v22_result.passed:
            blockers.extend(f"v2.2 gate blocker: {blocker}" for blocker in v22_result.blockers)
        blockers.extend(f"Deployment-validity overclaim found in {path}" for path in deployment_overclaim_paths)
        blockers.extend(f"alpha=0.001 overclaim found in {path}" for path in alpha_overclaim_paths)
        if missing_related_hidden:
            blockers.append("Missing real related work coverage is hidden by publication/review/manuscript labels.")
        if missing_baseline_hidden:
            blockers.append("Missing required baseline coverage is hidden by publication/review/manuscript labels.")
        if evidence_mislabeled:
            blockers.append("v2.3 evidence is mislabeled relative to blockers, readiness, or go/no-go status.")

        warnings = _warnings(artifacts, decision_status=decision_status)
        passed = all(requirements.values())
        return V23ReleaseGateResult(
            passed=passed,
            status="pass" if passed else "fail",
            recommended_next_version="v2.3" if passed else "v2.3-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            project_id=project_id,
            benchmark_id=benchmark_id,
            decision_status=decision_status,
            go_no_go_decision=artifacts.go_no_go.decision if artifacts.go_no_go else "",
            publication_readiness=artifacts.publication_review.readiness if artifacts.publication_review else "",
            manuscript_status=artifacts.main_manuscript.status if artifacts.main_manuscript else "",
            main_power_plan_id=artifacts.main_power_plan.id if artifacts.main_power_plan else "",
            alpha_001_decision_id=artifacts.alpha_decision.id if artifacts.alpha_decision else "",
            artifact_paths=self._artifact_paths(v22_result, benchmark_dir, artifacts),
        )

    def write_outputs(self, result: V23ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v23_release_gate_latest.json"
        data_md_path = self.release_dir / "v23-release-gate-latest.md"
        report = render_v23_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v23-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _v22_result(self) -> V22ReleaseGateResult:
        return V22ReleaseGateEnforcer(self.config).evaluate()

    def _project_root(self, project_id: str) -> Path:
        return Path(self.projects.load_project(project_id).project.root_dir)

    def _candidate_benchmark_dirs(self, primary: Path | None) -> list[Path]:
        dirs: list[Path] = []
        if primary is not None:
            dirs.append(primary)
        for project in self.projects.list_projects():
            path = Path(project.root_dir) / "selected_benchmark"
            if path.exists() and path not in dirs:
                dirs.append(path)
        return dirs

    def _claim_scan_paths(self, benchmark_dirs: list[Path]) -> list[Path]:
        roots = [
            root / child
            for root in benchmark_dirs
            for child in [
                "main_power",
                "main_dataset",
                "main_runs",
                "main_analysis",
                "related_work_completion",
                "reviews",
                "go_no_go",
                "main_manuscript",
                "main_paper_package",
            ]
        ]
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

    def _artifact_paths(
        self,
        v22_result: V22ReleaseGateResult,
        benchmark_dir: Path | None,
        artifacts: _V23Artifacts,
    ) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {
            "v22_release_gate": [str(self.release_dir / "v22_release_gate_latest.json")],
            "v22_artifacts": [item for values in v22_result.artifact_paths.values() for item in values],
        }
        if benchmark_dir is None:
            return paths
        candidates = {
            "main_power_plan": benchmark_dir / "main_power" / "main_power_plan.json",
            "related_work_completion": benchmark_dir / "related_work_completion" / "related_work_completion_status.json",
            "baseline_strength": benchmark_dir / "baseline_strength_assessment.json",
            "go_no_go": benchmark_dir / "go_no_go" / "go_no_go.json",
            "publication_review": benchmark_dir / "reviews" / "main_publication_review.json",
            "main_manuscript": benchmark_dir / "main_manuscript" / "selected_main_manuscript.json",
            "main_paper_package": benchmark_dir / "main_paper_package" / "main_paper_package.json",
        }
        for key, path in candidates.items():
            if path.exists():
                paths[key] = [str(path)]
        if artifacts.alpha_decision:
            paths["alpha_decision"] = [str(benchmark_dir / "main_power" / "decisions" / f"{artifacts.alpha_decision.id}.json")]
        if artifacts.main_dataset:
            paths["main_dataset"] = [str(benchmark_dir / "main_dataset" / f"{artifacts.main_dataset.id}.json")]
        return paths


@dataclass(slots=True)
class _V23Artifacts:
    main_power_plan: MainPowerPlan | None = None
    alpha_decision: MainPowerDecision | None = None
    related_work: RelatedWorkCompletionStatus | None = None
    baseline_strength: BaselineStrengthAssessment | None = None
    main_dataset: MainTraceDataset | None = None
    main_execution: SelectedMainExecution | None = None
    main_analysis: MainAnalysisResult | None = None
    pilot_analysis: PilotAnalysisResult | None = None
    go_no_go: SelectedBenchmarkGoNoGo | None = None
    publication_review: PublicationReadinessReview | None = None
    main_manuscript: SelectedMainManuscript | None = None
    main_paper_package: SelectedMainPaperPackage | None = None

    @classmethod
    def load(cls, benchmark_dirs: list[Path], benchmark_id: str) -> _V23Artifacts:
        if not benchmark_dirs:
            return cls()
        primary = benchmark_dirs[0]
        return cls(
            main_power_plan=_read_dataclass(MainPowerPlan, primary / "main_power" / "main_power_plan.json", benchmark_id),
            alpha_decision=_latest_alpha_decision(benchmark_dirs, benchmark_id),
            related_work=_read_dataclass(
                RelatedWorkCompletionStatus,
                primary / "related_work_completion" / "related_work_completion_status.json",
                benchmark_id,
            ),
            baseline_strength=_read_dataclass(
                BaselineStrengthAssessment,
                primary / "baseline_strength_assessment.json",
                benchmark_id,
            ),
            main_dataset=_latest_main_dataset(benchmark_dirs, benchmark_id),
            main_execution=_latest_main_execution(benchmark_dirs, benchmark_id),
            main_analysis=_latest_main_analysis(benchmark_dirs, benchmark_id),
            pilot_analysis=_latest_pilot_analysis(benchmark_dirs, benchmark_id),
            go_no_go=_read_dataclass(SelectedBenchmarkGoNoGo, primary / "go_no_go" / "go_no_go.json", benchmark_id),
            publication_review=_read_dataclass(
                PublicationReadinessReview,
                primary / "reviews" / "main_publication_review.json",
                benchmark_id,
            ),
            main_manuscript=_read_dataclass(
                SelectedMainManuscript,
                primary / "main_manuscript" / "selected_main_manuscript.json",
                benchmark_id,
            ),
            main_paper_package=_read_dataclass(
                SelectedMainPaperPackage,
                primary / "main_paper_package" / "main_paper_package.json",
                benchmark_id,
            ),
        )


def render_v23_release_gate_markdown(result: V23ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.3 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Selected project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Decision status: `{result.decision_status}`",
        f"- Go/no-go decision: `{result.go_no_go_decision or 'missing'}`",
        f"- Publication readiness: `{result.publication_readiness or 'missing'}`",
        f"- Manuscript status: `{result.manuscript_status or 'missing'}`",
        f"- Main power plan: `{result.main_power_plan_id or 'missing'}`",
        f"- alpha=0.001 decision: `{result.alpha_001_decision_id or 'missing'}`",
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
            "- v2.3 requires a mature publication, workshop, revise, or no-go decision.",
            "- Publication-candidate labels require powered main evidence and blocker-free review/go-no-go/manuscript artifacts.",
            "- Workshop, revise, and no-go outcomes may pass only when blockers are visible and claims are not mislabeled.",
            "- Synthetic evidence must not be used to claim deployment validity.",
            "- alpha=0.001 must not be claimed unless powered by the main alpha decision and main analysis.",
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


def _latest_alpha_decision(benchmark_dirs: list[Path], benchmark_id: str) -> MainPowerDecision | None:
    return _latest_dataclass(
        MainPowerDecision,
        [path for root in benchmark_dirs for path in (root / "main_power" / "decisions").glob("main-alpha-decision-*.json")],
        benchmark_id,
        predicate=lambda item: abs(float(item.alpha_level) - 0.001) < 1e-12,
    )


def _latest_main_dataset(benchmark_dirs: list[Path], benchmark_id: str) -> MainTraceDataset | None:
    return _latest_dataclass(
        MainTraceDataset, [path for root in benchmark_dirs for path in (root / "main_dataset").glob("*.json")], benchmark_id
    )


def _latest_main_execution(benchmark_dirs: list[Path], benchmark_id: str) -> SelectedMainExecution | None:
    return _latest_dataclass(
        SelectedMainExecution,
        [path for root in benchmark_dirs for path in (root / "main_runs" / "executions").glob("*/execution.json")],
        benchmark_id,
        predicate=lambda item: item.run_type == "main",
    )


def _latest_main_analysis(benchmark_dirs: list[Path], benchmark_id: str) -> MainAnalysisResult | None:
    return _latest_dataclass(
        MainAnalysisResult,
        [path for root in benchmark_dirs for path in (root / "main_analysis").glob("*/analysis_result.json")],
        benchmark_id,
        predicate=lambda item: item.run_type == "main",
    )


def _latest_pilot_analysis(benchmark_dirs: list[Path], benchmark_id: str) -> PilotAnalysisResult | None:
    return _latest_dataclass(
        PilotAnalysisResult,
        [path for root in benchmark_dirs for path in (root / "pilot_analysis").glob("*/analysis_result.json")],
        benchmark_id,
        predicate=lambda item: item.run_type == "pilot",
    )


def _latest_dataclass(
    model: type[Any],
    paths: list[Path],
    benchmark_id: str,
    *,
    predicate: Callable[[Any], bool] | None = None,
) -> Any | None:
    for path in sorted(paths, key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            value = from_dict(model, json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if getattr(value, "benchmark_id", "") != benchmark_id:
            continue
        if predicate is not None and not predicate(value):
            continue
        return value
    return None


def _alpha_001_powered(decision: MainPowerDecision | None, analysis: MainAnalysisResult | None) -> bool:
    return bool(decision and decision.decision == "power" and analysis and "0.001" in analysis.powered_alpha_levels)


def _explicit_pilot_only_decision(artifacts: _V23Artifacts) -> bool:
    return bool(
        (artifacts.main_manuscript and artifacts.main_manuscript.evidence_maturity == "pilot")
        or (artifacts.publication_review and artifacts.publication_review.readiness == "workshop_candidate")
    )


def _decision_status(artifacts: _V23Artifacts) -> str:
    if artifacts.go_no_go and artifacts.go_no_go.decision == "no_go":
        return "no_go"
    if artifacts.publication_review and artifacts.publication_review.readiness == "no_go":
        return "no_go"
    if artifacts.main_manuscript and artifacts.main_manuscript.status == "no_go":
        return "no_go"
    if _publication_candidate_label_present(artifacts):
        return "publication_candidate"
    if artifacts.main_manuscript and artifacts.main_manuscript.status == "workshop_candidate":
        return "workshop_candidate"
    if artifacts.publication_review and artifacts.publication_review.readiness == "workshop_candidate":
        return "workshop_candidate"
    if artifacts.go_no_go and artifacts.go_no_go.decision == "revise_benchmark":
        return "revise_benchmark"
    return "unknown"


def _publication_candidate_label_present(artifacts: _V23Artifacts) -> bool:
    return bool(
        (artifacts.go_no_go and artifacts.go_no_go.decision == "go_publication_candidate")
        or (artifacts.publication_review and artifacts.publication_review.readiness in {"publication_candidate", "conference_candidate"})
        or (artifacts.main_manuscript and artifacts.main_manuscript.status == "publication_candidate")
    )


def _missing_related_work_hidden(artifacts: _V23Artifacts) -> bool:
    status = artifacts.related_work
    if status is None:
        return False
    missing = bool(status.missing_categories or status.real_paper_count == 0 or status.blockers)
    if not missing:
        return False
    if _publication_candidate_label_present(artifacts):
        return True
    text = _blocker_text(artifacts)
    return "related work" not in text and "prior work" not in text and "real paper" not in text


def _missing_baselines_hidden(artifacts: _V23Artifacts) -> bool:
    assessment = artifacts.baseline_strength
    if assessment is None:
        return False
    missing = bool(assessment.missing_baselines or assessment.blockers)
    if not missing:
        return False
    if _publication_candidate_label_present(artifacts):
        return True
    text = _blocker_text(artifacts)
    return "baseline" not in text and "calibration" not in text


def _evidence_mislabeled(artifacts: _V23Artifacts, *, decision_status: str, alpha_powered: bool) -> bool:
    if decision_status == "publication_candidate":
        return not _publication_candidate_supported(artifacts, alpha_powered=alpha_powered)
    if decision_status == "no_go":
        return _publication_candidate_label_present(artifacts) or not _blocker_text(artifacts)
    if decision_status == "revise_benchmark":
        return _publication_candidate_label_present(artifacts) or not (
            artifacts.go_no_go and artifacts.go_no_go.decision == "revise_benchmark"
        )
    if decision_status == "workshop_candidate":
        return _publication_candidate_label_present(artifacts)
    return False


def _publication_candidate_supported(artifacts: _V23Artifacts, *, alpha_powered: bool) -> bool:
    if artifacts.main_analysis is None or artifacts.main_execution is None:
        return False
    if not alpha_powered:
        return False
    if not (
        artifacts.go_no_go
        and artifacts.go_no_go.decision == "go_publication_candidate"
        and artifacts.publication_review
        and artifacts.publication_review.readiness in {"publication_candidate", "conference_candidate"}
        and artifacts.main_manuscript
        and artifacts.main_manuscript.status == "publication_candidate"
    ):
        return False
    if artifacts.related_work and (artifacts.related_work.missing_categories or artifacts.related_work.real_paper_count == 0):
        return False
    if artifacts.baseline_strength and (artifacts.baseline_strength.missing_baselines or artifacts.baseline_strength.blockers):
        return False
    return not _open_blocker_text(artifacts)


def _blocker_text(artifacts: _V23Artifacts) -> str:
    values: list[str] = []
    if artifacts.publication_review:
        values.extend(artifacts.publication_review.fatal_blockers)
        values.extend(artifacts.publication_review.major_blockers)
        values.extend(artifacts.publication_review.required_revisions)
    if artifacts.go_no_go:
        values.extend(artifacts.go_no_go.blockers)
        values.extend(artifacts.go_no_go.required_next_steps)
    if artifacts.main_manuscript:
        values.extend(artifacts.main_manuscript.fatal_blockers)
        values.extend(artifacts.main_manuscript.major_blockers)
        values.extend(artifacts.main_manuscript.required_revisions)
        values.extend(artifacts.main_manuscript.unresolved_blockers)
    return "\n".join(values).lower()


def _open_blocker_text(artifacts: _V23Artifacts) -> str:
    values: list[str] = []
    if artifacts.publication_review:
        values.extend(artifacts.publication_review.fatal_blockers)
        values.extend(artifacts.publication_review.major_blockers)
        values.extend(artifacts.publication_review.required_revisions)
    if artifacts.go_no_go:
        values.extend(artifacts.go_no_go.blockers)
    if artifacts.main_manuscript:
        values.extend(artifacts.main_manuscript.fatal_blockers)
        values.extend(artifacts.main_manuscript.major_blockers)
        values.extend(artifacts.main_manuscript.required_revisions)
        values.extend(artifacts.main_manuscript.unresolved_blockers)
    return "\n".join(values).lower()


def _has_alpha_001_overclaim(text: str) -> bool:
    lowered = text.lower()
    if "alpha=0.001" not in lowered and "alpha 0.001" not in lowered:
        return False
    safe_context = [
        "blocked",
        "underpowered",
        "unless powered",
        "not claimed",
        "not claim",
        "not powered",
        "dropped",
        "defer",
        "decision is",
        "decision:",
    ]
    patterns = [
        r"alpha[= ]0\.001[^.\n]*(validates|validated|supports|supported|proves|proven|passes|achieved|demonstrates)",
        r"(validates|validated|supports|supported|proves|proven|passes|achieved|demonstrates)[^.\n]*alpha[= ]0\.001",
        r"alpha[= ]0\.001 operational specificity",
    ]
    return _sentence_matches(lowered, patterns, safe_context)


def _has_synthetic_deployment_overclaim(text: str) -> bool:
    lowered = text.lower()
    safe_context = [
        "does not claim deployment validity",
        "do not claim deployment validity",
        "no deployment validity",
        "does not establish deployment validity",
        "does not establish real-world deployment validity",
        "do not establish deployment validity",
        "do not establish real-world deployment validity",
        "do not prove real-world deployment validity",
        "not deployment evidence",
        "not evidence that a deployed monitor",
        "not deployment-validity evidence",
        "deployment-validity claims are blocked",
        "deployment validity is not established",
        "deployment validity is not claimed",
        "cannot establish deployment validity",
        "cannot establish real-world deployment validity",
        "cannot support deployment validity claims",
        "synthetic evidence alone never establishes deployment validity",
        "no synthetic main result establishes deployment validity",
        "cannot support deployment-validity claims",
        "no real-world deployment-validity claim",
        "not real-world deployment-validity claims",
        "do not imply real-world deployment validity",
        "synthetic data does not establish real-world deployment validity",
        "not deployment-validity evidence",
        "must not be interpreted as deployment-validity evidence",
        "must not be read as deployment validity",
        "real-world validity is outside scope",
    ]
    patterns = [
        r"synthetic[^.\n]*(establishes|established|validates|validated|proves|proven|confirms|confirmed|claims)[^.\n]*deployment validity",
        r"deployment validity[^.\n]*(established|validated|proven|confirmed|claimed|claims)[^.\n]*synthetic",
        r"valid for production deployment",
        r"synthetic traces represent real deployment",
        r"claims deployment validity",
    ]
    return _sentence_matches(lowered, patterns, safe_context)


def _sentence_matches(text: str, patterns: list[str], safe_context: list[str]) -> bool:
    for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        if any(marker in sentence for marker in safe_context):
            continue
        if any(re.search(pattern, sentence) for pattern in patterns):
            return True
    return False


def _warnings(artifacts: _V23Artifacts, *, decision_status: str) -> list[str]:
    warnings = ["v2.3 accepts mature honest outcomes; it does not require publication success."]
    if decision_status in {"workshop_candidate", "revise_benchmark", "no_go"}:
        warnings.append(f"v2.3 passed with honest non-publication outcome `{decision_status}`.")
    if artifacts.alpha_decision and artifacts.alpha_decision.decision != "power":
        warnings.append(
            f"alpha=0.001 decision is `{artifacts.alpha_decision.decision}`; claims must use a powered alpha or explicit downgrade."
        )
    if artifacts.related_work and artifacts.related_work.missing_categories:
        warnings.append("Related-work coverage remains incomplete but is visible in v2.3 decision artifacts.")
    if artifacts.baseline_strength and artifacts.baseline_strength.missing_baselines:
        warnings.append("Required baseline coverage remains incomplete but is visible in v2.3 decision artifacts.")
    return warnings


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [f"`{name}` is required for the v2.3 release gate." for name, passed in requirements.items() if not passed]


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
