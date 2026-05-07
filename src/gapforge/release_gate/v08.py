"""v0.8 manuscript, artifact-evaluation, and rebuttal release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.manuscript.citations import suspicious_citation_string, unresolved_citation_keys
from gapforge.manuscript.models import (
    BibliographyRecord,
    ManuscriptReviewPanel,
    ManuscriptState,
    ManuscriptTraceabilityReport,
    RevisionPlan,
    SubmissionChecklist,
    SubmissionPackage,
)
from gapforge.models import ExperimentExecutionRecord, from_dict


@dataclass(slots=True)
class V08ManuscriptAssessment:
    manuscript_id: str
    status: str
    requirements: dict[str, bool]
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class V08ReleaseGateResult:
    passed: bool
    status: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    manuscripts: list[V08ManuscriptAssessment]
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V08ReleaseGateEnforcer:
    """Machine-check v0.8 manuscript release eligibility."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def evaluate(self) -> V08ReleaseGateResult:
        artifacts = self._artifact_index()
        manuscript_assessments = [self._assess_manuscript(path) for path in artifacts["manuscript_states"]]
        manuscript_ready = any(item.status == "pass" for item in manuscript_assessments)
        manuscript_blockers = [f"{item.manuscript_id}: {blocker}" for item in manuscript_assessments for blocker in item.blockers]
        requirements = {
            "deterministic_ci_passed": self._deterministic_ci_passed(),
            "v7_release_gate_passed_or_documented": self._v7_gate_passed_or_documented(),
            "manuscript_project_created": bool(manuscript_assessments),
            "bibliography_built": manuscript_ready
            and any(item.requirements.get("bibliography_built", False) for item in manuscript_assessments),
            "manuscript_draft_generated": manuscript_ready
            and any(item.requirements.get("manuscript_draft_generated", False) for item in manuscript_assessments),
            "claim_traceability_report_generated": manuscript_ready
            and any(item.requirements.get("claim_traceability_report_generated", False) for item in manuscript_assessments),
            "artifact_backed_asset_generated": manuscript_ready
            and any(item.requirements.get("artifact_backed_asset_generated", False) for item in manuscript_assessments),
            "venue_checklist_generated": manuscript_ready
            and any(item.requirements.get("venue_checklist_generated", False) for item in manuscript_assessments),
            "artifact_evaluation_package_generated": manuscript_ready
            and any(item.requirements.get("artifact_evaluation_package_generated", False) for item in manuscript_assessments),
            "reviewer_panel_generated": manuscript_ready
            and any(item.requirements.get("reviewer_panel_generated", False) for item in manuscript_assessments),
            "rebuttal_revision_plan_generated": manuscript_ready
            and any(item.requirements.get("rebuttal_revision_plan_generated", False) for item in manuscript_assessments),
            "submission_package_exported": manuscript_ready
            and any(item.requirements.get("submission_package_exported", False) for item in manuscript_assessments),
            "unsupported_claims_blocked": bool(manuscript_assessments)
            and all(item.requirements.get("unsupported_claims_blocked", False) for item in manuscript_assessments),
            "fake_citations_blocked": bool(manuscript_assessments)
            and all(item.requirements.get("fake_citations_blocked", False) for item in manuscript_assessments),
            "no_fake_results_in_manuscript": bool(manuscript_assessments)
            and all(item.requirements.get("no_fake_results_in_manuscript", False) for item in manuscript_assessments),
            "failed_negative_experiments_acknowledged": bool(manuscript_assessments)
            and all(item.requirements.get("failed_negative_experiments_acknowledged", False) for item in manuscript_assessments),
            "camera_ready_rebuttal_blockers_addressed": bool(manuscript_assessments)
            and all(item.requirements.get("camera_ready_rebuttal_blockers_addressed", False) for item in manuscript_assessments),
        }
        blockers = _gate_blockers(requirements)
        if not manuscript_assessments:
            blockers.append("No manuscript project was found.")
        blockers.extend(manuscript_blockers)
        blockers = _unique(blockers)
        warnings = _unique(_gate_warnings(requirements) + [warning for item in manuscript_assessments for warning in item.warnings])
        passed = not blockers and all(requirements.values())
        status = "pass" if passed else "partial" if manuscript_assessments else "fail"
        return V08ReleaseGateResult(
            passed=passed,
            status=status,
            requirements=requirements,
            blockers=blockers,
            warnings=warnings,
            manuscripts=manuscript_assessments,
            artifact_paths={key: [str(path) for path in paths] for key, paths in artifacts.items()},
        )

    def write_outputs(self, result: V08ReleaseGateResult) -> tuple[Path, Path]:
        data_dir = self.config.data_dir / "release_gate"
        data_dir.mkdir(parents=True, exist_ok=True)
        json_path = data_dir / "v0.8_latest.json"
        md_path = data_dir / "v0.8_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v08_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _artifact_index(self) -> dict[str, list[Path]]:
        roots = [root for root in [self.config.project_root, self.config.data_dir] if root.exists()]
        return {
            "manuscript_states": _glob_many(roots, ["**/manuscripts/*/manuscript.json"]),
            "release_gate_reports": _glob_many(roots, ["**/release_gate/v0.*_latest.json", "**/release_gate/v0.*_latest.md"]),
        }

    def _assess_manuscript(self, manuscript_path: Path) -> V08ManuscriptAssessment:
        root = manuscript_path.parent
        state = _load_json_dataclass(ManuscriptState, manuscript_path)
        manuscript_id = state.manuscript.id if state else root.name
        paths = _manuscript_paths(root)
        bibliography = _load_optional(BibliographyRecord, paths["bibliography"])
        traceability = _load_optional(ManuscriptTraceabilityReport, paths["traceability"])
        checklist = _load_optional(SubmissionChecklist, paths["checklist"])
        review_panel = _load_optional(ManuscriptReviewPanel, paths["review_panel"])
        revision = _load_optional(RevisionPlan, paths["revision_plan"])
        submission_packages = [
            _load_optional(SubmissionPackage, path) for path in sorted(root.glob("submission/packages/*/submission_package.json"))
        ]
        packages = [item for item in submission_packages if item is not None]
        fake_citation_blockers = _fake_citation_blockers(state, bibliography) if state else ["Manuscript state could not be loaded."]
        unsupported_blockers = _unsupported_claim_blockers(traceability, state)
        fake_result_blockers = _fake_result_blockers(root)
        failed_blockers = _failed_experiment_blockers(root, state)
        camera_blockers = _camera_ready_blockers(packages, revision)
        requirements = {
            "bibliography_built": bibliography is not None and bool(bibliography.entries),
            "manuscript_draft_generated": bool(paths["drafts"]),
            "claim_traceability_report_generated": traceability is not None,
            "artifact_backed_asset_generated": bool(paths["figures"] or paths["tables"]),
            "venue_checklist_generated": checklist is not None,
            "artifact_evaluation_package_generated": bool(paths["artifact_packages"]),
            "reviewer_panel_generated": review_panel is not None,
            "rebuttal_revision_plan_generated": revision is not None,
            "submission_package_exported": bool(packages),
            "unsupported_claims_blocked": not unsupported_blockers,
            "fake_citations_blocked": not fake_citation_blockers,
            "no_fake_results_in_manuscript": not fake_result_blockers,
            "failed_negative_experiments_acknowledged": not failed_blockers,
            "camera_ready_rebuttal_blockers_addressed": not camera_blockers,
        }
        blockers = _manuscript_blockers(requirements)
        blockers.extend(unsupported_blockers)
        blockers.extend(fake_citation_blockers)
        blockers.extend(fake_result_blockers)
        blockers.extend(failed_blockers)
        blockers.extend(camera_blockers)
        blockers = _unique(blockers)
        status = "pass" if not blockers and all(requirements.values()) else "partial"
        warnings = _manuscript_warnings(state, packages, revision)
        return V08ManuscriptAssessment(
            manuscript_id=manuscript_id,
            status=status,
            requirements=requirements,
            blockers=blockers,
            warnings=warnings,
            artifact_paths={key: [str(path) for path in value] for key, value in paths.items()},
        )

    def _deterministic_ci_passed(self) -> bool:
        return _json_passed(self.config.data_dir / "release_gate" / "deterministic_ci.json")

    def _v7_gate_passed_or_documented(self) -> bool:
        release_dir = self.config.data_dir / "release_gate"
        json_path = release_dir / "v0.7_latest.json"
        md_path = release_dir / "v0.7_latest.md"
        if json_path.exists():
            if _json_passed(json_path):
                return True
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
            return isinstance(payload, dict) and "passed" in payload
        return md_path.exists()


