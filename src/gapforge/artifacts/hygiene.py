"""v1 artifact hygiene audit for generated and private project outputs."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import ProjectArtifactHygieneReport, Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.redaction import contains_secret
from gapforge.safety import audit_artifacts
from gapforge.state import utc_now_iso

DATASET_SUFFIXES = {".csv", ".jsonl", ".parquet", ".tsv", ".sqlite", ".sqlite3", ".db", ".npy", ".npz", ".arrow"}
TEXT_SUFFIXES = {".bib", ".csv", ".html", ".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}
TRANSCRIPT_NAMES = {"llm_transcripts.json", "llm_transcripts.md"}
LARGE_FILE_BYTES = 5 * 1024 * 1024
REQUIRED_GITIGNORE_PATTERNS = {
    "runs/*": "generated runs",
    "projects/*": "generated projects",
    "campaigns/*": "generated campaigns",
    "data/*": "generated data",
    "*.pdf": "PDF artifacts",
    "**/llm_transcripts.json": "JSON LLM transcripts",
    "**/llm_transcripts.md": "Markdown LLM transcripts",
    "**/dashboard/": "generated dashboards",
    "**/safe_bundles/": "safe bundle exports",
    ".gapforge_cache/": "source and retrieval cache",
    "artifacts/papers/": "downloaded paper artifacts",
}


@dataclass(slots=True)
class GitignoreVerification:
    passed: bool
    checked_patterns: list[str] = field(default_factory=list)
    missing_patterns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="verify-gitignore"))


class ArtifactHygieneAuditor:
    """Audit whether generated/private artifacts are safely ignored or packaged."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.gitignore_patterns = _load_gitignore_patterns(config.root / ".gitignore")

    def audit_project(self, project_id: str, *, write: bool = False) -> ProjectArtifactHygieneReport:
        program = ProjectMemoryManager(self.config).load_project(project_id)
        project_root = Path(program.project.root_dir)
        classifications = audit_artifacts(project_root)
        files = [path for path in sorted(project_root.rglob("*")) if path.is_file()]
        summary = {"ignored": 0, "not_ignored": 0, "safe_bundle": 0}
        blockers: list[str] = []
        generated_count = len(files)
        pdf_count = dataset_count = transcript_count = secret_risk_count = large_file_count = 0
        unsafe_paths: set[str] = set()

        for path in files:
            relative = path.relative_to(project_root)
            relative_text = relative.as_posix()
            repo_relative = _relative_to_root(path, self.config.root)
            safe_bundle = _is_safe_bundle_path(relative)
            ignored = safe_bundle or _is_ignored(repo_relative, self.gitignore_patterns)
            if safe_bundle:
                summary["safe_bundle"] += 1
            elif ignored:
                summary["ignored"] += 1
            else:
                summary["not_ignored"] += 1

            is_pdf = path.suffix.lower() == ".pdf"
            is_dataset = _is_dataset(path, relative)
            is_transcript = _is_transcript(path, relative)
            is_dashboard = _is_dashboard(path, relative)
            if is_pdf:
                pdf_count += 1
            if is_dataset:
                dataset_count += 1
            if is_transcript:
                transcript_count += 1
            if _has_secret_risk(path):
                secret_risk_count += 1
                unsafe_paths.add(relative_text)
                blockers.append(f"`{relative_text}` contains unredacted secret-like text.")
            if path.stat().st_size > LARGE_FILE_BYTES:
                large_file_count += 1
                if not ignored:
                    unsafe_paths.add(relative_text)
                    blockers.append(f"`{relative_text}` is a large generated artifact that is not ignored.")

            restricted = is_pdf or is_dataset or is_transcript
            if safe_bundle and restricted:
                unsafe_paths.add(relative_text)
                blockers.append(f"`{relative_text}` is a restricted artifact inside a safe bundle.")
            if not safe_bundle and restricted and not ignored:
                unsafe_paths.add(relative_text)
                blockers.append(f"`{relative_text}` is a restricted generated artifact that is not ignored.")
            if is_dashboard and not ignored:
                unsafe_paths.add(relative_text)
                blockers.append(f"`{relative_text}` is a generated dashboard that is not ignored.")

        for classification in classifications:
            if not classification.safe_to_commit and not _is_safe_bundle_text(classification.path):
                unsafe_paths.add(classification.path)

        gitignore = verify_gitignore_patterns(self.config)
        blockers.extend(
            f".gitignore missing `{pattern}` for {REQUIRED_GITIGNORE_PATTERNS[pattern]}." for pattern in gitignore.missing_patterns
        )

        report = ProjectArtifactHygieneReport(
            project_id=project_id,
            generated_artifact_count=generated_count,
            unsafe_to_commit_count=len(unsafe_paths),
            pdf_count=pdf_count,
            dataset_count=dataset_count,
            transcript_count=transcript_count,
            secret_risk_count=secret_risk_count,
            large_file_count=large_file_count,
            ignored_status_summary=summary,
            blockers=_dedupe(blockers),
            provenance=Provenance(
                created_by_skill="artifact-hygiene",
                source_ids=[project_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Checked generated/private artifacts, ignore coverage, safe bundles, secrets, and large files.",
            ),
        )
        if write:
            self.write_project_report(report)
        return report

    def audit_all(self, *, write: bool = False) -> list[ProjectArtifactHygieneReport]:
        reports = [self.audit_project(project.id, write=write) for project in ProjectMemoryManager(self.config).list_projects()]
        if write:
            self.write_release_gate_report(reports)
        return reports

    def write_project_report(self, report: ProjectArtifactHygieneReport) -> Path:
        report_dir = self.config.data_dir / "artifact_hygiene"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / f"{report.project_id}.json"
        md_path = report_dir / f"{report.project_id}.md"
        json_path.write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_artifact_hygiene_report([report]), encoding="utf-8")
        return json_path

    def write_release_gate_report(self, reports: list[ProjectArtifactHygieneReport]) -> Path:
        release_dir = self.config.data_dir / "release_gate"
        release_dir.mkdir(parents=True, exist_ok=True)
        gitignore = verify_gitignore_patterns(self.config)
        payload = {
            "passed": bool(reports) and gitignore.passed and all(not report.blockers for report in reports),
            "project_count": len(reports),
            "reports": to_plain(reports),
            "gitignore": to_plain(gitignore),
        }
        path = release_dir / "artifact_hygiene_audit.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (release_dir / "artifact_hygiene_audit.md").write_text(render_artifact_hygiene_report(reports), encoding="utf-8")
        return path


