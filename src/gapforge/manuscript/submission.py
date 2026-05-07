"""Submission package export for manuscript projects."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.anonymization import render_anonymization_report_markdown
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import SUBMISSION_PACKAGE_TYPES, AnonymizationReport, ManuscriptState, SubmissionPackage
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager, render_submission_checklist_markdown
from gapforge.manuscript.venues import get_venue_template
from gapforge.models import ArtifactEvaluationPackage, Provenance, from_dict, to_plain
from gapforge.replication.package import ReplicationPackageExporter
from gapforge.state import slugify, utc_now_iso


class SubmissionPackageExporter:
    """Export gated, auditable manuscript submission packages."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.checklist_manager = SubmissionChecklistManager(config)

    def export(self, manuscript_id: str, package_type: str) -> SubmissionPackage:
        if package_type not in SUBMISSION_PACKAGE_TYPES:
            allowed = ", ".join(sorted(SUBMISSION_PACKAGE_TYPES))
            raise ValueError(f"Unsupported submission package type: {package_type}. Expected one of: {allowed}")
        state = self.manuscript_manager.load_state(manuscript_id)
        template_id = "arxiv_preprint" if package_type == "arxiv" else state.manuscript.target_venue or "generic_conference"
        template = get_venue_template(template_id)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        package_id = f"submission-{slugify(manuscript_id)}-{slugify(package_type)}"
        package_dir = root / "submission" / "packages" / package_id
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True, exist_ok=True)

        checklist = self.checklist_manager.build(manuscript_id)
        blockers = _package_blockers(self.config, root, state, package_type, template.anonymization_required, checklist.blocking_issues)
        status = _package_status(package_type, blockers, checklist.status)
        artifact_package = _latest_artifact_package(root)
        anonymization_report_id = _write_anonymization_report(root, package_dir, template.anonymization_required)

        _write_manuscript_files(root, package_dir, state, template.format)
        _copy_optional_dir(root / "bibliography", package_dir / "bibliography")
        _copy_optional_dir(root / "figures", package_dir / "figures")
        _copy_optional_dir(root / "tables", package_dir / "tables")
        _write_appendix(root, package_dir, state)
        _write_limitations(root, package_dir, state)
        _write_checklist(package_dir, checklist)
        _write_artifact_evaluation(package_dir, artifact_package)
        _write_replication_instructions(self.config, state, package_dir, artifact_package)
        _write_status(package_dir, package_type, status, blockers, checklist.status)

        package = SubmissionPackage(
            id=package_id,
            manuscript_id=manuscript_id,
            venue_template_id=template.id,
            package_type=package_type,
            files=[],
            checklist_id=f"submission-checklist-{manuscript_id}",
            anonymization_report_id=anonymization_report_id,
            artifact_package_id=artifact_package.id if artifact_package else "",
            status=status,
            provenance=Provenance(
                created_by_skill="submission-package",
                source_ids=[
                    manuscript_id,
                    template.id,
                    checklist.manuscript_id,
                    artifact_package.id if artifact_package else "",
                ],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Exported a manuscript submission package from manuscript, bibliography, asset, checklist, "
                    "anonymization, artifact evaluation, and replication state without fabricating readiness."
                ),
            ),
        )
        package.files = _relative_files(package_dir)
        (package_dir / "submission_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        (package_dir / "README.md").write_text(render_submission_package_markdown(package, blockers), encoding="utf-8")
        package.files = _relative_files(package_dir)
        (package_dir / "submission_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def load(self, package_id: str) -> SubmissionPackage:
        return load_submission_package(self.config, package_id)

    def package_dir(self, package_id: str) -> Path:
        return submission_package_dir(self.config, package_id)

    def status_markdown(self, package_id: str) -> str:
        package = self.load(package_id)
        status_path = self.package_dir(package_id) / "PACKAGE_STATUS.md"
        if status_path.exists():
            return status_path.read_text(encoding="utf-8")
        return render_submission_package_markdown(package, [])


def load_submission_package(config: GapForgeConfig, package_id: str) -> SubmissionPackage:
    path = submission_package_dir(config, package_id) / "submission_package.json"
    return from_dict(SubmissionPackage, json.loads(path.read_text(encoding="utf-8")))


def submission_package_dir(config: GapForgeConfig, package_id: str) -> Path:
    for path in config.project_root.glob(f"*/manuscripts/*/submission/packages/{package_id}/submission_package.json"):
        return path.parent
    raise FileNotFoundError(f"No submission package found for {package_id}")


def render_submission_package_markdown(package: SubmissionPackage, blockers: list[str]) -> str:
    lines = [
        f"# Submission Package `{package.id}`",
        "",
        f"- Manuscript ID: `{package.manuscript_id}`",
        f"- Venue template: `{package.venue_template_id}`",
        f"- Package type: `{package.package_type}`",
        f"- Status: `{package.status}`",
        f"- Checklist: `{package.checklist_id}`",
        f"- Anonymization report: `{package.anonymization_report_id or 'not included'}`",
        f"- Artifact evaluation package: `{package.artifact_package_id or 'not included'}`",
        f"- Files: {len(package.files)}",
        "",
    ]
    if blockers:
        lines.extend(["## Blocking Issues", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("No package blockers recorded.")
    return "\n".join(lines).rstrip() + "\n"


def _package_blockers(
    config: GapForgeConfig,
    root: Path,
    state: ManuscriptState,
    package_type: str,
    anonymization_required: bool,
    checklist_blockers: list[str],
) -> list[str]:
    if package_type == "internal":
        return []
    blockers = list(checklist_blockers)
    if package_type == "review" and anonymization_required and not _has_anonymization_ready(root):
        blockers.append("Review package requires anonymization for this venue.")
    if package_type == "camera_ready":
        blockers.extend(_camera_ready_blockers(config, state.manuscript.id))
    return _unique(blockers)


def _camera_ready_blockers(config: GapForgeConfig, manuscript_id: str) -> list[str]:
    root = ManuscriptManager(config).manuscript_root(manuscript_id)
    revision_path = root / "reviews" / "revision_plan.json"
    if not revision_path.exists():
        return []
    revision = ManuscriptRebuttalManager(config).load_revision(manuscript_id)
    open_items = [item for item in revision.rebuttal_items if item.status in {"open", "deferred"}]
    return [f"Camera-ready package blocked by unresolved rebuttal item `{item.id}`." for item in open_items]


def _package_status(package_type: str, blockers: list[str], checklist_status: str) -> str:
    if package_type == "internal":
        return "internal_review" if blockers else f"internal_{checklist_status}"
    if blockers:
        return "blocked"
    if package_type == "camera_ready":
        return "camera_ready"
    if package_type == "arxiv":
        return "submission_ready"
    return "review_ready"


def _write_manuscript_files(root: Path, package_dir: Path, state: ManuscriptState, manuscript_format: str) -> None:
    markdown = _render_manuscript_markdown(root, state)
    (package_dir / "manuscript.md").write_text(markdown, encoding="utf-8")
    if manuscript_format == "latex":
        (package_dir / "manuscript.tex").write_text(_render_minimal_latex(state, markdown), encoding="utf-8")


def _render_manuscript_markdown(root: Path, state: ManuscriptState) -> str:
    lines = [f"# {state.manuscript.title}", ""]
    for section in state.sections:
        section_path = root / section.content_path
        if section_path.exists():
            lines.append(section_path.read_text(encoding="utf-8").rstrip())
        else:
            lines.extend([f"## {section.title}", "", "_Section file missing in manuscript workspace._"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_minimal_latex(state: ManuscriptState, markdown: str) -> str:
    escaped_title = _latex_escape(state.manuscript.title)
    body = "\n".join(_latex_escape(line) for line in markdown.splitlines())
    return (
        "\\documentclass{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        f"\\title{{{escaped_title}}}\n"
        "\\date{}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\begin{verbatim}\n"
        f"{body}\n"
        "\\end{verbatim}\n"
        "\\end{document}\n"
    )


def _write_appendix(root: Path, package_dir: Path, state: ManuscriptState) -> None:
    appendix_sections = [section for section in state.sections if section.section_type == "appendix"]
    lines = ["# Appendix", ""]
    if appendix_sections:
        for section in appendix_sections:
            section_path = root / section.content_path
            lines.append(section_path.read_text(encoding="utf-8").rstrip() if section_path.exists() else f"## {section.title}\n\nMissing.")
    else:
        lines.append("No appendix section is currently recorded.")
    (package_dir / "appendix.md").write_text("\n\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_limitations(root: Path, package_dir: Path, state: ManuscriptState) -> None:
    limitations = [section for section in state.sections if section.section_type == "limitations"]
    if not limitations:
        (package_dir / "limitations.md").write_text("# Limitations\n\nNo limitations section is currently recorded.\n", encoding="utf-8")
        return
    parts = ["# Limitations", ""]
    for section in limitations:
        section_path = root / section.content_path
        parts.append(section_path.read_text(encoding="utf-8").rstrip() if section_path.exists() else f"## {section.title}\n\nMissing.")
    (package_dir / "limitations.md").write_text("\n\n".join(parts).rstrip() + "\n", encoding="utf-8")


def _write_checklist(package_dir: Path, checklist) -> None:
    (package_dir / "checklist_report.md").write_text(render_submission_checklist_markdown(checklist), encoding="utf-8")
    (package_dir / "checklist_report.json").write_text(json.dumps(to_plain(checklist), indent=2) + "\n", encoding="utf-8")


def _write_anonymization_report(root: Path, package_dir: Path, required: bool) -> str:
    if not required:
        return ""
    report_path = root / "submission" / "anonymization_report.json"
    if report_path.exists():
        report = from_dict(AnonymizationReport, json.loads(report_path.read_text(encoding="utf-8")))
        (package_dir / "anonymization_report.md").write_text(render_anonymization_report_markdown(report), encoding="utf-8")
        (package_dir / "anonymization_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        return f"anonymization-report-{report.manuscript_id}"
    status_path = root / "submission" / "anonymization.json"
    if not status_path.exists():
        return ""
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or "").lower()
    if status not in {"ready", "anonymized"} and payload.get("anonymized") is not True:
        return ""
    lines = [
        "# Anonymization Report",
        "",
        "Anonymization is recorded by manuscript submission status rather than a full scan report.",
        "",
        f"- Status: `{status or 'ready'}`",
    ]
    if payload.get("notes"):
        lines.append(f"- Notes: {payload['notes']}")
    (package_dir / "anonymization_report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (package_dir / "anonymization_report.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return "anonymization-status"


def _write_artifact_evaluation(package_dir: Path, artifact_package: ArtifactEvaluationPackage | None) -> None:
    from gapforge.artifact_eval.package import render_artifact_evaluation_package_markdown

    artifact_dir = package_dir / "artifact_evaluation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if artifact_package is None:
        (artifact_dir / "README.md").write_text(
            "# Artifact Evaluation\n\nNo artifact evaluation package is currently recorded.\n", encoding="utf-8"
        )
        return
    (artifact_dir / "README.md").write_text(render_artifact_evaluation_package_markdown(artifact_package), encoding="utf-8")


def _write_replication_instructions(
    config: GapForgeConfig,
    state: ManuscriptState,
    package_dir: Path,
    artifact_package: ArtifactEvaluationPackage | None,
) -> None:
    try:
        replication = ReplicationPackageExporter(config).latest_for_workspace(state.manuscript.workspace_id)
    except FileNotFoundError:
        replication = None
    lines = [
        "# Replication Instructions",
        "",
        "Replication files are referenced from the workspace/package state and should be shared according to data restrictions.",
        "",
    ]
    if replication is None:
        lines.append("- No replication package is currently recorded.")
    else:
        lines.extend(
            [
                f"- Replication package: `{replication.id}`",
                f"- Manifest path: `{replication.manifest_path}`",
                f"- Safe to share: `{str(replication.safe_to_share).lower()}`",
            ]
        )
    if artifact_package is not None:
        lines.append(f"- Artifact evaluation package: `{artifact_package.id}`")
    (package_dir / "replication_instructions.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_status(package_dir: Path, package_type: str, status: str, blockers: list[str], checklist_status: str) -> None:
    lines = [
        "# Submission Package Status",
        "",
        f"- Package type: `{package_type}`",
        f"- Status: `{status}`",
        f"- Checklist status: `{checklist_status}`",
        "",
    ]
    if package_type == "internal":
        lines.append("Internal packages are less strict and must not be treated as submission-ready without passing gates.")
    if blockers:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)
    (package_dir / "PACKAGE_STATUS.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _copy_optional_dir(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    files = [path for path in source.rglob("*") if path.is_file()]
    if not files:
        return
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _latest_artifact_package(root: Path) -> ArtifactEvaluationPackage | None:
    paths = sorted(root.glob("artifact_evaluation/*/artifact_evaluation_package.json"))
    if not paths:
        return None
    return from_dict(ArtifactEvaluationPackage, json.loads(paths[-1].read_text(encoding="utf-8")))


def _has_anonymization_ready(root: Path) -> bool:
    report_path = root / "submission" / "anonymization_report.json"
    if report_path.exists():
        report = from_dict(AnonymizationReport, json.loads(report_path.read_text(encoding="utf-8")))
        return report.status in {"pass", "warning"}
    status_path = root / "submission" / "anonymization.json"
    if not status_path.exists():
        return False
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    status = str(payload.get("status") or "").lower()
    return status in {"ready", "anonymized"} or payload.get("anonymized") is True


def _relative_files(package_dir: Path) -> list[str]:
    return sorted(str(path.relative_to(package_dir)) for path in package_dir.rglob("*") if path.is_file())


def _latex_escape(value: str) -> str:
    return value.replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%").replace("$", "\\$")


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
