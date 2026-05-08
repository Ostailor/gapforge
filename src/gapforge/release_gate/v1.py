"""v1 readiness gate for the v0.9 external pilot and accumulated release gates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.pilots import PilotStore

AUDIT_FILES = {
    "migration_audit_passed": "migration_audit.json",
    "cli_audit_passed": "cli_audit.json",
    "docs_audit_passed": "docs_audit.json",
    "artifact_hygiene_audit_passed": "artifact_hygiene_audit.json",
}


@dataclass(slots=True)
class V1ReadinessResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    next_commands: list[str] = field(default_factory=list)
    pilot_id: str = ""
    pilot_outcome_type: str = "unknown"
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V1ReadinessGate:
    """Machine-check whether GapForge can move from v0.9 to v1."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"

    def evaluate(self) -> V1ReadinessResult:
        pilot = self._accepted_pilot()
        product_failures = self._product_failures()
        report_paths = self._full_project_reports()
        audit_paths = {name: self.release_dir / filename for name, filename in AUDIT_FILES.items()}
        migration_audit_payload = _read_json_object(audit_paths["migration_audit_passed"])
        requirements = {
            "v4_codex_workflow_gate_passed": _json_passed(self.release_dir / "v0.4_latest.json"),
            "v5_real_literature_quality_gate_passed": _json_passed(self.release_dir / "v0.5_latest.json"),
            "v6_empirical_validation_gate_passed": _json_passed(self.release_dir / "v0.6_latest.json"),
            "v7_benchmark_replication_gate_passed": _json_passed(self.release_dir / "v0.7_latest.json"),
            "v8_manuscript_submission_gate_passed": _json_passed(self.release_dir / "v0.8_latest.json"),
            "v09_pilot_accepted_as_direction_or_refusal": pilot["accepted"]
            and pilot["outcome_type"] in {"defensible_direction", "correct_refusal"},
            "compatibility_audit_v2_passed": _migration_audit_v2_passed(migration_audit_payload),
            "no_unresolved_product_failures": not product_failures,
            "cli_audit_passed": _json_passed(audit_paths["cli_audit_passed"]),
            "docs_audit_passed": _json_passed(audit_paths["docs_audit_passed"]),
            "artifact_hygiene_audit_passed": _json_passed(audit_paths["artifact_hygiene_audit_passed"]),
        }
        blockers = _requirement_blockers(requirements)
        blockers.extend(f"Unresolved product failure: {failure}" for failure in product_failures)
        blockers = _dedupe(blockers)
        passed = not blockers and all(requirements.values())
        recommended_next_version = "v1" if passed else "v0.9.1" if product_failures else "v0.9"
        status = "pass" if passed else "blocked" if product_failures else "incomplete"
        warnings = _warnings(requirements, recommended_next_version, migration_audit_payload)
        if migration_audit_payload.get("status") == "warning":
            warnings.extend(str(warning) for warning in migration_audit_payload.get("warnings", []))
        next_commands = _next_commands(requirements, product_failures)
        artifact_paths = {
            "release_gate_reports": [str(self.release_dir / f"v0.{version}_latest.json") for version in range(4, 9)],
            "audit_reports": [str(path) for path in audit_paths.values() if path.exists()],
            "full_project_reports": [str(path) for path in report_paths],
            "pilot_reviews": pilot["review_paths"],
        }
        return V1ReadinessResult(
            passed=passed,
            status=status,
            recommended_next_version=recommended_next_version,
            requirements=requirements,
            blockers=blockers,
            warnings=_dedupe(warnings),
            next_commands=next_commands,
            pilot_id=pilot["pilot_id"],
            pilot_outcome_type=pilot["outcome_type"],
            artifact_paths=artifact_paths,
        )

    def write_outputs(self, result: V1ReadinessResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v1_readiness_latest.json"
        data_md_path = self.release_dir / "v1-readiness-latest.md"
        report = render_v1_readiness_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v1-readiness-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _accepted_pilot(self) -> dict[str, Any]:
        store = PilotStore(self.config)
        accepted: dict[str, Any] = {
            "accepted": False,
            "pilot_id": "",
            "outcome_type": "unknown",
            "external_review_exists": False,
            "review_paths": [],
        }
        for record in self._pilot_records(store):
            reviews = store.load_external_reviews(record.id)
            summary = store.load_acceptance(record.id)
            review_paths = [str(store.record_dir(record.id) / "external_reviews" / f"{review.id}.json") for review in reviews]
            if summary.passed and summary.outcome_type in {"defensible_direction", "correct_refusal"} and reviews:
                return {
                    "accepted": True,
                    "pilot_id": record.id,
                    "outcome_type": summary.outcome_type,
                    "external_review_exists": True,
                    "review_paths": review_paths,
                }
            if reviews and not accepted["external_review_exists"]:
                accepted = {
                    "accepted": False,
                    "pilot_id": record.id,
                    "outcome_type": summary.outcome_type,
                    "external_review_exists": True,
                    "review_paths": review_paths,
                }
        return accepted

    def _pilot_records(self, store: PilotStore):
        root = self.config.data_dir / "pilots"
        if not root.exists():
            return []
        records = []
        for path in sorted(root.glob("*/pilot_run_record.json")):
            try:
                records.append(store.load_record(path.parent.name))
            except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return records

    def _product_failures(self) -> list[str]:
        failures: list[str] = []
        root = self.config.data_dir / "pilots"
        if root.exists():
            for path in sorted(root.glob("*/pilot_run_record.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                text = " ".join(
                    [
                        str(payload.get("id", path.parent.name)),
                        str(payload.get("status", "")),
                        str(payload.get("outcome_type", "")),
                        *[str(item) for item in payload.get("blockers", []) if isinstance(payload.get("blockers", []), list)],
                    ]
                ).lower()
                if "product_failure" in text or "product failure" in text:
                    failures.append(str(payload.get("id", path.parent.name)))
        for path in sorted(self.release_dir.glob("v0.*_latest.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            blockers = payload.get("blockers", []) if isinstance(payload, dict) else []
            if isinstance(blockers, list):
                for blocker in blockers:
                    if "product failure" in str(blocker).lower() or "product_failure" in str(blocker).lower():
                        failures.append(f"{path.name}: {blocker}")
        return _dedupe(failures)

    def _full_project_reports(self) -> list[Path]:
        roots = [root for root in [self.config.project_root, self.config.data_dir, self.config.runs_dir] if root.exists()]
        patterns = [
            "**/reports/final_pilot_report.md",
            "**/final_pilot_report.md",
            "**/pilot_report.md",
            "**/final_report.md",
        ]
        paths: list[Path] = []
        for root in roots:
            for pattern in patterns:
                paths.extend(path for path in root.glob(pattern) if path.is_file())
        return sorted(set(paths))


def render_v1_readiness_markdown(result: V1ReadinessResult) -> str:
    lines = [
        "# GapForge v1 Readiness Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Pilot: `{result.pilot_id or 'missing'}`",
        f"- Pilot outcome: `{result.pilot_outcome_type}`",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Next Commands", ""])
    lines.extend([f"- `{command}`" for command in result.next_commands] or ["- none"])
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    return "\n".join(lines).rstrip() + "\n"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _json_passed(path: Path) -> bool:
    payload = _read_json_object(path)
    if not payload:
        return False
    return payload.get("passed") is True or payload.get("status") == "pass"


def _migration_audit_v2_passed(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    if payload.get("audit_version") != 2:
        return False
    if payload.get("passed") is not True:
        return False
    if payload.get("status") not in {"pass", "warning"}:
        return False
    blockers = payload.get("blockers", [])
    if isinstance(blockers, list) and blockers:
        return False
    try:
        return int(payload.get("migration_failure_count", 0) or 0) == 0
    except (TypeError, ValueError):
        return False


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "v4_codex_workflow_gate_passed": "v0.4 Codex workflow gate has not passed.",
        "v5_real_literature_quality_gate_passed": "v0.5 real-literature quality gate has not passed.",
        "v6_empirical_validation_gate_passed": "v0.6 empirical validation gate has not passed.",
        "v7_benchmark_replication_gate_passed": "v0.7 benchmark/replication gate has not passed.",
        "v8_manuscript_submission_gate_passed": "v0.8 manuscript/submission gate has not passed.",
        "v09_pilot_accepted_as_direction_or_refusal": "No accepted defensible-direction or correct-refusal v0.9 pilot was found.",
        "compatibility_audit_v2_passed": "Migration/backward compatibility audit v2 has not passed.",
        "no_unresolved_product_failures": "Unresolved product failures remain.",
        "cli_audit_passed": "CLI workflow audit has not passed.",
        "docs_audit_passed": "Documentation usability audit has not passed.",
        "artifact_hygiene_audit_passed": "Artifact hygiene audit has not passed.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _warnings(requirements: dict[str, bool], recommended_next_version: str, migration_audit: dict[str, Any] | None = None) -> list[str]:
    warnings: list[str] = []
    if recommended_next_version == "v0.9.1":
        warnings.append("A product failure blocks v1; fix it in v0.9.1 before rechecking readiness.")
    elif recommended_next_version == "v0.9":
        warnings.append("Readiness evidence is incomplete; finish v0.9 audits or pilot acceptance before claiming v1.")
    if not requirements.get("v09_pilot_accepted_as_direction_or_refusal"):
        warnings.append("Only accepted defensible-direction and correct-refusal pilot outcomes can count toward v1 readiness.")
    if migration_audit and migration_audit.get("audit_version") == 2 and migration_audit.get("status") == "warning":
        warnings.append("Migration audit passed curated compatibility with non-blocking warnings; inspect migration_audit.json.")
    return warnings


def _next_commands(requirements: dict[str, bool], product_failures: list[str]) -> list[str]:
    commands_by_requirement = {
        "v4_codex_workflow_gate_passed": "gapforge v4-release-gate --write-report",
        "v5_real_literature_quality_gate_passed": "gapforge v5-release-gate --write-report",
        "v6_empirical_validation_gate_passed": "gapforge v6-release-gate --write-report",
        "v7_benchmark_replication_gate_passed": "gapforge v7-release-gate --write-report",
        "v8_manuscript_submission_gate_passed": "gapforge v8-release-gate --write-report",
        "v09_pilot_accepted_as_direction_or_refusal": "gapforge v9-release-gate --write-report",
        "compatibility_audit_v2_passed": "gapforge compatibility-audit --v2 --fixtures --local --write-report",
        "cli_audit_passed": "gapforge cli-audit --write-report",
        "docs_audit_passed": "gapforge docs-audit --write-report",
        "artifact_hygiene_audit_passed": "gapforge artifact-hygiene --all --write-report",
    }
    commands = [command for requirement, command in commands_by_requirement.items() if not requirements.get(requirement, False)]
    if product_failures:
        commands.append("gapforge v9-release-gate --write-report")
    if commands:
        commands.append("gapforge v1-readiness --write-report --json")
    return _dedupe(commands)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
