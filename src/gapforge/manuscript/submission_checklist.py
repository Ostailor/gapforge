"""Venue-aware manuscript submission readiness checklists."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.citations import unresolved_citation_keys
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import AnonymizationReport, ManuscriptState, SubmissionChecklist, VenueTemplate
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.manuscript.venues import get_venue_template
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.replication.package import ReplicationPackageExporter
from gapforge.state import utc_now_iso
from gapforge.venues.profiles import is_venue_profile


class SubmissionChecklistManager:
    """Build venue-aware submission readiness checklists without fabricating readiness."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.bibliography_manager = ManuscriptBibliographyManager(config)
        self.traceability_auditor = ManuscriptTraceabilityAuditor(config)
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def build(self, manuscript_id: str) -> SubmissionChecklist:
        state = self.manuscript_manager.load_state(manuscript_id)
        template, venue_warning = _venue_for_state(state)
        checks: dict[str, str] = {}
        blocking: list[str] = []
        warnings: list[str] = []
        if venue_warning:
            warnings.append(venue_warning)

        _check_required_sections(state, template, checks, blocking)
        _check_bibliography(self.bibliography_manager, state, checks, blocking, warnings)
        _check_traceability(self.traceability_auditor, state, checks, blocking)
        _check_result_artifacts(self.workspace_manager, state, checks, blocking)
        _check_artifact_package(self.config, state, template, checks, blocking, warnings)
        _check_ethics_and_limitations(state, template, checks, blocking)
        _check_anonymization(self.manuscript_manager.manuscript_root(manuscript_id), template, checks, blocking, warnings)

        if state.manuscript.status == "submission_ready" and blocking:
            blocking.append("Manuscript state is marked submission_ready while checklist blockers remain.")
        status = _status(blocking, warnings)
        checklist = SubmissionChecklist(
            manuscript_id=manuscript_id,
            venue_template_id=template.id,
            checks=checks,
            blocking_issues=_unique(blocking),
            warnings=_unique(warnings),
            status=status,
            provenance=Provenance(
                created_by_skill="submission-checklist",
                source_ids=[manuscript_id, template.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Computed venue-aware submission readiness from manuscript, bibliography, traceability, result, and package state."
                ),
            ),
        )
        self._write_checklist(checklist)
        return checklist

    def render_markdown(self, checklist: SubmissionChecklist) -> str:
        return render_submission_checklist_markdown(checklist)

    def _write_checklist(self, checklist: SubmissionChecklist) -> None:
        root = self.manuscript_manager.manuscript_root(checklist.manuscript_id)
        submission_dir = root / "submission"
        submission_dir.mkdir(parents=True, exist_ok=True)
        (submission_dir / "submission_checklist.json").write_text(
            json.dumps(to_plain(checklist), indent=2) + "\n",
            encoding="utf-8",
        )
        (submission_dir / "submission_checklist.md").write_text(render_submission_checklist_markdown(checklist), encoding="utf-8")


def render_submission_checklist_markdown(checklist: SubmissionChecklist) -> str:
    lines = [
        f"# Submission Checklist `{checklist.manuscript_id}`",
        "",
        f"- Venue template: `{checklist.venue_template_id}`",
        f"- Status: `{checklist.status}`",
        f"- Blocking issues: {len(checklist.blocking_issues)}",
        f"- Warnings: {len(checklist.warnings)}",
        "",
        "## Checks",
        "",
    ]
    for name, value in checklist.checks.items():
        lines.append(f"- `{name}`: {value}")
    if checklist.blocking_issues:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in checklist.blocking_issues)
    if checklist.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in checklist.warnings)
    return "\n".join(lines).rstrip() + "\n"


def _venue_for_state(state: ManuscriptState) -> tuple[VenueTemplate, str]:
    if state.manuscript.target_venue:
        return get_venue_template(state.manuscript.target_venue), ""
    return get_venue_template("generic_conference"), "No venue template was set; checked against generic_conference."


def _check_required_sections(
    state: ManuscriptState,
    template: VenueTemplate,
    checks: dict[str, str],
    blocking: list[str],
) -> None:
    present = {section.section_type for section in state.sections}
    missing = [section_type for section_type in template.sections_required if section_type not in present]
    checks["required_sections"] = "pass" if not missing else f"fail: missing {', '.join(missing)}"
    label = "venue profile" if is_venue_profile(template.id) else "venue"
    blocking.extend(f"Required section `{section_type}` is missing for {label} `{template.id}`." for section_type in missing)


def _check_bibliography(
    bibliography_manager: ManuscriptBibliographyManager,
    state: ManuscriptState,
    checks: dict[str, str],
    blocking: list[str],
    warnings: list[str],
) -> None:
    try:
        bibliography = bibliography_manager.load(state.manuscript.id)
    except FileNotFoundError:
        checks["bibliography"] = "fail: bibliography not built"
        checks["citations_valid"] = "fail: bibliography not built"
        blocking.append("Bibliography has not been built.")
        return
    unresolved = unresolved_citation_keys(state, bibliography.entries)
    checks["bibliography"] = "pass" if bibliography.entries else "fail: bibliography is empty"
    if not bibliography.entries:
        blocking.append("Bibliography is empty.")
    checks["citations_valid"] = "pass" if not unresolved else f"fail: unresolved {', '.join(unresolved)}"
    blocking.extend(f"Unresolved citation key `{key}` remains." for key in unresolved)
    for paper_id, fields in bibliography.missing_metadata.items():
        warnings.append(f"Bibliography entry `{paper_id}` is missing metadata: {', '.join(fields)}.")


