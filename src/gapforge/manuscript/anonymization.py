"""Blind-review anonymization support for manuscript projects."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import AnonymizationReport, IdentityLeak, ManuscriptState
from gapforge.manuscript.venues import get_venue_template
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

SCAN_GLOBS = ["sections/*.md", "figures/*.md", "tables/*.md", "bibliography/*.bib", "bibliography/*.md", "submission/*.md"]
PATH_PATTERN = re.compile(r"(?:(?:/Users|/home|/private/var|/tmp)/[^\s)\\\]}`]+|[A-Za-z]:\\[^\s)\\\]}`]+)")
REPO_URL_PATTERN = re.compile(r"https?://(?:www\.)?(?:github|gitlab|bitbucket)\.com/[^\s)\\\]}`]+", re.IGNORECASE)


class ManuscriptAnonymizer:
    """Create anonymized manuscript submission copies and report identity leaks."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)

    def anonymize(self, manuscript_id: str) -> AnonymizationReport:
        state = self.manuscript_manager.load_state(manuscript_id)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        output_dir = root / "submission" / "anonymized"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        replacements = _replacement_map(self.config, state)
        anonymized_paths: list[str] = []
        for source in _candidate_paths(root):
            relative = source.relative_to(root)
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(_anonymize_text(source.read_text(encoding="utf-8"), replacements), encoding="utf-8")
            anonymized_paths.append(str(destination.relative_to(root)))
        report = self._build_report(state, scan_root=output_dir, anonymized_paths=anonymized_paths, mode="anonymize")
        self._write_report(root, report)
        return report

    def check(self, manuscript_id: str) -> AnonymizationReport:
        state = self.manuscript_manager.load_state(manuscript_id)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        report = self._build_report(state, scan_root=root, anonymized_paths=[], mode="check")
        self._write_report(root, report)
        return report

    def deanonymize_package(self, manuscript_id: str) -> AnonymizationReport:
        state = self.manuscript_manager.load_state(manuscript_id)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        output_dir = root / "submission" / "deanonymized"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        copied_paths: list[str] = []
        for source in _candidate_paths(root):
            relative = source.relative_to(root)
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied_paths.append(str(destination.relative_to(root)))
        report = self._build_report(state, scan_root=output_dir, anonymized_paths=copied_paths, mode="deanonymize")
        self._write_report(root, report, filename="deanonymization_report.json")
        return report

    def load_report(self, manuscript_id: str) -> AnonymizationReport:
        path = self.manuscript_manager.manuscript_root(manuscript_id) / "submission" / "anonymization_report.json"
        if not path.exists():
            raise FileNotFoundError(f"No anonymization report found for {manuscript_id}")
        return from_dict(AnonymizationReport, json.loads(path.read_text(encoding="utf-8")))

    def render_markdown(self, report: AnonymizationReport) -> str:
        return render_anonymization_report_markdown(report)

    def _build_report(
        self,
        state: ManuscriptState,
        *,
        scan_root: Path,
        anonymized_paths: list[str],
        mode: str,
    ) -> AnonymizationReport:
        anonymous = _venue_requires_anonymity(state)
        configured = _identity_config(self.config, state)
        leaks: list[IdentityLeak] = []
        for path in _candidate_paths(scan_root):
            relative = path.relative_to(scan_root)
            leaks.extend(_detect_text_leaks(path.read_text(encoding="utf-8"), str(relative), configured, anonymous=anonymous))
        leaks.extend(_self_citation_leaks(self.config, state, configured, anonymous=anonymous))
        warnings: list[str] = []
        if not anonymous and leaks:
            warnings.append(
                "Venue does not require anonymization; leaks are reported for visibility but do not block submission readiness."
            )
        if mode == "deanonymize":
            warnings.append("Deanonymized package intentionally preserves manuscript identity details.")
        status = _status(leaks, anonymous=anonymous)
        return AnonymizationReport(
            manuscript_id=state.manuscript.id,
            anonymized_paths=anonymized_paths,
            detected_identity_leaks=_dedupe_leaks(leaks),
            warnings=warnings,
            status=status,
            provenance=Provenance(
                created_by_skill="manuscript-anonymization",
                source_ids=[state.manuscript.id, state.manuscript.target_venue],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Generated a blind-review anonymization report from manuscript copies; original manuscript artifacts were preserved."
                ),
            ),
        )

    def _write_report(self, root: Path, report: AnonymizationReport, *, filename: str = "anonymization_report.json") -> None:
        submission_dir = root / "submission"
        submission_dir.mkdir(parents=True, exist_ok=True)
        (submission_dir / filename).write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        markdown_name = filename.replace(".json", ".md")
        (submission_dir / markdown_name).write_text(render_anonymization_report_markdown(report), encoding="utf-8")
        if filename == "anonymization_report.json":
            (submission_dir / "anonymization.json").write_text(
                json.dumps({"status": "ready" if report.status in {"pass", "warning"} else "not_ready"}) + "\n",
                encoding="utf-8",
            )


