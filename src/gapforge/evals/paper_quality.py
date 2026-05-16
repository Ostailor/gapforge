"""Paper-quality assessment for selected benchmark manuscripts."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso

FAKE_CITATION_RE = re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)? et al\.?,?\s+(?:19|20)\d{2}\b|\[\d+\]|\bdoi:\s*\S+")
DEPLOYMENT_VALIDITY_RE = re.compile(
    r"deployment[- ]validity\s*:\s*true|deployment[- ]validity validated|validates deployment[- ]validity",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PaperQualityAssessment:
    id: str
    benchmark_id: str
    manuscript_id: str
    novelty_score: float
    related_work_score: float
    benchmark_fit_score: float
    baseline_strength_score: float
    statistical_strength_score: float
    artifact_strength_score: float
    writing_style_score: float
    reviewer_likelihood_score: float
    claim_honesty_score: float
    top_conference_readiness: bool
    workshop_readiness: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def average_score(self) -> float:
        values = [
            self.novelty_score,
            self.related_work_score,
            self.benchmark_fit_score,
            self.baseline_strength_score,
            self.statistical_strength_score,
            self.artifact_strength_score,
            self.writing_style_score,
            self.reviewer_likelihood_score,
            self.claim_honesty_score,
        ]
        return round(sum(values) / len(values), 3)


class PaperQualityEvaluator:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)

    def assess(self, *, benchmark_id: str = "", manuscript_id: str = "", write: bool = True) -> PaperQualityAssessment:
        context = self._resolve_context(benchmark_id=benchmark_id, manuscript_id=manuscript_id)
        assessment = assess_paper_quality_from_payload(
            context.payload,
            benchmark_id=context.benchmark_id,
            manuscript_id=context.manuscript_id,
            provenance={
                "created_by": "paper-quality-evaluator",
                "created_at": utc_now_iso(),
                "project_root": str(context.project_root) if context.project_root else "",
            },
        )
        if write and context.benchmark_dir is not None:
            output_dir = context.benchmark_dir / "paper_quality"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "paper_quality_assessment.json").write_text(json.dumps(assessment.to_dict(), indent=2) + "\n", encoding="utf-8")
            (output_dir / "paper_quality_assessment.md").write_text(render_paper_quality_report(assessment), encoding="utf-8")
        return assessment

    def report(self, *, benchmark_id: str = "", manuscript_id: str = "") -> str:
        return render_paper_quality_report(self.assess(benchmark_id=benchmark_id, manuscript_id=manuscript_id))

    def _resolve_context(self, *, benchmark_id: str, manuscript_id: str) -> _PaperQualityContext:
        snapshot = self._v25_or_v26_snapshot()
        project_id = str(snapshot.get("project_id", ""))
        resolved_benchmark_id = benchmark_id or str(snapshot.get("benchmark_id", ""))
        resolved_manuscript_id = manuscript_id or str(snapshot.get("manuscript_id", ""))
        project_root = self._project_root(project_id, resolved_benchmark_id, resolved_manuscript_id)
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        manuscript_root = self._manuscript_root(project_root, resolved_manuscript_id)
        if not resolved_manuscript_id and manuscript_root is not None:
            resolved_manuscript_id = manuscript_root.name
        if not resolved_benchmark_id:
            resolved_benchmark_id = self._benchmark_id_from_artifacts(benchmark_dir) or benchmark_id
        if not resolved_benchmark_id:
            raise FileNotFoundError("No selected benchmark id found for paper-quality assessment.")
        if not resolved_manuscript_id:
            raise FileNotFoundError("No manuscript id found for paper-quality assessment.")
        payload = _load_payload(benchmark_dir, manuscript_root, project_root)
        return _PaperQualityContext(
            benchmark_id=resolved_benchmark_id,
            manuscript_id=resolved_manuscript_id,
            project_root=project_root,
            benchmark_dir=benchmark_dir,
            manuscript_root=manuscript_root,
            payload=payload,
        )

    def _v25_or_v26_snapshot(self) -> dict[str, Any]:
        for name in ["v26_release_gate_latest.json", "v25_release_gate_latest.json"]:
            path = self.config.data_dir / "release_gate" / name
            if path.exists():
                return _read_json(path)
        return {}

    def _project_root(self, project_id: str, benchmark_id: str, manuscript_id: str) -> Path | None:
        if project_id:
            try:
                return Path(self.projects.load_project(project_id).project.root_dir)
            except FileNotFoundError:
                pass
        for project_dir in sorted(self.config.project_root.glob("*")):
            if manuscript_id and (project_dir / "manuscripts" / manuscript_id).exists():
                return project_dir
            if benchmark_id and _artifact_benchmark_id(project_dir / "selected_benchmark") == benchmark_id:
                return project_dir
        projects = sorted(self.config.project_root.glob("*"))
        return projects[-1] if projects else None

    def _manuscript_root(self, project_root: Path | None, manuscript_id: str) -> Path | None:
        if project_root is None:
            return None
        if manuscript_id:
            candidate = project_root / "manuscripts" / manuscript_id
            if candidate.exists():
                return candidate
        manuscripts = sorted((project_root / "manuscripts").glob("*"))
        return manuscripts[-1] if manuscripts else None

    def _benchmark_id_from_artifacts(self, benchmark_dir: Path | None) -> str:
        return _artifact_benchmark_id(benchmark_dir)


def assess_paper_quality_from_payload(
    payload: dict[str, Any],
    *,
    benchmark_id: str,
    manuscript_id: str,
    provenance: dict[str, str] | None = None,
) -> PaperQualityAssessment:
    blockers: list[str] = []
    warnings: list[str] = []
    matrix = _dict(payload.get("matrix_loader"))
    artifact = _dict(payload.get("artifact_package_loader"))
    search = _dict(payload.get("real_benchmark_search"))
    assessments = _dicts(payload.get("adapter_assessments")) or [_dict(payload.get("adapter_assessment"))]
    experiments = _dicts(payload.get("real_benchmark_experiments"))
    integration = _dict(payload.get("venue_artifact_integration"))
    rerun = _dict(payload.get("drastic_review_rerun"))
    revision = _dict(payload.get("revision_package"))
    safety = _dict(payload.get("safety"))

    novelty_score = _novelty_score(matrix, blockers, warnings)
    related_work_score = _related_work_score(matrix, blockers, warnings)
    benchmark_fit_score = _benchmark_fit_score(search, assessments, safety, blockers, warnings)
    baseline_strength_score = _baseline_strength_score(assessments, experiments, warnings)
    statistical_strength_score = _statistical_strength_score(experiments, warnings)
    artifact_strength_score = _artifact_strength_score(artifact, blockers, warnings)
    writing_style_score = _writing_style_score(integration, revision, warnings)
    reviewer_likelihood_score = _reviewer_likelihood_score(rerun, blockers, warnings)
    claim_honesty_score = _claim_honesty_score(safety, revision, blockers, warnings)

    likely_decision = str(rerun.get("likely_decision", "")).lower()
    package_status = str(revision.get("status", ""))
    average = round(
        sum(
            [
                novelty_score,
                related_work_score,
                benchmark_fit_score,
                baseline_strength_score,
                statistical_strength_score,
                artifact_strength_score,
                writing_style_score,
                reviewer_likelihood_score,
                claim_honesty_score,
            ]
        )
        / 9,
        3,
    )
    reject_like = likely_decision in {"reject_likely", "borderline_reject"} or "reject" in likely_decision
    top_ready = (
        not blockers
        and not reject_like
        and package_status == "conference_candidate"
        and average >= 0.72
        and benchmark_fit_score >= 0.7
        and related_work_score >= 0.7
        and claim_honesty_score >= 0.9
    )
    workshop_ready = (
        not any(blocker.startswith("safety:") or blocker.startswith("claims:") for blocker in blockers)
        and package_status in {"conference_candidate", "workshop_candidate", "benchmark_no_fit"}
        and related_work_score >= 0.6
        and artifact_strength_score >= 0.6
        and average >= 0.55
    )
    if reject_like and top_ready:
        top_ready = False
    return PaperQualityAssessment(
        id=f"paper-quality-{slugify(benchmark_id)}-{slugify(manuscript_id)}",
        benchmark_id=benchmark_id,
        manuscript_id=manuscript_id,
        novelty_score=novelty_score,
        related_work_score=related_work_score,
        benchmark_fit_score=benchmark_fit_score,
        baseline_strength_score=baseline_strength_score,
        statistical_strength_score=statistical_strength_score,
        artifact_strength_score=artifact_strength_score,
        writing_style_score=writing_style_score,
        reviewer_likelihood_score=reviewer_likelihood_score,
        claim_honesty_score=claim_honesty_score,
        top_conference_readiness=top_ready,
        workshop_readiness=workshop_ready,
        blockers=_unique(blockers),
        warnings=_unique(warnings),
        provenance={"schema": "paper-quality-v1", **(provenance or {})},
    )


def render_paper_quality_report(assessment: PaperQualityAssessment) -> str:
    lines = [
        f"# Paper Quality Assessment `{assessment.benchmark_id}`",
        "",
        f"- Assessment ID: `{assessment.id}`",
        f"- Benchmark: `{assessment.benchmark_id}`",
        f"- Manuscript: `{assessment.manuscript_id}`",
        f"- Average score: `{assessment.average_score:.3f}`",
        f"- Top-conference readiness: `{str(assessment.top_conference_readiness).lower()}`",
        f"- Workshop readiness: `{str(assessment.workshop_readiness).lower()}`",
        "",
        "## Metric Scores",
        "",
        f"- novelty_score: {assessment.novelty_score:.3f}",
        f"- related_work_score: {assessment.related_work_score:.3f}",
        f"- benchmark_fit_score: {assessment.benchmark_fit_score:.3f}",
        f"- baseline_strength_score: {assessment.baseline_strength_score:.3f}",
        f"- statistical_strength_score: {assessment.statistical_strength_score:.3f}",
        f"- artifact_strength_score: {assessment.artifact_strength_score:.3f}",
        f"- writing_style_score: {assessment.writing_style_score:.3f}",
        f"- reviewer_likelihood_score: {assessment.reviewer_likelihood_score:.3f}",
        f"- claim_honesty_score: {assessment.claim_honesty_score:.3f}",
        "",
        "## Blockers",
        "",
        *([f"- {item}" for item in assessment.blockers] if assessment.blockers else ["- none"]),
        "",
        "## Warnings",
        "",
        *([f"- {item}" for item in assessment.warnings] if assessment.warnings else ["- none"]),
        "",
        "## v2.7 Guidance",
        "",
        "- Prioritize the lowest scoring paper-quality dimensions before treating workflow completion as readiness.",
        "- Top-conference claims require strong benchmark fit, related work, reviewer likelihood, and claim honesty together.",
    ]
    return "\n".join(lines).rstrip() + "\n"


@dataclass(slots=True)
class _PaperQualityContext:
    benchmark_id: str
    manuscript_id: str
    project_root: Path | None
    benchmark_dir: Path | None
    manuscript_root: Path | None
    payload: dict[str, Any]


def _load_payload(benchmark_dir: Path | None, manuscript_root: Path | None, project_root: Path | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if benchmark_dir is not None:
        payload["matrix_loader"] = _read_json(benchmark_dir / "related_work_matrix_loader" / "related_work_matrix_load_result.json")
        payload["artifact_package_loader"] = _read_json(benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json")
        payload["real_benchmark_search"] = _read_json(benchmark_dir / "real_benchmark_search" / "real_benchmark_candidate_search.json")
        payload["adapter_assessments"] = [
            *_read_json_glob(benchmark_dir / "real_benchmark_adapters", "*.assessment.json"),
            *_read_json_glob(benchmark_dir / "real_benchmark_adapters", "real-benchmark-adapter-assessment-*.json"),
        ]
        payload["real_benchmark_experiments"] = _read_json_list(
            benchmark_dir / "real_benchmark_experiments" / "real_benchmark_experiment_attempts.json"
        )
        payload["venue_artifact_integration"] = _read_json(benchmark_dir / "venue_artifact_integration" / "report.json")
        payload["revision_package"] = _read_json(benchmark_dir / "venue_revision_package" / "latest.json")
    if manuscript_root is not None:
        payload["drastic_review_rerun"] = _read_json(manuscript_root / "reviews" / "drastic" / "drastic_review_rerun_result.json")
    payload["safety"] = _safety_payload(project_root)
    return payload


def _novelty_score(matrix: dict[str, Any], blockers: list[str], warnings: list[str]) -> float:
    if str(matrix.get("status", "")) not in {"loaded", "repaired"}:
        blockers.append("related_work: matrix is missing or unloadable")
        return 0.0
    if _list(matrix.get("blockers")):
        blockers.extend(f"related_work: {item}" for item in _list(matrix.get("blockers")))
        return 0.0
    checks = [
        _float(matrix.get("entry_count")) >= 5,
        _float(matrix.get("must_cite_count")) >= 2,
        _float(matrix.get("closest_prior_work_count")) >= 1,
        not bool(matrix.get("fallback_entries_promoted")),
    ]
    if bool(matrix.get("fallback_entries_promoted")):
        warnings.append("novelty: fallback-only related-work entries cannot establish novelty")
    return _score(checks)


def _related_work_score(matrix: dict[str, Any], blockers: list[str], warnings: list[str]) -> float:
    if str(matrix.get("status", "")) not in {"loaded", "repaired"}:
        blockers.append("related_work: related-work matrix is missing")
        return 0.0
    if _list(matrix.get("blockers")):
        blockers.extend(f"related_work: {item}" for item in _list(matrix.get("blockers")))
        return 0.0
    checks = [
        _float(matrix.get("entry_count")) >= 6,
        _float(matrix.get("must_cite_count")) >= 2,
        _float(matrix.get("closest_prior_work_count")) >= 1,
        not bool(matrix.get("fallback_entries_promoted")),
    ]
    if _float(matrix.get("entry_count")) < 6:
        warnings.append("related_work: required category coverage appears thin")
    return _score(checks)


def _benchmark_fit_score(
    search: dict[str, Any],
    assessments: list[dict[str, Any]],
    safety: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> float:
    if bool(safety.get("synthetic_deployment_validity_claim")):
        blockers.append("claims: synthetic-only evidence is used for deployment-validity claims")
    if str(search.get("status", "")) == "no_fit":
        warnings.append("benchmark_fit: no real/public benchmark fit supports strong claims")
        return 0.35
    if not search or str(search.get("status", "")) != "complete":
        blockers.append("benchmark_fit: real/vetted benchmark search is missing")
        return 0.0
    support = [_support_level(item) for item in assessments if item]
    if not support:
        blockers.append("benchmark_fit: adapter assessment is missing")
        return 0.0
    if "primary" in support:
        score = 0.85
    elif "auxiliary" in support:
        score = 0.55
        warnings.append("benchmark_fit: auxiliary-only benchmark fit caps benchmark_fit_score")
    elif "sanity_check" in support:
        score = 0.45
        warnings.append("benchmark_fit: sanity-check-only benchmark fit caps benchmark_fit_score")
    else:
        score = 0.4
        warnings.append("benchmark_fit: adapter fit is weak or unclear")
    if bool(search.get("synthetic_only")):
        score = min(score, 0.35)
        warnings.append("benchmark_fit: synthetic-only evidence caps benchmark_fit_score")
    return round(score, 3)


def _baseline_strength_score(assessments: list[dict[str, Any]], experiments: list[dict[str, Any]], warnings: list[str]) -> float:
    support = [_support_level(item) for item in assessments if item] + [str(item.get("claim_support_level", "")) for item in experiments]
    if "primary" in support:
        return 0.75
    if "auxiliary" in support:
        warnings.append("baselines: auxiliary evidence leaves baseline strength limited")
        return 0.55
    if "sanity_check" in support:
        warnings.append("baselines: sanity-check evidence is not a strong baseline suite")
        return 0.45
    warnings.append("baselines: required baseline coverage could not be established")
    return 0.4


def _statistical_strength_score(experiments: list[dict[str, Any]], warnings: list[str]) -> float:
    if not experiments:
        warnings.append("statistics: no real benchmark experiment or no-fit record was found")
        return 0.3
    support = [str(item.get("claim_support_level", "")) for item in experiments]
    if any("underpowered" in " ".join(str(value) for value in item.values()).lower() for item in experiments):
        warnings.append("statistics: underpowered warning present")
        return 0.3
    if "primary" in support:
        warnings.append("statistics: alpha/confidence-interval support should still be checked manually")
        return 0.7
    if "auxiliary" in support:
        warnings.append("statistics: auxiliary result support limits statistical strength")
        return 0.55
    if "sanity_check" in support:
        warnings.append("statistics: sanity-check result support limits statistical strength")
        return 0.45
    if "none" in support:
        warnings.append("statistics: no-fit evidence does not supply statistical support")
        return 0.35
    return 0.5


def _artifact_strength_score(artifact: dict[str, Any], blockers: list[str], warnings: list[str]) -> float:
    if str(artifact.get("status", "")) not in {"loaded", "repaired"}:
        blockers.append("artifact: artifact package is missing or unloadable")
        return 0.0
    if _list(artifact.get("blockers")):
        blockers.extend(f"artifact: {item}" for item in _list(artifact.get("blockers")))
        return 0.0
    required = set(str(item) for item in _list(artifact.get("required_files_present")))
    checks = [
        bool(artifact.get("selected_package_id")),
        {"README.md", "run.sh", "expected_outputs.json"} <= required,
        bool(artifact.get("expected_outputs_present")),
        bool(artifact.get("replication_package_present")),
        bool(artifact.get("hardware_requirements_present")),
        bool(artifact.get("run_instructions_present")),
    ]
    if not bool(artifact.get("replication_package_present")):
        warnings.append("artifact: replication package missing")
    return _score(checks)


def _writing_style_score(integration: dict[str, Any], revision: dict[str, Any], warnings: list[str]) -> float:
    files = set(str(item) for item in _list(revision.get("files")))
    limitations = _list(revision.get("limitations"))
    checks = [
        bool(integration.get("exists")),
        not _list(integration.get("blockers")),
        bool(revision.get("venue_profile_id")),
        str(revision.get("status", "")) in {"conference_candidate", "workshop_candidate", "revise_for_reviews", "benchmark_no_fit"},
        bool(files),
        bool(limitations),
    ]
    if not bool(limitations):
        warnings.append("writing: limitation visibility is missing")
    return _score(checks)


def _reviewer_likelihood_score(rerun: dict[str, Any], blockers: list[str], warnings: list[str]) -> float:
    if not rerun:
        blockers.append("reviewer: drastic review rerun is missing")
        return 0.0
    remaining = _list(rerun.get("remaining_blockers"))
    decision = str(rerun.get("likely_decision", "")).lower()
    if remaining:
        blockers.extend(f"reviewer: {item}" for item in remaining)
    if decision == "accept_likely":
        base = 0.9
    elif decision == "revise_before_submission":
        base = 0.65
    elif decision == "borderline_reject":
        base = 0.4
        warnings.append("reviewer: drastic review predicts borderline reject")
    elif decision == "reject_likely" or "reject" in decision:
        base = 0.25
        warnings.append("reviewer: drastic review predicts reject")
    else:
        base = 0.5
        warnings.append("reviewer: drastic review likely decision is unknown")
    if remaining:
        base = min(base, 0.35)
    return round(base, 3)


def _claim_honesty_score(safety: dict[str, Any], revision: dict[str, Any], blockers: list[str], warnings: list[str]) -> float:
    if any(bool(safety.get(key)) for key in ["fake_citation_present", "fake_result_present", "copied_prose_detected"]):
        blockers.append("safety: fake citation/result or copied prose detected")
        return 0.0
    if bool(safety.get("synthetic_deployment_validity_claim")) or bool(revision.get("synthetic_deployment_validity_claim")):
        blockers.append("claims: deployment-validity overclaim from synthetic-only evidence")
        return 0.0
    checks = [
        not bool(revision.get("fake_citations")),
        not bool(revision.get("fake_results")),
        not bool(revision.get("copied_prose")),
        not bool(revision.get("synthetic_deployment_validity_claim")),
        bool(_list(revision.get("limitations"))),
    ]
    if not bool(_list(revision.get("limitations"))):
        warnings.append("claims: limitation labels are missing")
    return _score(checks)


def _safety_payload(project_root: Path | None) -> dict[str, bool]:
    payload = {
        "fake_citation_present": False,
        "fake_result_present": False,
        "copied_prose_detected": False,
        "synthetic_deployment_validity_claim": False,
    }
    if project_root is None:
        return payload
    for path in project_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".tex"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lower = text.lower()
        if FAKE_CITATION_RE.search(text):
            payload["fake_citation_present"] = True
        if "fake result" in lower or "invented result" in lower:
            payload["fake_result_present"] = True
        if "copied prose" in lower:
            payload["copied_prose_detected"] = True
        if DEPLOYMENT_VALIDITY_RE.search(text):
            payload["synthetic_deployment_validity_claim"] = True
    return payload


def _artifact_benchmark_id(benchmark_dir: Path | None) -> str:
    if benchmark_dir is None:
        return ""
    for path in [
        benchmark_dir / "related_work_matrix_loader" / "related_work_matrix_load_result.json",
        benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json",
        benchmark_dir / "real_benchmark_search" / "real_benchmark_candidate_search.json",
    ]:
        payload = _read_json(path)
        value = payload.get("benchmark_id") or payload.get("selected_benchmark_id")
        if value:
            return str(value)
    return ""


def _support_level(assessment: dict[str, Any]) -> str:
    return str(
        assessment.get("expected_claim_support")
        or assessment.get("fit_status")
        or assessment.get("adapter_type")
        or assessment.get("claim_support_level")
        or ""
    )


def _score(checks: list[bool]) -> float:
    if not checks:
        return 0.0
    return round(sum(1 for item in checks if item) / len(checks), 3)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _read_json_glob(root: Path, pattern: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    return [_read_json(path) for path in sorted(root.glob(pattern)) if _read_json(path)]


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