def _check_traceability(
    auditor: ManuscriptTraceabilityAuditor,
    state: ManuscriptState,
    checks: dict[str, str],
    blocking: list[str],
) -> None:
    report = auditor.audit(state.manuscript.id)
    checks["claim_traceability"] = "pass" if not report.blocking_issues else f"fail: {len(report.blocking_issues)} blocker(s)"
    blocking.extend(report.blocking_issues)


def _check_result_artifacts(
    workspace_manager: ExperimentWorkspaceManager,
    state: ManuscriptState,
    checks: dict[str, str],
    blocking: list[str],
) -> None:
    result_claims = [claim_use for claim_use in state.claim_uses if claim_use.use_type == "result"]
    if not result_claims:
        checks["result_artifacts"] = "pass: no result claims"
        return
    artifact_ids = _workspace_result_artifact_ids(workspace_manager, state)
    linked_artifact_ids = {artifact_id for section in state.sections for artifact_id in section.source_artifact_ids}
    missing = sorted(linked_artifact_ids - artifact_ids)
    if not linked_artifact_ids:
        checks["result_artifacts"] = "fail: result claims have no linked artifacts"
        blocking.append("Result claims exist but no manuscript section links result artifacts.")
        return
    if missing:
        checks["result_artifacts"] = f"fail: unknown artifacts {', '.join(missing)}"
        blocking.extend(f"Linked result artifact `{artifact_id}` does not exist in the experiment workspace." for artifact_id in missing)
        return
    checks["result_artifacts"] = "pass"


def _check_artifact_package(
    config: GapForgeConfig,
    state: ManuscriptState,
    template: VenueTemplate,
    checks: dict[str, str],
    blocking: list[str],
    warnings: list[str],
) -> None:
    package_required = template.artifact_policy == "required"
    try:
        package = ReplicationPackageExporter(config).latest_for_workspace(state.manuscript.workspace_id)
    except FileNotFoundError:
        package = None
    if package is None:
        checks["artifact_package"] = "fail: missing" if package_required else "warn: missing"
        message = f"Venue `{template.id}` requires an artifact/replication package, but none exists."
        if package_required:
            blocking.append(message)
        elif template.artifact_policy == "expected":
            warnings.append("No artifact/replication package exists; reproducibility is expected or encouraged for this venue.")
        return
    if package_required and not package.safe_to_share:
        checks["artifact_package"] = "fail: package exists but is not safe to share"
        blocking.append("Artifact/replication package exists but is not safe to share.")
        return
    checks["artifact_package"] = "pass"


def _check_ethics_and_limitations(
    state: ManuscriptState,
    template: VenueTemplate,
    checks: dict[str, str],
    blocking: list[str],
) -> None:
    section_types = {section.section_type for section in state.sections}
    if "limitations" not in section_types:
        checks["limitations"] = "fail: limitations section missing"
        blocking.append("Limitations section is missing.")
    else:
        checks["limitations"] = "pass"
    if template.ethics_required and "ethics" not in section_types:
        checks["ethics"] = "fail: ethics section missing"
        blocking.append(f"Venue `{template.id}` requires an ethics section.")
    else:
        checks["ethics"] = "pass" if template.ethics_required else "pass: not required"


def _check_anonymization(
    manuscript_root: Path,
    template: VenueTemplate,
    checks: dict[str, str],
    blocking: list[str],
    warnings: list[str],
) -> None:
    if not template.anonymization_required:
        checks["anonymization"] = "pass: not required"
        return
    report_path = manuscript_root / "submission" / "anonymization_report.json"
    if report_path.exists():
        try:
            report = from_dict(AnonymizationReport, json.loads(report_path.read_text(encoding="utf-8")))
        except Exception:
            report = None
        if report is None:
            checks["anonymization"] = "fail: invalid anonymization report"
            blocking.append("Anonymization report exists but could not be loaded.")
            return
        if report.status == "fail":
            checks["anonymization"] = "fail: identity leaks detected"
            blocking.append("Anonymization report has blocking identity leaks.")
            return
        checks["anonymization"] = f"pass: report {report.status}"
        if report.status == "warning":
            warnings.append("Anonymization report has warning-level identity leaks.")
        warnings.extend(report.warnings)
        return
    path = manuscript_root / "submission" / "anonymization.json"
    if not path.exists():
        checks["anonymization"] = "fail: status missing"
        blocking.append(f"Venue `{template.id}` requires anonymization status, but `submission/anonymization.json` is missing.")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        checks["anonymization"] = "fail: invalid status file"
        blocking.append("Anonymization status file is invalid JSON.")
        return
    status = str(payload.get("status") or "").lower()
    if status not in {"ready", "anonymized"} and payload.get("anonymized") is not True:
        checks["anonymization"] = f"fail: {status or 'not_ready'}"
        blocking.append("Anonymization is required but not marked ready.")
        return
    checks["anonymization"] = "pass"
    if payload.get("notes"):
        warnings.append(f"Anonymization notes: {payload['notes']}")


def _workspace_result_artifact_ids(workspace_manager: ExperimentWorkspaceManager, state: ManuscriptState) -> set[str]:
    try:
        return {artifact.id for artifact in workspace_manager.list_result_artifacts(state.manuscript.workspace_id)}
    except FileNotFoundError:
        return set()


def _status(blocking: list[str], warnings: list[str]) -> str:
    if blocking:
        return "not_ready"
    if warnings:
        return "review_ready"
    return "submission_ready"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
