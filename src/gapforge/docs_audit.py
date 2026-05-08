"""Documentation usability audit for v0.9 and v1 readiness."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance
from gapforge.state import utc_now_iso


@dataclass(slots=True)
class DocsUsabilityAudit:
    passed: bool
    checks: dict[str, bool]
    missing_files: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    overclaim_findings: list[str] = field(default_factory=list)
    fake_evidence_findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="docs-audit"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DocsAuditor:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.docs_dir = config.root / "docs"

    def audit(self, *, write: bool = False) -> DocsUsabilityAudit:
        readme = self.config.root / "README.md"
        docs = self._markdown_files()
        corpus = _read_text(readme) + "\n" + "\n".join(_read_text(path) for path in docs)
        missing_files = _missing_files(
            [
                readme,
                self.docs_dir / "CODEX_QUICKSTART.md",
                self.docs_dir / "V0_5_REAL_LITERATURE_CAMPAIGNS.md",
                self.docs_dir / "V0_6_EXPERIMENT_EXECUTION.md",
                self.docs_dir / "V0_8_MANUSCRIPT_WORKFLOW.md",
                self.docs_dir / "V0_9_V1_READINESS.md",
                self.docs_dir / "KNOWN_LIMITATIONS.md",
            ]
        )
        checks = {
            "readme_has_v09_pilot_quickstart": _contains_all(
                _read_text(readme), ["v0.9 External Pilot", "pilot-run", "pilot-review", "v1-readiness"]
            ),
            "codex_quickstart_exists": (self.docs_dir / "CODEX_QUICKSTART.md").exists(),
            "real_literature_quickstart_exists": _contains_all(
                corpus, ["v0.5 Real Literature", "real-literature-run", "real-literature-review"]
            ),
            "experiment_quickstart_exists": _contains_all(corpus, ["v0.6", "experiment-workspace-create", "experiment-run"]),
            "manuscript_quickstart_exists": _contains_all(corpus, ["v0.8", "manuscript-create", "submission-package"]),
            "v1_readiness_docs_exist": (self.docs_dir / "V0_9_V1_READINESS.md").exists(),
            "limitations_visible": _contains_all(_read_text(self.docs_dir / "KNOWN_LIMITATIONS.md"), ["Known Limitations", "v0.9"]),
        }
        overclaim_findings = detect_overclaim_phrases(docs + [readme])
        fake_evidence_findings = detect_fake_evidence_presented_as_real(docs + [readme])
        checks["no_release_note_overclaims_acceptance"] = not overclaim_findings
        checks["no_fake_result_or_citation_examples_presented_as_real"] = not fake_evidence_findings
        missing_sections = [name for name, passed in checks.items() if not passed and name not in _finding_checks()]
        passed = not missing_files and not missing_sections and not overclaim_findings and not fake_evidence_findings
        audit = DocsUsabilityAudit(
            passed=passed,
            checks=checks,
            missing_files=missing_files,
            missing_sections=missing_sections,
            overclaim_findings=overclaim_findings,
            fake_evidence_findings=fake_evidence_findings,
            warnings=[] if passed else ["Documentation is not v1-ready until missing docs and overclaims are fixed."],
            provenance=Provenance(
                created_by_skill="docs-audit",
                source_ids=[str(path) for path in docs + [readme]],
                timestamp=utc_now_iso(),
                reasoning_summary="Checked new-user lifecycle docs and blocked overclaim/fake-evidence language.",
            ),
        )
        if write:
            self.write_outputs(audit)
        return audit

    def write_outputs(self, audit: DocsUsabilityAudit) -> tuple[Path, Path]:
        audit_dir = self.config.data_dir / "docs_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        json_path = audit_dir / "docs_audit_latest.json"
        md_path = audit_dir / "docs_audit_latest.md"
        report = render_docs_audit(audit)
        json_path.write_text(json.dumps(audit.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(report, encoding="utf-8")
        release_dir = self.config.data_dir / "release_gate"
        release_dir.mkdir(parents=True, exist_ok=True)
        release_payload = {
            "passed": audit.passed,
            "status": "pass" if audit.passed else "fail",
            "checks": audit.checks,
            "missing_files": audit.missing_files,
            "missing_sections": audit.missing_sections,
            "overclaim_findings": audit.overclaim_findings,
            "fake_evidence_findings": audit.fake_evidence_findings,
            "report_path": str(md_path),
        }
        (release_dir / "docs_audit.json").write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        return json_path, md_path

    def _markdown_files(self) -> list[Path]:
        if not self.docs_dir.exists():
            return []
        return sorted(path for path in self.docs_dir.rglob("*.md") if path.is_file())


def render_docs_audit(audit: DocsUsabilityAudit) -> str:
    lines = [
        "# GapForge Documentation Usability Audit",
        "",
        f"- Passed: {str(audit.passed).lower()}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in audit.checks.items())
    lines.extend(["", "## Missing Files", ""])
    lines.extend([f"- {item}" for item in audit.missing_files] or ["- none"])
    lines.extend(["", "## Missing Sections", ""])
    lines.extend([f"- {item}" for item in audit.missing_sections] or ["- none"])
    lines.extend(["", "## Overclaim Findings", ""])
    lines.extend([f"- {item}" for item in audit.overclaim_findings] or ["- none"])
    lines.extend(["", "## Fake Evidence Findings", ""])
    lines.extend([f"- {item}" for item in audit.fake_evidence_findings] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in audit.warnings] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def detect_overclaim_phrases(paths: list[Path]) -> list[str]:
    patterns = [
        re.compile(r"\bguarantees?\s+(novelty|publication|acceptance|venue acceptance)\b", re.IGNORECASE),
        re.compile(r"\bproves?\s+(novelty|publication readiness|venue acceptance|paper acceptance)\b", re.IGNORECASE),
        re.compile(r"\bpublication-ready\b", re.IGNORECASE),
        re.compile(r"\baccepted\s+(at|to)\s+(iclr|neurips|icml|acl|emnlp|cvpr|aaai|kdd|sigir)\b", re.IGNORECASE),
    ]
    return _detect_line_findings(paths, patterns, allow_negated=True)


def detect_fake_evidence_presented_as_real(paths: list[Path]) -> list[str]:
    patterns = [
        re.compile(r"\bfake\s+(citation|result)[^.\\n]*(accepted|real|valid|passes|passed)\b", re.IGNORECASE),
        re.compile(r"\b(accepted|real|valid|passes|passed)[^.\\n]*fake\s+(citation|result)\b", re.IGNORECASE),
        re.compile(r"\bfabricated\s+(citation|result)[^.\\n]*(accepted|real|valid|passes|passed)\b", re.IGNORECASE),
    ]
    return _detect_line_findings(paths, patterns, allow_negated=True)


def _detect_line_findings(paths: list[Path], patterns: list[re.Pattern[str]], *, allow_negated: bool) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            context = "\n".join(lines[max(0, number - 4) : number])
            if allow_negated and _is_negated_or_blocking_line(line, context):
                continue
            if any(pattern.search(line) for pattern in patterns):
                findings.append(f"{path}:{number}: {line.strip()}")
    return findings


def _is_negated_or_blocking_line(line: str, context: str = "") -> bool:
    lowered = f"{context}\n{line}".lower()
    safe_terms = [
        "not ",
        "no ",
        "never ",
        "must not",
        "does not",
        "do not",
        "cannot",
        "without",
        "blocked",
        "blocks",
        "rejected",
        "reject",
        "fails",
        "fail",
        "limitation",
        "non-goal",
        "not the same",
        "fail:",
        "regression",
        "fixture",
        "eval",
        "test",
    ]
    return any(term in lowered for term in safe_terms)


def _missing_files(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if not path.exists()]


def _contains_all(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def _finding_checks() -> set[str]:
    return {"no_release_note_overclaims_acceptance", "no_fake_result_or_citation_examples_presented_as_real"}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
