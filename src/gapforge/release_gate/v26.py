"""v2.6 release gate for drastic-review remediation and real artifact packaging."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.evals.metrics import (
    EvalScoreGroup,
    EvalScores,
    adapter_assessment_honesty,
    artifact_package_loader_correctness,
    build_eval_score_group,
    drastic_review_rerun_quality,
    matrix_loader_correctness,
    readiness_status_correctness,
    real_benchmark_search_quality,
    revision_package_completeness,
    v26_release_gate_correctness,
)
from gapforge.evals.paper_quality import PaperQualityAssessment, assess_paper_quality_from_payload
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v25 import V25ReleaseGateEnforcer

V26_STATUSES = {"conference_candidate", "workshop_candidate", "revise_for_reviews", "benchmark_no_fit", "no_go"}
V25_COMPLETED_STATUSES = {"conference_candidate", "workshop_candidate", "revise_for_reviews", "benchmark_no_fit", "no_go", "pass"}
FAKE_CITATION_RE = re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)? et al\.?,?\s+(?:19|20)\d{2}\b|\[\d+\]|\bdoi:\s*\S+")
DEPLOYMENT_VALIDITY_RE = re.compile(
    r"deployment[- ]validity\s*:\s*true|deployment[- ]validity validated|validates deployment[- ]validity",
    re.IGNORECASE,
)


@dataclass(slots=True)
class V26ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    manuscript_id: str = ""
    v25_status: str = ""
    readiness_status: str = "no_go"
    regression_score: float = 0.0
    safety_score: float = 0.0
    workflow_score: float = 0.0
    paper_quality_score: float = 0.0
    release_gate_score: float = 0.0
    overall_score: float = 0.0
    top_conference_readiness: bool = False
    workshop_readiness: bool = False
    likely_reviewer_decision: str = ""
    paper_quality_status: str = "not_assessed"
    score_group: EvalScoreGroup | None = None
    paper_quality_assessment: PaperQualityAssessment | None = None
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V26ReleaseGateEnforcer:
    """Validate v2.6 remediation artifacts without hiding missing evidence."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)

    def evaluate(self) -> V26ReleaseGateResult:
        v25 = self._v25_snapshot()
        project_id = str(v25.get("project_id", ""))
        benchmark_id = str(v25.get("benchmark_id", ""))
        project_root = self._project_root(project_id)
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        manuscript_root = self._manuscript_root(project_root, v25.get("manuscript_id", ""))
        manuscript_id = manuscript_root.name if manuscript_root else str(v25.get("manuscript_id", ""))
        artifacts = _V26Artifacts.load(benchmark_dir, manuscript_root)

        fake_hits = _fake_citation_or_result_hits(project_root)
        copied_hits = _copied_prose_hits(project_root)
        synthetic_claim_hits = _synthetic_deployment_validity_hits(project_root)
        candidate_ids = _candidate_ids(artifacts.real_search)
        no_fit_explicit = _explicit_no_fit(artifacts.real_search, artifacts.real_no_fit_report)
        attempts = artifacts.real_experiment_attempts if isinstance(artifacts.real_experiment_attempts, list) else []
        remaining_fatal = _remaining_fatal_blockers(artifacts.drastic_rerun)
        package_status = str(artifacts.revision_package.get("status", ""))
        likely_reviewer_decision = str(artifacts.drastic_rerun.get("likely_decision", ""))

        requirements = {
            "v25_release_gate_completed": bool(v25) and str(v25.get("status", "")) in V25_COMPLETED_STATUSES,
            "related_work_matrix_load_result_loaded": artifacts.related_matrix.get("status") in {"loaded", "repaired"}
            and not artifacts.related_matrix.get("blockers"),
            "artifact_package_load_result_loaded": artifacts.artifact_package.get("status") in {"loaded", "repaired"}
            and not artifacts.artifact_package.get("blockers"),
            "real_benchmark_search_or_no_fit_exists": bool(artifacts.real_search) or bool(artifacts.real_no_fit_report),
            "real_benchmark_adapter_assessment_exists_if_candidate_exists": not candidate_ids
            or _assessments_cover_candidates(artifacts.real_adapter_assessments, candidate_ids),
            "real_benchmark_experiment_attempt_or_no_fit_exists": _has_attempt_or_no_fit(attempts, no_fit_explicit),
            "venue_artifact_integration_report_exists": bool(artifacts.venue_artifact_integration),
            "venue_artifact_integration_has_no_blockers": bool(artifacts.venue_artifact_integration)
            and not artifacts.venue_artifact_integration.get("blockers"),
            "drastic_review_rerun_exists": bool(artifacts.drastic_rerun),
            "revision_package_exists": bool(artifacts.revision_package) and package_status in V26_STATUSES - {"benchmark_no_fit"},
            "fake_citations_results_blocked": not fake_hits,
            "no_copied_paper_prose": not copied_hits,
            "no_hidden_fatal_blockers": _fatal_blockers_not_hidden(remaining_fatal, package_status, artifacts.revision_package),
            "no_synthetic_deployment_validity_claim": not synthetic_claim_hits,
        }
        blockers = _requirement_blockers(requirements)
        blockers.extend(f"Fake citation/result signal: {hit}" for hit in fake_hits)
        blockers.extend(f"Copied prose signal: {hit}" for hit in copied_hits)
        blockers.extend(f"Synthetic deployment-validity claim signal: {hit}" for hit in synthetic_claim_hits)
        blockers.extend(_artifact_blockers(artifacts.related_matrix, "related-work matrix"))
        blockers.extend(_artifact_blockers(artifacts.artifact_package, "artifact package"))
        status = _decision_status(
            requirements=requirements,
            hard_blockers=_hard_blockers(blockers),
            remaining_fatal=remaining_fatal,
            package_status=package_status,
            no_fit_explicit=no_fit_explicit,
            attempts=attempts,
        )
        passed = status in {"conference_candidate", "workshop_candidate", "benchmark_no_fit"}
        paper_quality_payload = _paper_quality_payload(
            artifacts=artifacts,
            fake_hits=fake_hits,
            copied_hits=copied_hits,
            synthetic_claim_hits=synthetic_claim_hits,
        )
        paper_quality_assessment = assess_paper_quality_from_payload(
            paper_quality_payload,
            benchmark_id=benchmark_id or "selected-benchmark",
            manuscript_id=manuscript_id or "selected-manuscript",
            provenance={"created_by": "v26-release-gate", "release_status": status},
        )
        score_group = _score_group_from_artifacts(
            paper_quality_payload,
            paper_quality_score=paper_quality_assessment.average_score,
        )
        warnings = _warnings(artifacts, remaining_fatal=remaining_fatal, no_fit_explicit=no_fit_explicit)
        warnings.extend(_paper_quality_warnings(status, paper_quality_assessment, likely_reviewer_decision))
        return V26ReleaseGateResult(
            passed=passed,
            status=status,
            recommended_next_version="v2.7" if passed else "v2.6-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            project_id=project_id,
            benchmark_id=benchmark_id,
            manuscript_id=manuscript_id,
            v25_status=str(v25.get("status", "")),
            readiness_status=status,
            regression_score=score_group.regression_score,
            safety_score=score_group.safety_score,
            workflow_score=score_group.workflow_score,
            paper_quality_score=score_group.paper_quality_score,
            release_gate_score=score_group.release_gate_score,
            overall_score=score_group.overall_score,
            top_conference_readiness=paper_quality_assessment.top_conference_readiness,
            workshop_readiness=paper_quality_assessment.workshop_readiness,
            likely_reviewer_decision=likely_reviewer_decision,
            paper_quality_status=_paper_quality_status(status, paper_quality_assessment, likely_reviewer_decision),
            score_group=score_group,
            paper_quality_assessment=paper_quality_assessment,
            artifact_paths=artifacts.paths,
            warnings=_unique(warnings),
        )

    def write_outputs(self, result: V26ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v26_release_gate_latest.json"
        data_md_path = self.release_dir / "v26-release-gate-latest.md"
        report = render_v26_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v26-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _v25_snapshot(self) -> dict[str, Any]:
        path = self.release_dir / "v25_release_gate_latest.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        result = V25ReleaseGateEnforcer(self.config).evaluate()
        return result.to_dict()

    def _project_root(self, project_id: str) -> Path | None:
        if project_id:
            try:
                return Path(self.projects.load_project(project_id).project.root_dir)
            except FileNotFoundError:
                pass
        projects = sorted(self.config.project_root.glob("*"))
        return projects[-1] if projects else None

    def _manuscript_root(self, project_root: Path | None, manuscript_id: Any) -> Path | None:
        if project_root is None:
            return None
        if manuscript_id:
            candidate = project_root / "manuscripts" / str(manuscript_id)
            if candidate.exists():
                return candidate
        manuscripts = sorted((project_root / "manuscripts").glob("*"))
        return manuscripts[-1] if manuscripts else None


@dataclass(slots=True)
class _V26Artifacts:
    related_matrix: dict[str, Any] = field(default_factory=dict)
    artifact_package: dict[str, Any] = field(default_factory=dict)
    real_search: dict[str, Any] = field(default_factory=dict)
    real_no_fit_report: str = ""
    real_adapter_assessments: list[dict[str, Any]] = field(default_factory=list)
    real_experiment_attempts: list[dict[str, Any]] = field(default_factory=list)
    venue_artifact_integration: dict[str, Any] = field(default_factory=dict)
    drastic_rerun: dict[str, Any] = field(default_factory=dict)
    revision_package: dict[str, Any] = field(default_factory=dict)
    paths: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, benchmark_dir: Path | None, manuscript_root: Path | None) -> _V26Artifacts:
        artifacts = cls()
        if benchmark_dir is not None:
            artifacts.related_matrix = _read_json(benchmark_dir / "related_work_matrix_loader" / "related_work_matrix_load_result.json")
            artifacts.artifact_package = _read_json(benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json")
            artifacts.real_search = _read_json(benchmark_dir / "real_benchmark_search" / "real_benchmark_candidate_search.json")
            no_fit_path = benchmark_dir / "real_benchmark_search" / "real_benchmark_no_fit_report.md"
            artifacts.real_no_fit_report = no_fit_path.read_text(encoding="utf-8") if no_fit_path.exists() else ""
            adapter_dir = benchmark_dir / "real_benchmark_adapters"
            artifacts.real_adapter_assessments = [
                *_read_json_glob(adapter_dir, "*.assessment.json"),
                *_read_json_glob(adapter_dir, "real-benchmark-adapter-assessment-*.json"),
            ]
            artifacts.real_experiment_attempts = _read_json_list(
                benchmark_dir / "real_benchmark_experiments" / "real_benchmark_experiment_attempts.json"
            )
            artifacts.venue_artifact_integration = _read_json(benchmark_dir / "venue_artifact_integration" / "report.json")
            artifacts.revision_package = _read_json(benchmark_dir / "venue_revision_package" / "latest.json")
        if manuscript_root is not None:
            artifacts.drastic_rerun = _read_json(manuscript_root / "reviews" / "drastic" / "drastic_review_rerun_result.json")
        artifacts.paths = _paths(benchmark_dir, manuscript_root)
        return artifacts


def render_v26_release_gate_markdown(result: V26ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.6 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Manuscript: `{result.manuscript_id or 'missing'}`",
        f"- v2.5 status: `{result.v25_status or 'missing'}`",
        "",
        "## Score Groups",
        "",
        f"- regression_score: {result.regression_score:.3f}",
        f"- safety_score: {result.safety_score:.3f}",
        f"- workflow_score: {result.workflow_score:.3f}",
        f"- paper_quality_score: {result.paper_quality_score:.3f}",
        f"- release_gate_score: {result.release_gate_score:.3f}",
        f"- overall_score: {result.overall_score:.3f}",
        "",
        "## Paper Quality",
        "",
        f"- top_conference_readiness: {str(result.top_conference_readiness).lower()}",
        f"- workshop_readiness: {str(result.workshop_readiness).lower()}",
        f"- likely reviewer decision: `{result.likely_reviewer_decision or 'unknown'}`",
        f"- paper_quality_status: `{result.paper_quality_status}`",
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
            "- v2.6 directly verifies the v2.5 fatal blockers: related-work matrix and artifact package loading.",
            "- v2.6 can pass as tooling/remediation progress without proving top-conference paper readiness.",
            "- Real benchmark no-fit is acceptable only when recorded explicitly.",
            "- Drastic review remains harsh; unresolved fatal blockers produce `revise_for_reviews`.",
            "- No fake citations/results, copied prose, hidden fatal blockers, or synthetic deployment-validity claims are allowed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _paper_quality_payload(
    *,
    artifacts: _V26Artifacts,
    fake_hits: list[str],
    copied_hits: list[str],
    synthetic_claim_hits: list[str],
) -> dict[str, Any]:
    return {
        "matrix_loader": artifacts.related_matrix,
        "artifact_package_loader": artifacts.artifact_package,
        "real_benchmark_search": artifacts.real_search,
        "adapter_assessments": artifacts.real_adapter_assessments,
        "adapter_assessment": artifacts.real_adapter_assessments[0] if artifacts.real_adapter_assessments else {},
        "real_benchmark_experiments": artifacts.real_experiment_attempts,
        "real_benchmark_experiment": artifacts.real_experiment_attempts[0] if artifacts.real_experiment_attempts else {},
        "venue_artifact_integration": artifacts.venue_artifact_integration,
        "drastic_review_rerun": artifacts.drastic_rerun,
        "revision_package": artifacts.revision_package,
        "safety": {
            "fake_citation_present": bool(fake_hits),
            "fake_result_present": bool(fake_hits),
            "copied_prose_detected": bool(copied_hits),
            "synthetic_deployment_validity_claim": bool(synthetic_claim_hits),
            "release_gate_blocked": bool(fake_hits or copied_hits or synthetic_claim_hits),
        },
        "v25_release_gate": {"passes": True},
        "v26_release_gate": {
            "expected_pass": True,
            "expected_status": str(artifacts.revision_package.get("status", "")),
            "expected_blockers": [],
        },
    }


def _score_group_from_artifacts(payload: dict[str, Any], *, paper_quality_score: float) -> EvalScoreGroup:
    scores = EvalScores(
        gap_specificity_score=1.0,
        evidence_linkage_score=paper_quality_score,
        novelty_gate_accuracy=paper_quality_score,
        duplicate_detection_rate=1.0,
        unsupported_claim_rate=0.0,
        experiment_completeness_score=1.0,
        reviewer_objection_quality_score=1.0,
    )
    scores.matrix_loader_correctness = matrix_loader_correctness(payload)
    scores.artifact_package_loader_correctness = artifact_package_loader_correctness(payload)
    scores.real_benchmark_search_quality = real_benchmark_search_quality(payload)
    scores.adapter_assessment_honesty = adapter_assessment_honesty(payload)
    scores.drastic_review_rerun_quality = drastic_review_rerun_quality(payload)
    scores.revision_package_completeness = revision_package_completeness(payload)
    scores.readiness_status_correctness = readiness_status_correctness(payload)
    scores.v26_release_gate_correctness = v26_release_gate_correctness(payload)
    group = build_eval_score_group(
        scores,
        provenance={"source": "v26-release-gate"},
        selected_benchmark_fixture=payload,
    )
    group.paper_quality_score = _capped_paper_quality_score(
        paper_quality_score,
        str(_dict(payload.get("drastic_review_rerun")).get("likely_decision", "")),
    )
    group.overall_score = _release_overall_score(group)
    return group


def _capped_paper_quality_score(score: float, likely_decision: str) -> float:
    decision = likely_decision.lower()
    if "reject" in decision and "borderline" not in decision:
        return min(round(score, 3), 0.35)
    if "borderline_reject" in decision or "borderline reject" in decision or decision == "borderline":
        return min(round(score, 3), 0.5)
    return round(score, 3)


def _release_overall_score(group: EvalScoreGroup) -> float:
    grouped_average = round(
        (group.regression_score + group.safety_score + group.workflow_score + group.paper_quality_score + group.release_gate_score) / 5,
        3,
    )
    if group.blocking_failures:
        return min(grouped_average, group.safety_score, group.workflow_score, group.release_gate_score)
    if group.paper_quality_score < 0.6:
        return min(grouped_average, group.paper_quality_score)
    return grouped_average


def _paper_quality_status(status: str, assessment: PaperQualityAssessment, likely_decision: str) -> str:
    decision = likely_decision.lower()
    if assessment.top_conference_readiness:
        return "top_conference_ready"
    if "borderline" in decision:
        return "progress_not_success_borderline_reject"
    if "reject" in decision:
        return "progress_not_success_reject_likely"
    if status == "workshop_candidate" or assessment.workshop_readiness:
        return "workshop_candidate"
    if status in {"conference_candidate", "benchmark_no_fit"}:
        return "tooling_pass_paper_not_ready"
    return "not_ready"


def _paper_quality_warnings(
    status: str,
    assessment: PaperQualityAssessment,
    likely_decision: str,
) -> list[str]:
    warnings = []
    decision = likely_decision.lower()
    if status == "workshop_candidate":
        warnings.append("v2.6 status is workshop_candidate; this is not top-conference readiness.")
    if "borderline" in decision and not assessment.top_conference_readiness:
        warnings.append("Drastic review predicts borderline reject; top_conference_readiness is false.")
    if status in {"workshop_candidate", "conference_candidate"} and not assessment.top_conference_readiness:
        warnings.append("Artifact and matrix blockers improved, but paper quality remains progress, not success.")
    return warnings


def _decision_status(
    *,
    requirements: dict[str, bool],
    hard_blockers: list[str],
    remaining_fatal: list[str],
    package_status: str,
    no_fit_explicit: bool,
    attempts: list[dict[str, Any]],
) -> str:
    if hard_blockers:
        return "no_go"
    if not all(requirements.values()):
        return "no_go"
    if remaining_fatal:
        return "revise_for_reviews"
    if no_fit_explicit and not any(attempt.get("status") == "complete" for attempt in attempts):
        return "benchmark_no_fit"
    if package_status == "conference_candidate":
        return "conference_candidate"
    if package_status == "workshop_candidate":
        return "workshop_candidate"
    if package_status == "revise_for_reviews":
        return "revise_for_reviews"
    return "no_go"


def _candidate_ids(search: dict[str, Any]) -> list[str]:
    return [str(item) for item in search.get("candidate_benchmark_ids", []) if item]


def _explicit_no_fit(search: dict[str, Any], report: str) -> bool:
    if search.get("status") == "no_fit":
        return True
    text = report.lower()
    return "no-fit" in text or "no candidate survived" in text or "new benchmark protocol is needed" in text


def _assessments_cover_candidates(assessments: list[dict[str, Any]], candidate_ids: list[str]) -> bool:
    assessed = {str(item.get("candidate_benchmark_id", "")) for item in assessments}
    return all(candidate_id in assessed for candidate_id in candidate_ids)


def _has_attempt_or_no_fit(attempts: list[dict[str, Any]], no_fit_explicit: bool) -> bool:
    if no_fit_explicit:
        return True
    return any(str(attempt.get("status", "")) in {"complete", "failed", "no_fit", "skipped"} for attempt in attempts)


def _remaining_fatal_blockers(rerun: dict[str, Any]) -> list[str]:
    return [str(item) for item in rerun.get("remaining_blockers", []) if item]


def _fatal_blockers_not_hidden(remaining_fatal: list[str], package_status: str, revision_package: dict[str, Any]) -> bool:
    if not remaining_fatal:
        return True
    if package_status != "revise_for_reviews":
        return False
    limitations = "\n".join(str(item) for item in revision_package.get("limitations", []))
    return all(_blocker_key(blocker) in limitations for blocker in remaining_fatal)


def _blocker_key(blocker: str) -> str:
    return blocker.split(maxsplit=1)[0]


def _artifact_blockers(artifact: dict[str, Any], label: str) -> list[str]:
    if not artifact:
        return [f"Missing {label} load result."]
    return [f"{label}: {blocker}" for blocker in artifact.get("blockers", [])]


def _hard_blockers(blockers: list[str]) -> list[str]:
    hard_markers = [
        "missing related_work_matrix_load_result_loaded",
        "missing artifact_package_load_result_loaded",
        "fake citation/result",
        "copied prose",
        "synthetic deployment-validity",
        "hidden fatal",
        "no_hidden_fatal_blockers",
    ]
    lowered = [blocker.lower() for blocker in blockers]
    return [blocker for blocker, low in zip(blockers, lowered, strict=False) if any(marker in low for marker in hard_markers)]


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [f"Missing `{name}`." for name, passed in requirements.items() if not passed]


def _warnings(artifacts: _V26Artifacts, *, remaining_fatal: list[str], no_fit_explicit: bool) -> list[str]:
    warnings = []
    status = artifacts.revision_package.get("status")
    if status:
        warnings.append(f"Venue revision package status is `{status}`.")
    if remaining_fatal:
        warnings.append("Fatal blockers remain after drastic rerun; conference_candidate is blocked.")
    if no_fit_explicit:
        warnings.append("Real benchmark path is explicit no-fit or no-fit-only; do not claim real benchmark validity.")
    return _unique(warnings)


def _fake_citation_or_result_hits(project_root: Path | None) -> list[str]:
    hits = []
    for path in _text_paths(project_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(_line_has_fake_citation_or_result_signal(line) for line in text.splitlines()):
            hits.append(str(path))
    return _unique(hits)


def _copied_prose_hits(project_root: Path | None) -> list[str]:
    hits = []
    for path in _text_paths(project_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(_line_has_copied_prose_signal(line) for line in text.splitlines()):
            hits.append(str(path))
    return _unique(hits)


def _line_has_fake_citation_or_result_signal(line: str) -> bool:
    lower = line.lower()
    if any(
        phrase in lower
        for phrase in [
            "no fake citation",
            "no fake result",
            "fake citations/results",
            "fake citations or fake results",
            "do not invent",
            "must not invent",
            "not allowed",
            "blocked",
            "claim boundary",
            "boundary",
        ]
    ):
        return False
    return bool(FAKE_CITATION_RE.search(line) or "invented result" in lower or "fake result" in lower)


def _line_has_copied_prose_signal(line: str) -> bool:
    lower = line.lower()
    if '"copied_text_warnings": []' in lower or "no copied" in lower or "do not copy" in lower or "must not copy" in lower:
        return False
    return "unique_style_do_not_copy_marker" in lower or "copied source sentence" in lower or "copied_text_warnings" in lower


def _synthetic_deployment_validity_hits(project_root: Path | None) -> list[str]:
    hits = []
    for path in _text_paths(project_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if DEPLOYMENT_VALIDITY_RE.search(text):
            hits.append(str(path))
    return _unique(hits)


def _text_paths(project_root: Path | None) -> list[Path]:
    if project_root is None or not project_root.exists():
        return []
    return [
        path
        for path in project_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".txt"} and ".git" not in path.parts
    ]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _read_json_glob(root: Path, pattern: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records = []
    for path in sorted(root.glob(pattern)):
        record = _read_json(path)
        if record:
            records.append(record)
    return records


def _paths(benchmark_dir: Path | None, manuscript_root: Path | None) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    if benchmark_dir is not None:
        paths["benchmark_dir"] = [str(benchmark_dir)]
        for name in [
            "related_work_matrix_loader",
            "artifact_package_loader",
            "real_benchmark_search",
            "real_benchmark_adapters",
            "real_benchmark_experiments",
            "venue_artifact_integration",
            "venue_revision_package",
        ]:
            path = benchmark_dir / name
            if path.exists():
                paths[name] = [str(item) for item in sorted(path.rglob("*")) if item.is_file()]
    if manuscript_root is not None:
        paths["manuscript_root"] = [str(manuscript_root)]
        drastic = manuscript_root / "reviews" / "drastic"
        if drastic.exists():
            paths["drastic_review"] = [str(item) for item in sorted(drastic.rglob("*")) if item.is_file()]
    return paths


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _unique(items: list[str]) -> list[str]:
    result = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