def render_v08_release_gate_markdown(result: V08ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.8 Manuscript Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Manuscripts assessed: {len(result.manuscripts)}",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(["", "## Manuscripts", ""])
    for manuscript in result.manuscripts:
        lines.extend(
            [
                f"### `{manuscript.manuscript_id}`",
                "",
                f"- Status: `{manuscript.status}`",
                f"- Submission package: {str(manuscript.requirements.get('submission_package_exported', False)).lower()}",
                "",
            ]
        )
        lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in manuscript.requirements.items())
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    return "\n".join(lines).rstrip() + "\n"


def _manuscript_paths(root: Path) -> dict[str, list[Path]]:
    return {
        "bibliography": _glob_many([root], ["bibliography/bibliography.json"]),
        "drafts": _glob_many([root], ["submission/packages/*/manuscript.md", "submission/packages/*/manuscript.tex", "sections/*.md"]),
        "traceability": _glob_many([root], ["submission/traceability_report.json"]),
        "figures": _glob_many([root], ["figures/*.json", "figures/*.svg", "submission/packages/*/figures/*"]),
        "tables": _glob_many([root], ["tables/*.json", "tables/*.md", "submission/packages/*/tables/*"]),
        "checklist": _glob_many([root], ["submission/submission_checklist.json", "submission/packages/*/checklist_report.json"]),
        "artifact_packages": _glob_many([root], ["artifact_evaluation/*/artifact_evaluation_package.json"]),
        "review_panel": _glob_many([root], ["reviews/manuscript_review_panel.json"]),
        "revision_plan": _glob_many([root], ["reviews/revision_plan.json"]),
        "submission_packages": _glob_many([root], ["submission/packages/*/submission_package.json"]),
    }