def render_anonymization_report_markdown(report: AnonymizationReport) -> str:
    lines = [
        f"# Anonymization Report `{report.manuscript_id}`",
        "",
        f"- Status: `{report.status}`",
        f"- Anonymized paths: {len(report.anonymized_paths)}",
        f"- Identity leaks: {len(report.detected_identity_leaks)}",
        "",
    ]
    if report.anonymized_paths:
        lines.extend(["## Anonymized Paths", ""])
        lines.extend(f"- `{path}`" for path in report.anonymized_paths)
        lines.append("")
    if report.detected_identity_leaks:
        lines.extend(["## Identity Leaks", ""])
        for leak in report.detected_identity_leaks:
            lines.extend(
                [
                    f"- `{leak.leak_type}` ({leak.severity}) in `{leak.path}`: {leak.text_snippet}",
                    f"  Suggested fix: {leak.suggested_fix}",
                ]
            )
    else:
        lines.append("No identity leaks detected.")
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines).rstrip() + "\n"


def _candidate_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    excluded_parts = {"anonymized", "deanonymized"}
    for pattern in SCAN_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and not (set(path.relative_to(root).parts) & excluded_parts):
                paths.append(path)
    return paths


def _identity_config(config: GapForgeConfig, state: ManuscriptState) -> dict[str, list[str]]:
    root = ManuscriptManager(config).manuscript_root(state.manuscript.id)
    payload: dict[str, object] = {}
    config_path = root / "submission" / "anonymization_config.json"
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    program = ProjectMemoryManager(config).load_project(state.manuscript.project_id)
    author_names = _as_strings(payload.get("author_names"))
    affiliations = _as_strings(payload.get("affiliations"))
    project_names = _as_strings(payload.get("project_names")) or [program.project.name, program.project.id]
    repository_urls = _as_strings(payload.get("repository_urls"))
    return {
        "author_names": author_names,
        "affiliations": affiliations,
        "project_names": [item for item in project_names if item],
        "repository_urls": repository_urls,
    }


def _replacement_map(config: GapForgeConfig, state: ManuscriptState) -> dict[str, str]:
    identity = _identity_config(config, state)
    replacements = {
        "{{AUTHOR_NAMES}}": "Anonymous Authors",
        "{{AFFILIATION}}": "Anonymous Institution",
        "{{PROJECT_NAME}}": "Anonymous Project",
        "{{REPOSITORY_URL}}": "[anonymous repository withheld]",
    }
    replacements.update({name: "Anonymous Author" for name in identity["author_names"]})
    replacements.update({name: "Anonymous Institution" for name in identity["affiliations"]})
    replacements.update({name: "Anonymous Project" for name in identity["project_names"]})
    replacements.update({url: "[anonymous repository withheld]" for url in identity["repository_urls"]})
    return replacements


def _anonymize_text(text: str, replacements: dict[str, str]) -> str:
    anonymized = text
    for source, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if source:
            anonymized = anonymized.replace(source, replacement)
    anonymized = REPO_URL_PATTERN.sub("[anonymous repository withheld]", anonymized)
    anonymized = PATH_PATTERN.sub("[local path withheld]", anonymized)
    return anonymized


