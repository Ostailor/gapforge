"""Go/no-go decision gate for the selected benchmark v2.3 workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaselineManager
from gapforge.selected_benchmark.main_analysis import MainAnalysisManager, MainAnalysisResult
from gapforge.selected_benchmark.related_work_completion import RelatedWorkCompletionManager, RelatedWorkCompletionStatus
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class SelectedBenchmarkGoNoGo:
    id: str
    benchmark_id: str
    decision: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_next_steps: list[str] = field(default_factory=list)
    confidence: str = "low"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-go-no-go"))


class GoNoGoManager:
    """Combine v2.3 evidence gates into a conservative next decision."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.analysis_manager = MainAnalysisManager(config)
        self.related_work_manager = RelatedWorkCompletionManager(config)
        self.baseline_manager = MonitorBaselineManager(config)

    def decide(self, benchmark_id: str) -> SelectedBenchmarkGoNoGo:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        analysis, analysis_blockers = self._analysis(benchmark_id)
        related_work, related_blockers = self._related_work(benchmark_id)
        baseline_assessment = self.baseline_manager.assess_baseline_strength(benchmark_id)
        review_status = self._review_status(spec.project_id)
        traceability = self._traceability_status(spec.project_id)

        blockers = [
            *analysis_blockers,
            *related_blockers,
            *baseline_assessment.blockers,
            *review_status["blockers"],
            *traceability["blockers"],
        ]
        evidence = _unique(
            [
                analysis.id if analysis else "",
                related_work.id if related_work else "",
                baseline_assessment.id,
                review_status.get("path", ""),
                traceability.get("path", ""),
            ]
        )
        decision, reason, next_steps = _decision(
            analysis=analysis,
            related_work=related_work,
            baseline_blockers=baseline_assessment.blockers,
            review_blockers=review_status["blockers"],
            traceability_blockers=traceability["blockers"],
            blockers=blockers,
        )
        result = SelectedBenchmarkGoNoGo(
            id=f"selected-go-no-go-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            decision=decision,
            reason=reason,
            evidence=evidence,
            blockers=_unique(blockers),
            required_next_steps=next_steps,
            confidence="medium" if decision == "go_publication_candidate" else "low",
            provenance=Provenance(
                created_by_skill="selected-go-no-go",
                source_ids=[benchmark_id, spec.project_id, *evidence],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Combined main analysis, related-work, baseline, reviewer, and traceability gates into a go/no-go decision."
                ),
            ),
        )
        self._write_json(self._go_no_go_dir(spec.project_id) / "go_no_go.json", result)
        (self._go_no_go_dir(spec.project_id) / "go_no_go.md").write_text(render_go_no_go_report(result), encoding="utf-8")
        return result

    def load(self, benchmark_id: str) -> SelectedBenchmarkGoNoGo:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._go_no_go_dir(spec.project_id) / "go_no_go.json"
        if not path.exists():
            return self.decide(benchmark_id)
        return from_dict(SelectedBenchmarkGoNoGo, json.loads(path.read_text(encoding="utf-8")))

    def report(self, benchmark_id: str) -> str:
        result = self.load(benchmark_id)
        report = render_go_no_go_report(result)
        spec = self.benchmark_manager.load_spec(benchmark_id)
        (self._go_no_go_dir(spec.project_id) / "go_no_go.md").write_text(report, encoding="utf-8")
        return report

    def _analysis(self, benchmark_id: str) -> tuple[MainAnalysisResult | None, list[str]]:
        try:
            analysis = self.analysis_manager.load_latest_for_benchmark(benchmark_id)
        except FileNotFoundError:
            return None, ["Main result analysis is missing."]
        blockers = []
        if "0.001" not in analysis.powered_alpha_levels:
            blockers.append("alpha=0.001 is not powered in the latest main analysis.")
        blockers.extend(blocker for blocker in analysis.publication_blockers if not _deployment_validity_only(blocker))
        return analysis, blockers

    def _related_work(self, benchmark_id: str) -> tuple[RelatedWorkCompletionStatus | None, list[str]]:
        try:
            status = self.related_work_manager.load_status(benchmark_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return None, ["Related work completion status is missing."]
        blockers = [f"Related work blocker: {blocker}" for blocker in status.blockers]
        if status.missing_categories:
            blockers.append("Related work categories remain incomplete.")
        if status.novelty_status in {"duplicate", "fatal_duplicate", "not_novel"}:
            blockers.append(f"Fatal novelty duplicate or non-novel status: {status.novelty_status}.")
        elif status.novelty_status == "unknown":
            blockers.append("Related work novelty status remains unknown.")
        return status, blockers

    def _review_status(self, project_id: str) -> dict[str, Any]:
        path = self._benchmark_dir(project_id) / "reviews" / "main_publication_review.json"
        if not path.exists():
            return {"path": str(path), "blockers": ["Main publication reviewer panel status is missing."]}
        payload = json.loads(path.read_text(encoding="utf-8"))
        fatal = list(payload.get("fatal_blockers", []))
        return {"path": str(path), "blockers": [f"Fatal reviewer blocker: {item}" for item in fatal]}

    def _traceability_status(self, project_id: str) -> dict[str, Any]:
        path = self._benchmark_dir(project_id) / "main_manuscript" / "traceability.json"
        if not path.exists():
            return {"path": str(path), "blockers": ["Main manuscript traceability status is missing."]}
        payload = json.loads(path.read_text(encoding="utf-8"))
        fatal = list(payload.get("fatal_blockers", []))
        passed = bool(payload.get("traceability_passed")) or payload.get("status") == "pass"
        blockers = [f"Manuscript traceability blocker: {item}" for item in fatal]
        if not passed:
            blockers.append("Main manuscript traceability did not pass.")
        return {"path": str(path), "blockers": blockers}

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _go_no_go_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "go_no_go"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_go_no_go_report(decision: SelectedBenchmarkGoNoGo) -> str:
    lines = [
        f"# Selected Benchmark Go/No-Go `{decision.benchmark_id}`",
        "",
        f"- Decision: `{decision.decision}`",
        f"- Confidence: `{decision.confidence}`",
        f"- Reason: {decision.reason}",
        "",
        "## Evidence",
        "",
    ]
    lines.extend([f"- `{item}`" for item in decision.evidence] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in decision.blockers] or ["- none"])
    lines.extend(["", "## Required Next Steps", ""])
    lines.extend([f"- {item}" for item in decision.required_next_steps] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Publication-candidate status is impossible with open fatal blockers.",
            "- A no-go decision is an acceptable v2.3 outcome.",
            "- Synthetic evidence alone never establishes deployment validity.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _decision(
    *,
    analysis: MainAnalysisResult | None,
    related_work: RelatedWorkCompletionStatus | None,
    baseline_blockers: list[str],
    review_blockers: list[str],
    traceability_blockers: list[str],
    blockers: list[str],
) -> tuple[str, str, list[str]]:
    blocker_text = "\n".join(blockers).lower()
    if "duplicate" in blocker_text or "not_novel" in blocker_text or "validity failed" in blocker_text:
        return (
            "no_go",
            "Fatal novelty, duplicate-prior-work, or validity evidence blocks the selected benchmark idea.",
            ["Stop publication-candidate claims and record the failed novelty/validity rationale."],
        )
    if analysis is not None and "0.001" not in analysis.powered_alpha_levels:
        return (
            "run_more_experiments",
            "The main run is underpowered for alpha=0.001; more negative traces or a dropped alpha claim are required.",
            ["Increase main negative trace count or formally drop alpha=0.001 from v2.3 claims."],
        )
    if baseline_blockers:
        return (
            "run_more_experiments",
            "Required baselines or calibration gates are incomplete but can be addressed with more benchmark work.",
            ["Implement missing baselines, rerun calibration, then rerun main analysis."],
        )
    if blockers:
        return (
            "revise_benchmark",
            "Non-experimental publication gates remain incomplete.",
            ["Complete related work, reviewer, and manuscript traceability blockers before publication-candidate claims."],
        )
    if related_work is None or review_blockers or traceability_blockers:
        return (
            "revise_benchmark",
            "Required publication-readiness artifacts are missing.",
            ["Attach related-work, reviewer, and traceability evidence."],
        )
    return (
        "go_publication_candidate",
        "Powered main analysis, sufficient related-work coverage, required baselines, nonfatal reviewer status, and traceability pass.",
        ["Prepare publication-candidate package without deployment-validity claims."],
    )


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _deployment_validity_only(blocker: str) -> bool:
    text = blocker.lower()
    return "synthetic-only" in text or "deployment-validity" in text or "deployment validity" in text