def _fake_citation_blockers(state: ManuscriptState, bibliography: BibliographyRecord | None) -> list[str]:
    blockers: list[str] = []
    entries = bibliography.entries if bibliography else []
    unresolved = unresolved_citation_keys(state, entries)
    for key in unresolved:
        if suspicious_citation_string(key):
            blockers.append(f"Unresolved fake-looking citation `{key}` remains in manuscript claims.")
        else:
            blockers.append(f"Unresolved citation key `{key}` remains in manuscript claims.")
    return blockers


def _unsupported_claim_blockers(traceability: ManuscriptTraceabilityReport | None, state: ManuscriptState | None) -> list[str]:
    blockers: list[str] = []
    if traceability is not None:
        blockers.extend(f"Unsupported manuscript claims remain: {item}" for item in traceability.unsupported_claims)
        blockers.extend(traceability.blocking_issues)
    if state is not None:
        for claim in state.claim_uses:
            if claim.support_status in {"unsupported", "uncertain", ""} and claim.support_status not in {"hypothesis", "speculation"}:
                blockers.append(f"Unsupported manuscript claims remain: {claim.claim_id}")
    return _unique(blockers)


def _fake_result_blockers(root: Path) -> list[str]:
    blockers: list[str] = []
    for path in _glob_many([root], ["**/*.json"]):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if _contains_fake_result_marker(payload):
            blockers.append(f"Fake result marker found in manuscript artifact `{path.relative_to(root)}`.")
    workspace_root = root.parents[1] / "experiment_workspaces"
    if workspace_root.exists():
        for path in _glob_many([workspace_root], ["**/results/*.json", "**/reports/*.json"]):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if _contains_fake_result_marker(payload):
                blockers.append(f"Fake result marker found in workspace artifact `{path.relative_to(workspace_root)}`.")
    return blockers


def _failed_experiment_blockers(root: Path, state: ManuscriptState | None) -> list[str]:
    if state is None:
        return []
    workspace_root = root.parents[1] / "experiment_workspaces" / state.manuscript.workspace_id
    failed_ids: list[str] = []
    if workspace_root.exists():
        for path in _glob_many([workspace_root], ["runs/execution-*.json"]):
            execution = _load_optional(ExperimentExecutionRecord, path)
            if execution and execution.status == "failed":
                failed_ids.append(execution.id)
    if not failed_ids:
        return []
    text = _manuscript_text(root).lower()
    if "failed" in text or "negative" in text or "limitation" in text:
        return []
    return [
        f"Failed or negative experiment `{execution_id}` is not acknowledged in manuscript/package text." for execution_id in failed_ids
    ]


def _camera_ready_blockers(packages: list[SubmissionPackage], revision: RevisionPlan | None) -> list[str]:
    camera_packages = [package for package in packages if package.package_type == "camera_ready" or package.status == "camera_ready"]
    if not camera_packages:
        return []
    if revision is None:
        return ["Camera-ready package exists but no revision plan was generated."]
    open_items = [item for item in revision.rebuttal_items if item.status in {"open", "deferred"}]
    blockers = [f"Camera-ready package blocked by unresolved rebuttal item `{item.id}`." for item in open_items]
    blockers.extend(
        f"Camera-ready submission package `{package.id}` is blocked." for package in camera_packages if package.status != "camera_ready"
    )
    return blockers


