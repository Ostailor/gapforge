"""v0.7 benchmark execution and replication release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.datasets.cache import dataset_cache_dir


@dataclass(slots=True)
class V07ReleaseGateResult:
    passed: bool
    status: str
    fixture_gate_passed: bool
    real_benchmark_claimed: bool
    real_benchmark_gate_passed: bool
    requirements: dict[str, bool]
    real_benchmark_requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V07ReleaseGateEnforcer:
    """Machine-check v0.7 benchmark and replication release eligibility."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def evaluate(self, *, claim_real_benchmark_validation: bool = False) -> V07ReleaseGateResult:
        artifacts = self._artifact_index()
        requirements = {
            "deterministic_ci_documented": self._deterministic_ci_documented(),
            "v6_release_gate_documented": self._gate_passed_or_documented("v0.6_latest"),
            "benchmark_registry_exists": bool(artifacts["benchmark_records"]),
            "fixture_benchmark_success": _has_canary_status(artifacts["benchmark_canary_records"], "fixture_benchmark_success", {"passed"}),
            "fixture_benchmark_failure_path": _has_canary_status(
                artifacts["benchmark_canary_records"], "fixture_benchmark_failure", {"failed"}
            ),
            "benchmark_comparison_report": bool(artifacts["benchmark_comparison_reports"]),
            "result_aggregation": bool(artifacts["aggregate_result_reports"]),
            "error_analysis_report": bool(artifacts["error_analysis_reports"]),
            "replication_package_exported": bool(artifacts["replication_packages"]),
            "replication_verification_attempted": bool(artifacts["replication_verifications"]),
            "low_fpr_underpowered_warning_tested": _low_fpr_underpowered_tested(artifacts["benchmark_canary_records"]),
            "no_fake_results_accepted": not artifacts["fake_result_markers"],
            "smoke_pilot_main_labels_preserved": _run_type_labels_preserved(artifacts["execution_records"], artifacts["result_tables"]),
        }
        real_requirements = self._real_benchmark_requirements(artifacts)
        fixture_gate_passed = all(requirements.values())
        real_gate_passed = claim_real_benchmark_validation and all(real_requirements.values())
        blockers = _fixture_blockers(requirements)
        if claim_real_benchmark_validation:
            blockers.extend(_real_blockers(real_requirements))
        warnings = _warnings(requirements, real_requirements, claim_real_benchmark_validation)
        passed = fixture_gate_passed and (not claim_real_benchmark_validation or real_gate_passed)
        status = "pass" if passed else "partial" if _has_benchmark_progress(artifacts) else "fail"
        return V07ReleaseGateResult(
            passed=passed,
            status=status,
            fixture_gate_passed=fixture_gate_passed,
            real_benchmark_claimed=claim_real_benchmark_validation,
            real_benchmark_gate_passed=real_gate_passed,
            requirements=requirements,
            real_benchmark_requirements=real_requirements,
            blockers=_dedupe(blockers),
            warnings=_dedupe(warnings),
            artifact_paths={key: [str(path) for path in paths] for key, paths in artifacts.items()},
        )

    def write_outputs(self, result: V07ReleaseGateResult) -> tuple[Path, Path]:
        data_dir = self.config.data_dir / "release_gate"
        data_dir.mkdir(parents=True, exist_ok=True)
        json_path = data_dir / "v0.7_latest.json"
        md_path = data_dir / "v0.7_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v07_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _artifact_index(self) -> dict[str, list[Path]]:
        project_root = self.config.project_root
        data_root = self.config.data_dir
        cache_root = dataset_cache_dir(self.config)
        roots = [root for root in [project_root, data_root, cache_root] if root.exists()]
        return {
            "benchmark_records": _glob_many(roots, ["**/benchmarks/benchmark-*.record.json"]),
            "benchmark_canary_records": _glob_many(roots, ["**/benchmark_canaries/benchmark-canary-*.json"]),
            "benchmark_comparison_reports": _glob_many(
                roots, ["**/reports/benchmark_comparison_*.json", "**/reports/benchmark_comparison_*.md"]
            ),
            "aggregate_result_reports": _glob_many(roots, ["**/reports/aggregate_results.json", "**/reports/aggregate_results.md"]),
            "error_analysis_reports": _glob_many(roots, ["**/reports/error_analysis_*.json", "**/reports/error_analysis_*.md"]),
            "replication_packages": _glob_many(roots, ["**/replication_packages/*/replication_package.json"]),
            "replication_verifications": _glob_many(roots, ["**/replication_packages/*/verification/replication_verification.json"]),
            "execution_records": _glob_many(roots, ["**/runs/execution-*.json"]),
            "result_tables": _glob_many(roots, ["**/reports/result_table.json"]),
            "dataset_consents": _glob_many(roots, ["**/consent/dataset-consent-*.json"]),
            "fake_result_markers": _find_fake_result_markers(roots),
        }

    def _deterministic_ci_documented(self) -> bool:
        path = self.config.data_dir / "release_gate" / "deterministic_ci.json"
        return _json_passed(path)

    def _gate_passed_or_documented(self, stem: str) -> bool:
        release_dir = self.config.data_dir / "release_gate"
        json_path = release_dir / f"{stem}.json"
        md_path = release_dir / f"{stem}.md"
        if json_path.exists():
            return _json_passed(json_path) or _json_has_key(json_path, "passed")
        return md_path.exists()

    def _real_benchmark_requirements(self, artifacts: dict[str, list[Path]]) -> dict[str, bool]:
        real_canaries = _canary_payloads(artifacts["benchmark_canary_records"], profile_id="local_public_small_benchmark")
        accepted_real = [
            payload
            for payload in real_canaries
            if str(payload.get("status", "")).lower() in {"passed", "accepted"} and payload.get("execution_status") == "complete"
        ]
        real_workspace_ids = {str(payload.get("workspace_id") or "") for payload in accepted_real if payload.get("workspace_id")}
        return {
            "accepted_opt_in_real_benchmark_canary": bool(accepted_real),
            "dataset_consent_recorded": bool(artifacts["dataset_consents"]),
            "real_results_artifact_backed": bool(accepted_real and any(payload.get("artifact_paths") for payload in accepted_real)),
            "real_reproduction_package_exported": _replication_for_any_workspace(artifacts["replication_packages"], real_workspace_ids),
        }


