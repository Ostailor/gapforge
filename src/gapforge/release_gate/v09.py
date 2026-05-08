"""v0.9 external-pilot release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.pilots import PilotStore, assess_pilot_outcome, get_pilot_spec
from gapforge.pilots.specs import LOW_FPR_COLLUSION, pilot_docs_dir

AUDIT_REPORTS = {
    "v1_readiness_report_generated": "v1_readiness_latest.json",
    "migration_audit_generated": "migration_audit.json",
    "cli_audit_generated": "cli_audit.json",
    "docs_audit_generated": "docs_audit.json",
    "artifact_hygiene_audit_generated": "artifact_hygiene_audit.json",
}


@dataclass(slots=True)
class V09ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    pilot_id: str = ""
    pilot_outcome_type: str = "unknown"
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V09ReleaseGateEnforcer:
    """Machine-check whether v0.9 validated the external pilot."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"

    def evaluate(self) -> V09ReleaseGateResult:
        spec = _load_spec()
        spec_docs = _pilot_spec_documents(self.config)
        store = PilotStore(self.config)
        record = None
        reviews = []
        summary = None
        outcome = None
        try:
            record = store.load_record(spec.id)
            reviews = store.load_external_reviews(record.id)
            summary = store.load_acceptance(record.id)
            outcome = assess_pilot_outcome(record, spec)
        except FileNotFoundError:
            pass

        pilot_id = record.id if record else ""
        product_failures = self._product_failures()
        idea_gate_path = self._idea_gate_path(pilot_id)
        accepted_direction = bool(
            summary
            and summary.passed
            and summary.outcome_type == "defensible_direction"
            and outcome
            and outcome.outcome_type == "defensible_direction"
        )
        accepted_refusal = bool(
            summary
            and summary.passed
            and summary.outcome_type == "correct_refusal"
            and outcome
            and outcome.outcome_type == "correct_refusal"
        )
        audit_paths = {name: self.release_dir / filename for name, filename in AUDIT_REPORTS.items()}
        requirements = {
            "v8_release_gate_passed_or_documented": self._v8_gate_passed_or_documented(),
            "pilot_spec_exists": all(path.exists() for path in spec_docs),
            "pilot_run_exists": record is not None,
            "pilot_outcome_classified": outcome is not None
            and outcome.outcome_type
            in {
                "defensible_direction",
                "correct_refusal",
                "product_failure",
                "incomplete",
            },
            "human_external_review_exists": bool(reviews),
            "idea_gate_ran": bool(idea_gate_path and idea_gate_path.exists()),
            "accepted_defensible_direction": accepted_direction,
            "accepted_correct_refusal": accepted_refusal,
            "accepted_direction_or_refusal": accepted_direction or accepted_refusal,
            "no_unresolved_product_failure": not product_failures,
            **{name: path.exists() for name, path in audit_paths.items()},
        }
        blockers = _requirement_blockers(requirements)
        blockers.extend(f"Unresolved product failure: {failure}" for failure in product_failures)
        blockers = _dedupe(blockers)
        passed = not blockers and all(
            value for key, value in requirements.items() if key not in {"accepted_defensible_direction", "accepted_correct_refusal"}
        )
        recommended_next_version = "v1" if passed else "v0.9.1" if product_failures else "v0.9"
        status = "pass" if passed else "product_failure" if product_failures else "incomplete"
        artifact_paths = {
            "pilot_spec_documents": [str(path) for path in spec_docs if path.exists()],
            "pilot_records": [str(store.record_dir(pilot_id) / "pilot_run_record.json")] if pilot_id else [],
            "pilot_reviews": [str(store.record_dir(pilot_id) / "external_reviews" / f"{review.id}.json") for review in reviews]
            if pilot_id
            else [],
            "idea_gate": [str(idea_gate_path)] if idea_gate_path and idea_gate_path.exists() else [],
            "audit_reports": [str(path) for path in audit_paths.values() if path.exists()],
            "v8_release_gate": [
                str(path) for path in [self.release_dir / "v0.8_latest.json", self.release_dir / "v0.8_latest.md"] if path.exists()
            ],
        }
        return V09ReleaseGateResult(
            passed=passed,
            status=status,
            recommended_next_version=recommended_next_version,
            requirements=requirements,
            blockers=blockers,
            warnings=_warnings(requirements, recommended_next_version),
            pilot_id=pilot_id,
            pilot_outcome_type=outcome.outcome_type if outcome else "unknown",
            artifact_paths=artifact_paths,
        )

    def write_outputs(self, result: V09ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v0.9_latest.json"
        md_path = self.release_dir / "v0.9_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v09_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _v8_gate_passed_or_documented(self) -> bool:
        json_path = self.release_dir / "v0.8_latest.json"
        md_path = self.release_dir / "v0.8_latest.md"
        if _json_passed(json_path):
            return True
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return False
            return isinstance(payload, dict) and "passed" in payload
        return md_path.exists()

    def _idea_gate_path(self, pilot_id: str) -> Path | None:
        if not pilot_id:
            return None
        return self.config.data_dir / "pilots" / pilot_id / "idea_gate_assessment.json"

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
        return _dedupe(failures)


def render_v09_release_gate_markdown(result: V09ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.9 External Pilot Release Gate",
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
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    return "\n".join(lines).rstrip() + "\n"


def _load_spec():
    return get_pilot_spec(LOW_FPR_COLLUSION)


def _pilot_spec_documents(config: GapForgeConfig) -> list[Path]:
    docs_dir = pilot_docs_dir(config, LOW_FPR_COLLUSION)
    return [docs_dir / "PILOT_SPEC.md", docs_dir / "ACCEPTANCE_CRITERIA.md", docs_dir / "REVIEW_CHECKLIST.md"]


def _json_passed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("passed") is True or payload.get("status") == "pass"


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "v8_release_gate_passed_or_documented": "v0.8 manuscript/submission release gate has not passed or been documented.",
        "pilot_spec_exists": "v0.9 pilot specification documents are missing.",
        "pilot_run_exists": "No v0.9 pilot run record was found.",
        "pilot_outcome_classified": "Pilot outcome has not been classified.",
        "human_external_review_exists": "No human/external pilot review was found.",
        "idea_gate_ran": "Idea gate has not run for the pilot.",
        "accepted_direction_or_refusal": "Pilot has neither an accepted defensible direction nor an accepted correct refusal.",
        "no_unresolved_product_failure": "Unresolved product failure blocks v0.9.",
        "v1_readiness_report_generated": "v1 readiness report has not been generated.",
        "migration_audit_generated": "Migration/backward compatibility audit has not been generated.",
        "cli_audit_generated": "CLI audit has not been generated.",
        "docs_audit_generated": "Docs audit has not been generated.",
        "artifact_hygiene_audit_generated": "Artifact hygiene audit has not been generated.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _warnings(requirements: dict[str, bool], recommended_next_version: str) -> list[str]:
    warnings: list[str] = []
    if recommended_next_version == "v0.9.1":
        warnings.append("A product failure blocks the pilot release; fix it in v0.9.1 before claiming v1 readiness.")
    elif recommended_next_version == "v0.9":
        warnings.append("v0.9 evidence is incomplete; finish pilot acceptance and audits before deciding v1.")
    if requirements.get("accepted_correct_refusal"):
        warnings.append("Correct refusal is an accepted v0.9 success outcome; do not invent a research direction.")
    return warnings


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