def _manuscript_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "bibliography_built": "Bibliography has not been built.",
        "manuscript_draft_generated": "No manuscript draft/section files were found.",
        "claim_traceability_report_generated": "Claim traceability report has not been generated.",
        "artifact_backed_asset_generated": "No artifact-backed figure or table has been generated.",
        "venue_checklist_generated": "Venue submission checklist has not been generated.",
        "artifact_evaluation_package_generated": "Artifact evaluation package has not been generated.",
        "reviewer_panel_generated": "Manuscript reviewer panel has not been generated.",
        "rebuttal_revision_plan_generated": "Rebuttal/revision plan has not been generated.",
        "submission_package_exported": "Submission package has not been exported.",
        "unsupported_claims_blocked": "Unsupported claims are not blocked.",
        "fake_citations_blocked": "Fake or unresolved citations are not blocked.",
        "no_fake_results_in_manuscript": "Fake results are present in manuscript artifacts.",
        "failed_negative_experiments_acknowledged": "Failed/negative experiments are hidden or unacknowledged.",
        "camera_ready_rebuttal_blockers_addressed": "Camera-ready package has unresolved rebuttal blockers.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _gate_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "deterministic_ci_passed": "Deterministic CI pass evidence is missing.",
        "v7_release_gate_passed_or_documented": "v0.7 release gate pass/documentation is missing.",
        "manuscript_project_created": "No manuscript project was found.",
        "bibliography_built": "No release-ready manuscript has a bibliography.",
        "manuscript_draft_generated": "No release-ready manuscript draft was generated.",
        "claim_traceability_report_generated": "No release-ready manuscript has a traceability report.",
        "artifact_backed_asset_generated": "No release-ready manuscript has an artifact-backed figure/table.",
        "venue_checklist_generated": "No release-ready manuscript has a venue checklist.",
        "artifact_evaluation_package_generated": "No release-ready manuscript has an artifact evaluation package.",
        "reviewer_panel_generated": "No release-ready manuscript has a reviewer panel.",
        "rebuttal_revision_plan_generated": "No release-ready manuscript has a rebuttal/revision plan.",
        "submission_package_exported": "No release-ready manuscript has an exported submission package.",
        "unsupported_claims_blocked": "Unsupported manuscript claims remain unblocked.",
        "fake_citations_blocked": "Fake or unresolved manuscript citations remain unblocked.",
        "no_fake_results_in_manuscript": "Fake result markers remain in manuscript/workspace artifacts.",
        "failed_negative_experiments_acknowledged": "Failed/negative experiments are not acknowledged.",
        "camera_ready_rebuttal_blockers_addressed": "Camera-ready package has unresolved reviewer/rebuttal blockers.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _gate_warnings(requirements: dict[str, bool]) -> list[str]:
    warnings: list[str] = []
    if not requirements.get("deterministic_ci_passed"):
        warnings.append("Write data/release_gate/deterministic_ci.json with passed=true after running deterministic CI.")
    if not requirements.get("v7_release_gate_passed_or_documented"):
        warnings.append("Run or document the v0.7 release gate before claiming v0.8 readiness.")
    return warnings


def _manuscript_warnings(state: ManuscriptState | None, packages: list[SubmissionPackage], revision: RevisionPlan | None) -> list[str]:
    warnings: list[str] = []
    if state is not None and state.manuscript.status not in {"review_ready", "submission_ready", "camera_ready", "drafting"}:
        warnings.append(f"Manuscript `{state.manuscript.id}` status is `{state.manuscript.status}`.")
    if packages and not any(package.status in {"review_ready", "submission_ready", "camera_ready"} for package in packages):
        warnings.append("Submission packages exist but none are ready for review/submission/camera-ready use.")
    if revision is not None and revision.status != "addressed":
        warnings.append(f"Revision plan status is `{revision.status}`.")
    return warnings


def _manuscript_text(root: Path) -> str:
    chunks: list[str] = []
    for path in _glob_many([root], ["sections/*.md", "submission/packages/*/*.md", "submission/packages/*/tables/*.md"]):
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(chunks)


def _glob_many(roots: list[Path], patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        for pattern in patterns:
            paths.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(paths))


def _load_json_dataclass(cls, path: Path):
    try:
        return from_dict(cls, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _load_optional(cls, paths: list[Path] | Path):
    if isinstance(paths, Path):
        return _load_json_dataclass(cls, paths)
    if not paths:
        return None
    return _load_json_dataclass(cls, paths[0])


def _json_passed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and (payload.get("passed") is True or payload.get("status") == "pass")


def _contains_fake_result_marker(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"fake_result", "fake_results"} and item is True:
                return True
            if normalized == "result_scope" and str(item).lower() == "fake":
                return True
            if _contains_fake_result_marker(item):
                return True
    if isinstance(value, list):
        return any(_contains_fake_result_marker(item) for item in value)
    return False


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