def render_v07_release_gate_markdown(result: V07ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.7 Benchmark Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Fixture gate passed: {str(result.fixture_gate_passed).lower()}",
        f"- Real benchmark validation claimed: {str(result.real_benchmark_claimed).lower()}",
        f"- Real benchmark gate passed: {str(result.real_benchmark_gate_passed).lower()}",
        "",
        "## Fixture Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Real Benchmark Claim Requirements", ""])
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.real_benchmark_requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    return "\n".join(lines).rstrip() + "\n"


def _fixture_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "deterministic_ci_documented": "Deterministic CI pass evidence is missing or not documented.",
        "v6_release_gate_documented": "v0.6 release-gate status is missing or not documented.",
        "benchmark_registry_exists": "No benchmark registry records were found.",
        "fixture_benchmark_success": "No fixture benchmark success canary has passed.",
        "fixture_benchmark_failure_path": "No fixture benchmark failure path has been recorded.",
        "benchmark_comparison_report": "No benchmark comparison report has been generated.",
        "result_aggregation": "No result aggregation report has been generated.",
        "error_analysis_report": "No error analysis report has been generated.",
        "replication_package_exported": "No replication package has been exported.",
        "replication_verification_attempted": "No replication package verification attempt was recorded.",
        "low_fpr_underpowered_warning_tested": "No low-FPR underpowered warning canary was recorded.",
        "no_fake_results_accepted": "A fake result marker was found in accepted benchmark artifacts.",
        "smoke_pilot_main_labels_preserved": "Execution/result records are missing run-type labels or mix smoke/pilot/main results.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _real_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "accepted_opt_in_real_benchmark_canary": (
            "Real benchmark validation was claimed, but no accepted opt-in real benchmark canary was found."
        ),
        "dataset_consent_recorded": "Real benchmark validation was claimed, but no dataset consent record was found.",
        "real_results_artifact_backed": "Real benchmark validation was claimed, but results are not artifact-backed.",
        "real_reproduction_package_exported": (
            "Real benchmark validation was claimed, but no real benchmark replication package was exported."
        ),
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _warnings(
    requirements: dict[str, bool],
    real_requirements: dict[str, bool],
    claim_real_benchmark_validation: bool,
) -> list[str]:
    warnings: list[str] = []
    if not claim_real_benchmark_validation:
        warnings.append(
            "Real benchmark validation is not claimed. Fixture benchmark canaries validate plumbing, not broad benchmark performance."
        )
    if not requirements.get("deterministic_ci_documented"):
        warnings.append("Write data/release_gate/deterministic_ci.json with passed=true after running deterministic CI.")
    if claim_real_benchmark_validation and not all(real_requirements.values()):
        warnings.append("Run an opt-in real/local benchmark canary with dataset consent, artifact-backed results, and replication export.")
    return warnings


def _glob_many(roots: list[Path], patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        for pattern in patterns:
            paths.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(paths))


def _json_passed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("passed") is True or payload.get("status") == "pass"


def _json_has_key(path: Path, key: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and key in payload


def _has_canary_status(paths: list[Path], profile_id: str, statuses: set[str]) -> bool:
    return any(str(payload.get("status", "")).lower() in statuses for payload in _canary_payloads(paths, profile_id=profile_id))


def _canary_payloads(paths: list[Path], *, profile_id: str = "") -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if profile_id and payload.get("profile_id") != profile_id:
            continue
        payloads.append(payload)
    return payloads


def _low_fpr_underpowered_tested(paths: list[Path]) -> bool:
    for payload in _canary_payloads(paths, profile_id="low_fpr_underpowered_benchmark"):
        text = json.dumps(payload).lower()
        if payload.get("status") in {"warning", "failed"} and "underpowered" in text:
            return True
    return False


def _run_type_labels_preserved(execution_records: list[Path], result_tables: list[Path]) -> bool:
    if not execution_records and not result_tables:
        return False
    allowed = {"smoke", "pilot", "main", "ablation", "negative_control", "reproduction"}
    for table_path in result_tables:
        try:
            table = json.loads(table_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        rows = table.get("rows") if isinstance(table, dict) else None
        if rows is not None and any(str(row.get("run_type", "")) not in allowed for row in rows if isinstance(row, dict)):
            return False
    for execution_path in execution_records:
        try:
            execution = json.loads(execution_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        manifest_id = str(execution.get("manifest_id") or "")
        if not any(label in manifest_id for label in allowed):
            return False
    return True


def _find_fake_result_markers(roots: list[Path]) -> list[Path]:
    markers: list[Path] = []
    for path in _glob_many(roots, ["**/results/*.json", "**/reports/*.json", "**/paper_package_v2/*.json"]):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if _contains_fake_result_marker(payload):
            markers.append(path)
    return markers


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


def _replication_for_any_workspace(paths: list[Path], workspace_ids: set[str]) -> bool:
    if not workspace_ids:
        return False
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("workspace_id") in workspace_ids:
            return True
    return False


def _has_benchmark_progress(artifacts: dict[str, list[Path]]) -> bool:
    return any(paths for paths in artifacts.values())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