def build_project_artifact_hygiene_report(config: GapForgeConfig, project_id: str, *, write: bool = False) -> ProjectArtifactHygieneReport:
    return ArtifactHygieneAuditor(config).audit_project(project_id, write=write)


def verify_gitignore_patterns(config: GapForgeConfig) -> GitignoreVerification:
    patterns = _load_gitignore_patterns(config.root / ".gitignore")
    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in patterns]
    warnings = []
    if not (config.root / ".gitignore").exists():
        warnings.append(".gitignore does not exist.")
    return GitignoreVerification(
        passed=not missing,
        checked_patterns=sorted(REQUIRED_GITIGNORE_PATTERNS),
        missing_patterns=missing,
        warnings=warnings,
        provenance=Provenance(
            created_by_skill="verify-gitignore",
            timestamp=utc_now_iso(),
            reasoning_summary="Verified generated/private artifact ignore patterns needed before v1.",
        ),
    )


def render_artifact_hygiene_report(reports: list[ProjectArtifactHygieneReport]) -> str:
    passed = bool(reports) and all(not report.blockers for report in reports)
    lines = [
        "# GapForge Artifact Hygiene Audit",
        "",
        f"- Status: {'PASSED' if passed else 'FAILED'}",
        f"- Projects audited: {len(reports)}",
        "",
    ]
    if not reports:
        lines.extend(["## Blockers", "", "- No project artifact hygiene reports exist."])
    for report in reports:
        lines.extend(
            [
                f"## Project `{report.project_id}`",
                "",
                f"- Generated artifacts: {report.generated_artifact_count}",
                f"- Unsafe to commit: {report.unsafe_to_commit_count}",
                f"- PDFs: {report.pdf_count}",
                f"- Datasets: {report.dataset_count}",
                f"- Transcripts: {report.transcript_count}",
                f"- Secret risks: {report.secret_risk_count}",
                f"- Large files: {report.large_file_count}",
                f"- Ignored: {report.ignored_status_summary.get('ignored', 0)}",
                f"- Not ignored: {report.ignored_status_summary.get('not_ignored', 0)}",
                f"- Safe bundle files: {report.ignored_status_summary.get('safe_bundle', 0)}",
                "",
                "### Blockers",
                "",
            ]
        )
        if report.blockers:
            lines.extend(f"- {blocker}" for blocker in report.blockers)
        else:
            lines.append("- none")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_gitignore_verification(result: GitignoreVerification) -> str:
    lines = [
        "# GapForge Gitignore Verification",
        "",
        f"- Status: {'PASSED' if result.passed else 'FAILED'}",
        f"- Required patterns checked: {len(result.checked_patterns)}",
        "",
        "## Missing Patterns",
        "",
    ]
    if result.missing_patterns:
        lines.extend(f"- `{pattern}`: {REQUIRED_GITIGNORE_PATTERNS[pattern]}" for pattern in result.missing_patterns)
    else:
        lines.append("- none")
    if result.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines).rstrip() + "\n"


def _load_gitignore_patterns(path: Path) -> set[str]:
    if not path.exists():
        return set()
    patterns: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
            patterns.add(stripped)
    return patterns


def _is_ignored(relative_path: str, patterns: set[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    name = Path(normalized).name
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if _matches_gitignore_pattern(normalized, name, normalized_pattern):
            return True
    return False


def _matches_gitignore_pattern(path: str, name: str, pattern: str) -> bool:
    if pattern.endswith("/*") and (path == pattern[:-2] or path.startswith(pattern[:-1])):
        return True
    if pattern.endswith("/") and (path == pattern.rstrip("/") or path.startswith(pattern)):
        return True
    if pattern.startswith("**/") and pattern.endswith("/"):
        needle = f"/{pattern[3:]}"
        return path.endswith(pattern[3:-1]) or needle in f"/{path}/"
    if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern):
        return True
    return path == pattern


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_safe_bundle_path(relative: Path) -> bool:
    return "safe_bundles" in relative.parts or "safe_bundle" in relative.parts


def _is_safe_bundle_text(relative: str) -> bool:
    parts = Path(relative).parts
    return "safe_bundles" in parts or "safe_bundle" in parts


def _is_dataset(path: Path, relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    return path.suffix.lower() in DATASET_SUFFIXES and bool(parts & {"data", "dataset", "datasets", "dataset_cache"})


def _is_transcript(path: Path, relative: Path) -> bool:
    lower = relative.as_posix().lower()
    return path.name in TRANSCRIPT_NAMES or "transcript" in lower


def _is_dashboard(path: Path, relative: Path) -> bool:
    return "dashboard" in {part.lower() for part in relative.parts} or path.suffix.lower() == ".html"


def _has_secret_risk(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TRANSCRIPT_NAMES:
        return False
    try:
        sample = path.read_bytes()[:1_000_000].decode("utf-8", errors="ignore")
    except OSError:
        return False
    return contains_secret(sample)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