def _detect_text_leaks(text: str, path: str, identity: dict[str, list[str]], *, anonymous: bool) -> list[IdentityLeak]:
    leaks: list[IdentityLeak] = []
    if not path.startswith("bibliography/"):
        for name in identity["author_names"]:
            leaks.extend(
                _literal_leaks(
                    text,
                    path,
                    name,
                    "author_name",
                    "Remove or replace the author name for anonymous review.",
                    anonymous,
                )
            )
        for affiliation in identity["affiliations"]:
            leaks.extend(
                _literal_leaks(
                    text,
                    path,
                    affiliation,
                    "affiliation",
                    "Remove or replace the affiliation for anonymous review.",
                    anonymous,
                )
            )
    for url in identity["repository_urls"]:
        leaks.extend(
            _literal_leaks(
                text,
                path,
                url,
                "repository_url",
                "Use an anonymous repository URL or omit the link.",
                anonymous,
            )
        )
    for match in REPO_URL_PATTERN.finditer(text):
        leaks.append(
            _leak(
                path,
                match.group(0),
                "repository_url",
                _severity(anonymous),
                "Use an anonymous repository URL or omit the link.",
            )
        )
    for match in PATH_PATTERN.finditer(text):
        leaks.append(
            _leak(
                path,
                match.group(0),
                "path",
                _severity(anonymous),
                "Replace local filesystem paths with relative or anonymized paths.",
            )
        )
    return leaks


def _literal_leaks(
    text: str,
    path: str,
    needle: str,
    leak_type: str,
    suggested_fix: str,
    anonymous: bool,
) -> list[IdentityLeak]:
    if not needle:
        return []
    leaks: list[IdentityLeak] = []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    for match in pattern.finditer(text):
        leaks.append(_leak(path, _snippet(text, match.start(), match.end()), leak_type, _severity(anonymous), suggested_fix))
    return leaks


def _self_citation_leaks(
    config: GapForgeConfig,
    state: ManuscriptState,
    identity: dict[str, list[str]],
    *,
    anonymous: bool,
) -> list[IdentityLeak]:
    if not identity["author_names"]:
        return []
    try:
        bibliography = ManuscriptBibliographyManager(config).load(state.manuscript.id)
    except FileNotFoundError:
        return []
    author_names = {name.lower() for name in identity["author_names"]}
    leaks: list[IdentityLeak] = []
    for entry in bibliography.entries:
        if any(author.lower() in author_names for author in entry.authors):
            leaks.append(
                _leak(
                    "bibliography/bibliography.json",
                    f"{entry.citation_key}: {entry.title}",
                    "self_citation",
                    "warning" if anonymous else "info",
                    "For anonymous review, cite prior self-work in third person and remove identifying phrasing.",
                )
            )
    return leaks


def _leak(path: str, text: str, leak_type: str, severity: str, suggested_fix: str) -> IdentityLeak:
    normalized = " ".join(text.split())[:180]
    return IdentityLeak(
        id=f"identity-leak-{_slug(path)}-{leak_type}-{_slug(normalized)[:32]}",
        path=path,
        text_snippet=normalized,
        leak_type=leak_type,
        severity=severity,
        suggested_fix=suggested_fix,
        provenance=Provenance(
            created_by_skill="manuscript-anonymization",
            source_ids=[path],
            timestamp=utc_now_iso(),
            reasoning_summary="Detected a manuscript identity leak candidate for blind review.",
        ),
    )


def _snippet(text: str, start: int, end: int) -> str:
    return text[max(0, start - 60) : min(len(text), end + 60)]


def _venue_requires_anonymity(state: ManuscriptState) -> bool:
    if not state.manuscript.target_venue:
        return True
    return get_venue_template(state.manuscript.target_venue).anonymization_required


def _status(leaks: list[IdentityLeak], *, anonymous: bool) -> str:
    if anonymous and any(leak.severity in {"blocking", "high"} for leak in leaks):
        return "fail"
    if leaks:
        return "warning"
    return "pass"


def _severity(anonymous: bool) -> str:
    return "blocking" if anonymous else "info"


def _dedupe_leaks(leaks: list[IdentityLeak]) -> list[IdentityLeak]:
    result: list[IdentityLeak] = []
    seen: set[tuple[str, str, str]] = set()
    for leak in leaks:
        key = (leak.path, leak.leak_type, leak.text_snippet.lower())
        if key not in seen:
            result.append(leak)
            seen.add(key)
    return result


def _as_strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "identity"
