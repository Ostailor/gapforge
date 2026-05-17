"""v2.7 conference-candidate hardening release gate."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.external_review import ExternalExpertReview, external_review_status
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v26 import V26ReleaseGateEnforcer

V27_STATUSES = {"conference_candidate", "workshop_candidate", "revise_for_reviews", "no_go"}
PAPER_QUALITY_THRESHOLD = 0.72


@dataclass(slots=True)
class V27ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    benchmark_id: str = ""
    manuscript_id: str = ""
    v26_status: str = ""
    paper_quality_score: float = 0.0
    paper_quality_threshold: float = PAPER_QUALITY_THRESHOLD
    top_conference_readiness: bool = False
    external_review_status: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V27ReleaseGateEnforcer:
    """Require issue-level, artifact-level, and paper-quality closure before conference candidacy."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)

    def evaluate(self) -> V27ReleaseGateResult:
        v26 = V26ReleaseGateEnforcer(self.config).evaluate()
        project_root = self._project_root(v26.project_id)
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        manuscript_root = self._manuscript_root(project_root, v26.manuscript_id)
        manuscript_id = manuscript_root.name if manuscript_root else v26.manuscript_id
        artifacts = _V27Artifacts.load(benchmark_dir, manuscript_root)
        review_status = _review_issue_status(artifacts.review_issues, manuscript_id)
        external_status = _external_status(artifacts.external_reviews, artifacts.external_unavailable, manuscript_id)

        requirements = {
            "v26_gate_passes": bool(v26.passed),
            "paper_quality_above_threshold": bool(v26.top_conference_readiness and v26.paper_quality_score >= PAPER_QUALITY_THRESHOLD),
            "drastic_review_no_fatal_blockers": not _remaining_fatal(artifacts.drastic_rerun),
            "review_issue_tracker_has_no_open_fatal_issues": not review_status["open_fatal_issue_ids"]
            and not review_status["impossible_fatal_issue_ids"],
            "benchmark_fit_or_no_fit_argument_present": artifacts.benchmark_fit_present,
            "required_ablations_complete_or_justified": artifacts.ablation_complete_or_justified,
            "manuscript_top_conference_revision_complete": artifacts.top_revision_complete,
            "artifact_package_loadable": artifacts.artifact_package.get("status") in {"loaded", "repaired"}
            and not artifacts.artifact_package.get("blockers"),
            "claim_traceability_passes": artifacts.claim_traceability_passes,
            "no_fake_citations_results_copied_prose": bool(
                v26.requirements.get("fake_citations_results_blocked") and v26.requirements.get("no_copied_paper_prose")
            ),
            "no_synthetic_deployment_overclaim": bool(v26.requirements.get("no_synthetic_deployment_validity_claim")),
            "external_review_captured_or_explicitly_unavailable": bool(
                external_status["human_review_count"] or external_status["simulated_review_count"] or artifacts.external_unavailable
            )
            and external_status["conference_candidate_allowed"],
        }
        blockers = _requirement_blockers(requirements)
        blockers.extend(_review_issue_blockers(review_status))
        blockers.extend(external_status.get("blockers", []))
        blockers.extend(_artifact_blockers(artifacts))
        status = _decision_status(requirements, blockers=blockers, v26_status=v26.status)
        passed = status in {"conference_candidate", "workshop_candidate"}
        warnings = _warnings(v26_status=v26.status, artifacts=artifacts, external_status=external_status)
        return V27ReleaseGateResult(
            passed=passed,
            status=status,
            recommended_next_version="v2.8" if status == "conference_candidate" else "v2.7-remediation",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            project_id=v26.project_id,
            benchmark_id=v26.benchmark_id,
            manuscript_id=manuscript_id,
            v26_status=v26.status,
            paper_quality_score=v26.paper_quality_score,
            top_conference_readiness=v26.top_conference_readiness,
            external_review_status=external_status,
            artifact_paths=artifacts.paths,
        )

    def write_outputs(self, result: V27ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v27_release_gate_latest.json"
        data_md_path = self.release_dir / "v27-release-gate-latest.md"
        report = render_v27_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v27-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _project_root(self, project_id: str) -> Path | None:
        if project_id:
            try:
                return Path(self.projects.load_project(project_id).project.root_dir)
            except FileNotFoundError:
                pass
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


@dataclass(slots=True)
class _V27Artifacts:
    artifact_package: dict[str, Any] = field(default_factory=dict)
    drastic_rerun: dict[str, Any] = field(default_factory=dict)
    review_issues: list[dict[str, Any]] = field(default_factory=list)
    top_revision: dict[str, Any] = field(default_factory=dict)
    top_readiness: dict[str, Any] = field(default_factory=dict)
    traceability: dict[str, Any] = field(default_factory=dict)
    ablation_run: dict[str, Any] = field(default_factory=dict)
    external_reviews: list[dict[str, Any]] = field(default_factory=list)
    external_unavailable: bool = False
    benchmark_fit_present: bool = False
    ablation_complete_or_justified: bool = False
    top_revision_complete: bool = False
    claim_traceability_passes: bool = False
    paths: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, benchmark_dir: Path | None, manuscript_root: Path | None) -> _V27Artifacts:
        artifact = cls()
        if benchmark_dir is not None:
            artifact.artifact_package = _read_json(benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json")
            artifact.ablation_run = _read_json(benchmark_dir / "ablations" / "selected_ablation_run.json")
            artifact.benchmark_fit_present = _benchmark_fit_present(benchmark_dir)
            artifact.ablation_complete_or_justified = _ablation_complete_or_justified(benchmark_dir, artifact.ablation_run)
        if manuscript_root is not None:
            artifact.drastic_rerun = _read_json(manuscript_root / "reviews" / "drastic" / "drastic_review_rerun_result.json")
            artifact.review_issues = _read_json(manuscript_root / "reviews" / "drastic" / "review_issues.json").get("issues", [])
            artifact.top_revision = _read_json(
                manuscript_root / "submission" / "top_conference_revision" / "top_conference_revision_report.json"
            )
            artifact.top_readiness = _read_json(
                manuscript_root / "submission" / "top_conference_revision" / "top_conference_readiness.json"
            )
            artifact.traceability = _read_json(manuscript_root / "submission" / "traceability_report.json")
            artifact.external_reviews = _read_json(manuscript_root / "reviews" / "external" / "external_expert_reviews.json").get(
                "reviews", []
            )
            artifact.external_unavailable = _external_unavailable(manuscript_root)
            artifact.top_revision_complete = _top_revision_complete(artifact.top_revision, artifact.top_readiness)
            artifact.claim_traceability_passes = not artifact.traceability.get("blocking_issues") and bool(artifact.traceability)
        artifact.paths = _paths(benchmark_dir, manuscript_root)
        return artifact


def render_v27_release_gate_markdown(result: V27ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.7 Conference-Candidate Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Project: `{result.project_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Manuscript: `{result.manuscript_id or 'missing'}`",
        f"- v2.6 status: `{result.v26_status or 'missing'}`",
        f"- Paper-quality score: {result.paper_quality_score:.3f}",
        f"- Paper-quality threshold: {result.paper_quality_threshold:.3f}",
        f"- Top-conference readiness: {str(result.top_conference_readiness).lower()}",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## External Review", ""])
    for key in [
        "human_review_count",
        "simulated_review_count",
        "unresolved_fatal_external_review_count",
        "conference_candidate_allowed",
    ]:
        lines.append(f"- {key}: `{result.external_review_status.get(key, 'missing')}`")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- v2.7 conference_candidate is intentionally hard to achieve.",
            "- Workshop, revise_for_reviews, and no_go are honest alternatives when evidence is incomplete or unsafe.",
            "- No fatal blocker may be hidden behind a positive status.",
            "- This gate does not claim acceptance.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _decision_status(requirements: dict[str, bool], *, blockers: list[str], v26_status: str) -> str:
    hard_failures = {
        "artifact_package_loadable",
        "claim_traceability_passes",
        "no_fake_citations_results_copied_prose",
        "no_synthetic_deployment_overclaim",
    }
    if any(not requirements[name] for name in hard_failures):
        return "no_go"
    if all(requirements.values()) and not blockers:
        return "conference_candidate"
    if requirements["v26_gate_passes"] and v26_status == "workshop_candidate" and not _fatal_blocker_text(blockers):
        return "workshop_candidate"
    return "revise_for_reviews"


def _fatal_blocker_text(blockers: list[str]) -> bool:
    return any("fatal" in blocker.lower() or "external human review" in blocker.lower() for blocker in blockers)


def _review_issue_status(issues: list[dict[str, Any]], manuscript_id: str) -> dict[str, Any]:
    open_fatal = [
        str(issue.get("id")) for issue in issues if issue.get("severity") == "fatal" and issue.get("status") in {"open", "in_progress"}
    ]
    impossible_fatal = [
        str(issue.get("id")) for issue in issues if issue.get("severity") == "fatal" and issue.get("status") == "impossible"
    ]
    return {
        "manuscript_id": manuscript_id,
        "has_checklist": bool(issues),
        "open_fatal_issue_ids": open_fatal,
        "impossible_fatal_issue_ids": impossible_fatal,
    }


def _review_issue_blockers(status: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if status["open_fatal_issue_ids"]:
        blockers.append("Open fatal review issues remain: " + ", ".join(status["open_fatal_issue_ids"]))
    if status["impossible_fatal_issue_ids"]:
        blockers.append("Impossible fatal review issues remain: " + ", ".join(status["impossible_fatal_issue_ids"]))
    return blockers


def _external_status(reviews: list[dict[str, Any]], unavailable: bool, manuscript_id: str) -> dict[str, Any]:
    typed_reviews = [from_dict_external_review(review) for review in reviews]
    status = external_review_status(manuscript_id, typed_reviews)
    status["explicitly_unavailable"] = unavailable
    if not reviews and not unavailable:
        status["blockers"] = [*status.get("blockers", []), "External review is missing and not explicitly marked unavailable."]
    return status


def from_dict_external_review(payload: dict[str, Any]) -> ExternalExpertReview:
    provenance = payload.get("provenance") or {}
    return ExternalExpertReview(
        id=str(payload.get("id", "")),
        manuscript_id=str(payload.get("manuscript_id", "")),
        reviewer_role=str(payload.get("reviewer_role", "")),
        expertise_area=str(payload.get("expertise_area", "")),
        overall_recommendation=str(payload.get("overall_recommendation", "borderline")),
        key_strengths=[str(item) for item in payload.get("key_strengths", [])],
        key_weaknesses=[str(item) for item in payload.get("key_weaknesses", [])],
        missing_related_work=[str(item) for item in payload.get("missing_related_work", [])],
        missing_experiments=[str(item) for item in payload.get("missing_experiments", [])],
        claim_overreach=[str(item) for item in payload.get("claim_overreach", [])],
        required_revisions=[str(item) for item in payload.get("required_revisions", [])],
        notes=[str(item) for item in payload.get("notes", [])],
        provenance=from_dict_provenance(provenance),
    )


def from_dict_provenance(payload: dict[str, Any]) -> Provenance:
    return Provenance(
        created_by_skill=str(payload.get("created_by_skill", "external-expert-review-human")),
        source_ids=[str(item) for item in payload.get("source_ids", [])],
        timestamp=str(payload.get("timestamp", "")),
        reasoning_summary=str(payload.get("reasoning_summary", "")),
    )


def _remaining_fatal(rerun: dict[str, Any]) -> list[str]:
    return [str(item) for item in rerun.get("remaining_blockers", []) if item]


def _benchmark_fit_present(benchmark_dir: Path) -> bool:
    hardening = benchmark_dir / "benchmark_fit_hardening"
    return (hardening / "benchmark_fit_hardening_report.md").exists() or (hardening / "no_fit_argument.md").exists()


def _ablation_complete_or_justified(benchmark_dir: Path, ablation_run: dict[str, Any]) -> bool:
    if (
        ablation_run.get("strong_claim_allowed")
        and not ablation_run.get("missing_ablation_types")
        and not ablation_run.get("reviewer_blockers")
    ):
        return True
    justification = _read_json(benchmark_dir / "ablations" / "ablation_justification.json")
    return justification.get("status") == "justified" and not justification.get("reviewer_blockers")


def _top_revision_complete(revision: dict[str, Any], readiness: dict[str, Any]) -> bool:
    return (
        revision.get("status") == "revision_ready"
        and bool(revision.get("claim_traceability_passed"))
        and bool(revision.get("limitations_preserved"))
        and not revision.get("unsupported_claims_added")
        and not revision.get("blockers")
        and bool(readiness.get("claim_traceability_passed", True))
    )


def _external_unavailable(manuscript_root: Path) -> bool:
    unavailable_json = manuscript_root / "reviews" / "external" / "external_review_unavailable.json"
    unavailable_md = manuscript_root / "reviews" / "external" / "external_review_unavailable.md"
    if unavailable_json.exists():
        payload = _read_json(unavailable_json)
        return bool(payload.get("explicitly_not_available") or payload.get("status") == "not_available")
    if unavailable_md.exists():
        text = unavailable_md.read_text(encoding="utf-8").lower()
        return "not available" in text or "unavailable" in text
    return False


def _artifact_blockers(artifacts: _V27Artifacts) -> list[str]:
    blockers: list[str] = []
    if artifacts.artifact_package and artifacts.artifact_package.get("blockers"):
        blockers.extend(f"Artifact package blocker: {item}" for item in artifacts.artifact_package.get("blockers", []))
    if artifacts.ablation_run and artifacts.ablation_run.get("missing_ablation_types"):
        blockers.append("Missing ablations remain: " + ", ".join(artifacts.ablation_run.get("missing_ablation_types", [])))
    if artifacts.top_revision and artifacts.top_revision.get("blockers"):
        blockers.extend(f"Top-conference revision blocker: {item}" for item in artifacts.top_revision.get("blockers", []))
    if artifacts.traceability and artifacts.traceability.get("blocking_issues"):
        blockers.extend(f"Traceability blocker: {item}" for item in artifacts.traceability.get("blocking_issues", []))
    return blockers


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    labels = {
        "v26_gate_passes": "v2.6 gate does not pass.",
        "paper_quality_above_threshold": f"Paper-quality score is below threshold {PAPER_QUALITY_THRESHOLD:.2f} or not top-ready.",
        "drastic_review_no_fatal_blockers": "Drastic review has remaining fatal blockers.",
        "review_issue_tracker_has_no_open_fatal_issues": "Review issue tracker has open fatal issues or no checklist.",
        "benchmark_fit_or_no_fit_argument_present": "Benchmark fit/no-fit argument is missing.",
        "required_ablations_complete_or_justified": "Required ablations are incomplete and not justified.",
        "manuscript_top_conference_revision_complete": "Top-conference manuscript revision is missing or blocked.",
        "artifact_package_loadable": "Artifact package is not loadable.",
        "claim_traceability_passes": "Claim traceability does not pass.",
        "no_fake_citations_results_copied_prose": "Fake citations/results or copied prose are detected.",
        "no_synthetic_deployment_overclaim": "Synthetic deployment overclaim is detected.",
        "external_review_captured_or_explicitly_unavailable": "External review is missing, fatal, or not explicitly unavailable.",
    }
    return [labels[name] for name, passed in requirements.items() if not passed]


def _warnings(*, v26_status: str, artifacts: _V27Artifacts, external_status: dict[str, Any]) -> list[str]:
    warnings = [f"v2.6 status is `{v26_status}`."]
    if artifacts.external_unavailable:
        warnings.append("External review is explicitly unavailable; this is weaker than captured human critique.")
    if external_status.get("simulated_review_count") and not external_status.get("human_review_count"):
        warnings.append("Only simulated external review is present; simulated review is advisory.")
    if artifacts.ablation_run.get("synthetic"):
        warnings.append("Ablation run is synthetic; do not claim deployment validity from it.")
    return warnings


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _paths(benchmark_dir: Path | None, manuscript_root: Path | None) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    candidates = []
    if benchmark_dir is not None:
        candidates.extend(
            [
                benchmark_dir / "artifact_package_loader" / "artifact_package_load_result.json",
                benchmark_dir / "benchmark_fit_hardening" / "benchmark_fit_hardening_report.md",
                benchmark_dir / "benchmark_fit_hardening" / "no_fit_argument.md",
                benchmark_dir / "ablations" / "selected_ablation_run.json",
            ]
        )
    if manuscript_root is not None:
        candidates.extend(
            [
                manuscript_root / "reviews" / "drastic" / "drastic_review_rerun_result.json",
                manuscript_root / "reviews" / "drastic" / "review_issues.json",
                manuscript_root / "reviews" / "external" / "external_expert_reviews.json",
                manuscript_root / "submission" / "traceability_report.json",
                manuscript_root / "submission" / "top_conference_revision" / "top_conference_revision_report.json",
                manuscript_root / "submission" / "top_conference_revision" / "top_conference_readiness.json",
            ]
        )
    for path in candidates:
        if path.exists():
            paths.setdefault(path.parent.name, []).append(str(path))
    return paths


def _unique(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
