"""Real public benchmark experiment attempt path for selected benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.real_benchmark_search import RealBenchmarkCandidate, RealBenchmarkSearchManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.vetted_experiment import SelectedVettedBenchmarkExperimentManager
from gapforge.state import slugify, utc_now_iso

CLAIM_SUPPORT_LEVELS = {"none", "sanity_check", "auxiliary", "primary"}


@dataclass(slots=True)
class RealBenchmarkExperimentAttempt:
    id: str
    selected_benchmark_id: str
    candidate_benchmark_id: str
    adapter_id: str
    status: str = "planned"
    run_type: str = "real_public_benchmark_adapter_metadata"
    metric_results: list[dict[str, Any]] = field(default_factory=list)
    result_artifact_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    claim_support_level: str = "none"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-real-benchmark-experiment"))


class RealBenchmarkExperimentManager:
    """Plan, run, and report real-public-benchmark grounding attempts."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)
        self.real_search = RealBenchmarkSearchManager(config)
        self.vetted_experiments = SelectedVettedBenchmarkExperimentManager(config)

    def plan(self, benchmark_id: str) -> list[RealBenchmarkExperimentAttempt]:
        spec = self.benchmarks.load_spec(benchmark_id)
        search = self.real_search.load_or_search(spec.id)
        candidates = self.real_search.load_candidates(spec.id)
        by_id = {candidate.id: candidate for candidate in candidates}
        ordered_ids = [
            *search.candidate_benchmark_ids,
            *[candidate_id for candidate_id in search.rejected_candidate_ids if candidate_id not in search.candidate_benchmark_ids],
        ]
        attempts = [self._plan_candidate(spec.id, by_id[candidate_id]) for candidate_id in ordered_ids if candidate_id in by_id]
        if not attempts:
            attempts.append(
                RealBenchmarkExperimentAttempt(
                    id=f"real-benchmark-experiment-attempt-{slugify(spec.id)}-none",
                    selected_benchmark_id=spec.id,
                    candidate_benchmark_id="",
                    adapter_id="",
                    status="skipped",
                    limitations=[
                        search.no_fit_reason or "No real public benchmark candidates are available for an experiment attempt.",
                        "No dataset download or synthetic fallback was used.",
                    ],
                    claim_support_level="none",
                    provenance=Provenance(
                        created_by_skill="selected-real-benchmark-experiment-plan",
                        source_ids=[spec.id, search.id],
                        timestamp=utc_now_iso(),
                        reasoning_summary="Recorded skipped real benchmark experiment planning because no candidate was available.",
                    ),
                )
            )
        self.write_attempts(spec.project_id, attempts)
        return attempts

    def run(self, benchmark_id: str) -> list[RealBenchmarkExperimentAttempt]:
        spec = self.benchmarks.load_spec(benchmark_id)
        attempts = self.load_attempts(spec.id)
        if not attempts:
            attempts = self.plan(spec.id)
        completed = [self._run_attempt(attempt) for attempt in attempts]
        self.write_attempts(spec.project_id, completed)
        return completed

    def report(self, benchmark_id: str) -> str:
        spec = self.benchmarks.load_spec(benchmark_id)
        attempts = self.load_attempts(spec.id)
        if not attempts:
            attempts = self.plan(spec.id)
        markdown = render_real_benchmark_experiment_attempts(attempts)
        (self._experiment_dir(spec.project_id) / "real_benchmark_experiment_attempts.md").write_text(
            markdown,
            encoding="utf-8",
        )
        return markdown

    def load_attempts(self, benchmark_id: str) -> list[RealBenchmarkExperimentAttempt]:
        spec = self.benchmarks.load_spec(benchmark_id)
        path = self._attempts_path(spec.project_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [from_dict(RealBenchmarkExperimentAttempt, item) for item in raw]

    def write_attempts(self, project_id: str, attempts: list[RealBenchmarkExperimentAttempt]) -> None:
        experiment_dir = self._experiment_dir(project_id)
        experiment_dir.mkdir(parents=True, exist_ok=True)
        (experiment_dir / "real_benchmark_experiment_attempts.json").write_text(
            json.dumps(to_plain(attempts), indent=2) + "\n",
            encoding="utf-8",
        )
        (experiment_dir / "real_benchmark_experiment_attempts.md").write_text(
            render_real_benchmark_experiment_attempts(attempts),
            encoding="utf-8",
        )
        for attempt in attempts:
            if attempt.id:
                (experiment_dir / f"{attempt.id}.json").write_text(
                    json.dumps(to_plain(attempt), indent=2) + "\n",
                    encoding="utf-8",
                )

    def _plan_candidate(self, selected_benchmark_id: str, candidate: RealBenchmarkCandidate) -> RealBenchmarkExperimentAttempt:
        assessment = self.vetted_experiments.assess_real_candidate(selected_benchmark_id, candidate.id)
        claim_support = _claim_support_level(assessment.expected_claim_support)
        limitations = _dedupe(
            [
                *candidate.limitations,
                *assessment.schema_mismatches,
                *assessment.label_mismatches,
                *assessment.blockers,
                "Real public benchmark attempts are separated from synthetic selected-benchmark outputs.",
                "Dataset downloads require explicit consent; the default path is metadata-only.",
            ]
        )
        adapter_id = ""
        status = "no_fit"
        source_ids = [selected_benchmark_id, candidate.id, candidate.source_url, assessment.id]
        if assessment.adapter_possible:
            adapter = self.vetted_experiments.create_real_candidate_adapter(selected_benchmark_id, candidate.id)
            adapter_id = adapter.id
            status = "planned"
            source_ids.append(adapter.id)
        else:
            limitations.append("No experiment run is planned because no honest adapter path exists.")
        return RealBenchmarkExperimentAttempt(
            id=_attempt_id(selected_benchmark_id, candidate.id),
            selected_benchmark_id=selected_benchmark_id,
            candidate_benchmark_id=candidate.id,
            adapter_id=adapter_id,
            status=status,
            limitations=_dedupe(limitations),
            claim_support_level=claim_support if status != "no_fit" else "none",
            provenance=Provenance(
                created_by_skill="selected-real-benchmark-experiment-plan",
                source_ids=source_ids,
                timestamp=utc_now_iso(),
                reasoning_summary=("Planned a real public benchmark attempt only where adapter assessment allowed an honest mapping."),
            ),
        )

    def _run_attempt(self, attempt: RealBenchmarkExperimentAttempt) -> RealBenchmarkExperimentAttempt:
        if attempt.status in {"no_fit", "skipped", "failed"}:
            return attempt
        if not attempt.adapter_id:
            return _failed_attempt(attempt, "No adapter ID is available for this planned attempt.")
        try:
            run = self.vetted_experiments.run_real_candidate_adapter(attempt.adapter_id)
            output_path = self.config.data_dir / "vetted_benchmarks" / "adapter_runs" / run.id / "adapted_trace_units.json"
            if run.status != "complete":
                return _failed_attempt(attempt, f"Real benchmark adapter run `{run.id}` ended with status `{run.status}`.")
            if not output_path.exists():
                return _failed_attempt(attempt, f"Real benchmark adapter output is missing at `{output_path}`.")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            claim_support = _claim_support_level(
                str(payload.get("expected_claim_support") or payload.get("evidence_label") or attempt.claim_support_level)
            )
            metric_results = _attempt_metrics(attempt, run.id, payload, claim_support)
            limitations = _dedupe(
                [
                    *attempt.limitations,
                    *run.warnings,
                    *payload.get("warnings", []),
                    *_claim_support_limitations(claim_support, payload),
                ]
            )
            return RealBenchmarkExperimentAttempt(
                id=attempt.id,
                selected_benchmark_id=attempt.selected_benchmark_id,
                candidate_benchmark_id=attempt.candidate_benchmark_id,
                adapter_id=attempt.adapter_id,
                status="complete",
                run_type=attempt.run_type,
                metric_results=metric_results,
                result_artifact_ids=_dedupe([run.id, str(output_path)]),
                limitations=limitations,
                claim_support_level=claim_support,
                provenance=Provenance(
                    created_by_skill="selected-real-benchmark-experiment-run",
                    source_ids=[
                        attempt.id,
                        attempt.adapter_id,
                        run.id,
                        str(output_path),
                    ],
                    timestamp=utc_now_iso(),
                    reasoning_summary=("Ran a real public benchmark adapter attempt with outputs labeled by claim support level."),
                ),
            )
        except Exception as exc:
            return _failed_attempt(attempt, f"Real benchmark adapter run failed: {exc}")

    def _attempts_path(self, project_id: str) -> Path:
        return self._experiment_dir(project_id) / "real_benchmark_experiment_attempts.json"

    def _experiment_dir(self, project_id: str) -> Path:
        program = self.projects.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "real_benchmark_experiments"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_real_benchmark_experiment_attempts(attempts: list[RealBenchmarkExperimentAttempt]) -> str:
    selected_id = attempts[0].selected_benchmark_id if attempts else "unknown"
    lines = [
        f"# Real Benchmark Experiment Attempts `{selected_id}`",
        "",
        f"- Attempt count: {len(attempts)}",
        "- Output boundary: `real_public_benchmark_adapter` results remain separate from synthetic selected-benchmark outputs.",
        "- Dataset boundary: no large or restricted benchmark assets are downloaded by the default attempt path.",
        "",
        "## Attempts",
        "",
    ]
    if not attempts:
        lines.append("No real benchmark experiment attempts recorded.")
        return "\n".join(lines).rstrip() + "\n"
    for attempt in attempts:
        lines.extend(
            [
                f"### `{attempt.id}`",
                "",
                f"- Candidate benchmark: `{attempt.candidate_benchmark_id or 'none'}`",
                f"- Adapter: `{attempt.adapter_id or 'none'}`",
                f"- Status: `{attempt.status}`",
                f"- Run type: `{attempt.run_type}`",
                f"- Claim Support: `{attempt.claim_support_level}`",
                f"- Result artifacts: {_fmt(attempt.result_artifact_ids)}",
                "",
                "#### Metrics",
                "",
            ]
        )
        if attempt.metric_results:
            for metric in attempt.metric_results:
                lines.append(
                    f"- `{metric['metric_id']}`: {metric['value']} "
                    f"(source `{metric['result_source']}`, claim `{metric['claim_support_level']}`)"
                )
        else:
            lines.append("- No metrics recorded.")
        lines.extend(["", "#### Limitations", ""])
        lines.extend(f"- {item}" for item in (attempt.limitations or ["No limitations recorded."]))
        lines.append("")
    lines.extend(
        [
            "## Claim Boundary",
            "",
            "- `sanity_check` and `auxiliary` attempts cannot support primary benchmark validity.",
            "- `no_fit`, `failed`, and `skipped` attempts are retained as evidence of the attempted grounding path.",
            "- Primary support requires an honest adapter mapping and preserved source labels; metadata-only runs remain limited.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _attempt_metrics(
    attempt: RealBenchmarkExperimentAttempt,
    run_id: str,
    payload: dict[str, Any],
    claim_support: str,
) -> list[dict[str, Any]]:
    examples = payload.get("examples", []) if isinstance(payload.get("examples", []), list) else []
    warnings = payload.get("warnings", []) if isinstance(payload.get("warnings", []), list) else []
    strong_claims_allowed = bool(payload.get("strong_claims_allowed")) and claim_support == "primary"
    common = {
        "selected_benchmark_id": attempt.selected_benchmark_id,
        "candidate_benchmark_id": attempt.candidate_benchmark_id,
        "adapter_id": attempt.adapter_id,
        "execution_id": run_id,
        "result_source": "real_public_benchmark_adapter",
        "synthetic": False,
        "do_not_merge_with_synthetic": True,
        "claim_support_level": claim_support,
        "primary_validity_supported": strong_claims_allowed,
    }
    return [
        {**common, "metric_id": "real_benchmark_attempt_executed", "value": 1},
        {**common, "metric_id": "real_benchmark_adapted_example_count", "value": len(examples)},
        {**common, "metric_id": "real_benchmark_warning_count", "value": len(warnings)},
        {
            **common,
            "metric_id": "real_benchmark_dataset_downloaded",
            "value": int(bool(payload.get("downloaded_dataset"))),
        },
    ]


def _claim_support_limitations(claim_support: str, payload: dict[str, Any]) -> list[str]:
    limitations = [
        "Real benchmark output is labeled separately from synthetic selected-benchmark outputs.",
        "Metadata-only attempt does not download large or restricted public benchmark assets.",
    ]
    if claim_support in {"sanity_check", "auxiliary", "none"}:
        limitations.append(f"`{claim_support}` real benchmark evidence cannot support primary benchmark validity.")
    if not payload.get("strong_claims_allowed"):
        limitations.append("Strong claims remain blocked by the adapter assessment or metadata-only transformation.")
    return limitations


def _failed_attempt(attempt: RealBenchmarkExperimentAttempt, reason: str) -> RealBenchmarkExperimentAttempt:
    return RealBenchmarkExperimentAttempt(
        id=attempt.id,
        selected_benchmark_id=attempt.selected_benchmark_id,
        candidate_benchmark_id=attempt.candidate_benchmark_id,
        adapter_id=attempt.adapter_id,
        status="failed",
        run_type=attempt.run_type,
        metric_results=list(attempt.metric_results),
        result_artifact_ids=list(attempt.result_artifact_ids),
        limitations=_dedupe([*attempt.limitations, reason]),
        claim_support_level=attempt.claim_support_level,
        provenance=Provenance(
            created_by_skill="selected-real-benchmark-experiment-run",
            source_ids=[attempt.id, attempt.adapter_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Preserved failed real benchmark experiment attempt instead of dropping it.",
        ),
    )


def _claim_support_level(value: str) -> str:
    normalized = (value or "none").strip().lower().replace("-", "_")
    if normalized == "no_fit":
        return "none"
    return normalized if normalized in CLAIM_SUPPORT_LEVELS else "none"


def _attempt_id(selected_benchmark_id: str, candidate_id: str) -> str:
    return f"real-benchmark-experiment-attempt-{slugify(selected_benchmark_id)}-{slugify(candidate_id)}"


def _dedupe(items: list[str]) -> list[str]:
    deduped = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _fmt(items: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in items) if items else "none"
