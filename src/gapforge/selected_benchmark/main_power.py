"""Main-scale power planning for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.power import DEFAULT_CONFIDENCE, required_negative_count_for_zero_fp_bound
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso

MAIN_ALPHA_LEVELS = [0.01, 0.001]
DEFAULT_SECONDARY_ALPHA_LEVELS = [0.001]
DEFAULT_POSITIVE_REQUIREMENTS = {"0.01": 150, "0.001": 500}


@dataclass(slots=True)
class MainPowerPlan:
    id: str
    benchmark_id: str
    target_alpha_levels: list[float] = field(default_factory=list)
    primary_alpha: float = 0.01
    secondary_alpha_levels: list[float] = field(default_factory=list)
    required_negative_counts: dict[str, int] = field(default_factory=dict)
    required_positive_counts: dict[str, int] = field(default_factory=dict)
    planned_negative_count: int = 0
    planned_positive_count: int = 0
    confidence_interval_targets: dict[str, Any] = field(default_factory=dict)
    stopping_rules: list[str] = field(default_factory=list)
    sequential_multiple_testing_adjustment: str = ""
    feasibility_status: str = "unknown"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-power"))


@dataclass(slots=True)
class MainPowerDecision:
    id: str
    benchmark_id: str
    alpha_level: float
    decision: str
    reason: str
    required_count: int
    planned_count: int
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-alpha-decision"))


class MainPowerManager:
    """Create v2.3 main-scale low-FPR power plans and alpha decisions."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def create_plan(
        self,
        benchmark_id: str,
        *,
        planned_negative_count: int | None = None,
        planned_positive_count: int | None = None,
    ) -> MainPowerPlan:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        required_negative_counts = {
            _alpha_key(alpha): required_negative_count_for_zero_fp_bound(alpha, confidence=DEFAULT_CONFIDENCE)
            for alpha in MAIN_ALPHA_LEVELS
        }
        planned_negatives = planned_negative_count
        if planned_negatives is None:
            planned_negatives = required_negative_counts[_alpha_key(0.001)]
        planned_positives = planned_positive_count if planned_positive_count is not None else DEFAULT_POSITIVE_REQUIREMENTS["0.001"]
        if planned_negatives < 0:
            raise ValueError("planned_negative_count must be nonnegative.")
        if planned_positives < 0:
            raise ValueError("planned_positive_count must be nonnegative.")

        primary_alpha = _primary_powered_alpha(planned_negatives, required_negative_counts)
        feasibility_status = _feasibility_status(planned_negatives, required_negative_counts)
        now = utc_now_iso()
        plan = MainPowerPlan(
            id=f"main-power-plan-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            target_alpha_levels=list(MAIN_ALPHA_LEVELS),
            primary_alpha=primary_alpha,
            secondary_alpha_levels=list(DEFAULT_SECONDARY_ALPHA_LEVELS),
            required_negative_counts=required_negative_counts,
            required_positive_counts=dict(DEFAULT_POSITIVE_REQUIREMENTS),
            planned_negative_count=planned_negatives,
            planned_positive_count=planned_positives,
            confidence_interval_targets={
                "confidence": DEFAULT_CONFIDENCE,
                "method": "one-sided exact zero-false-positive upper bound plus binomial intervals",
                "claim_rule": "Publication claims must use the lowest target alpha whose required negative count is actually planned.",
                "alpha_0_001_rule": "alpha=0.001 requires at least the computed negative trace count after correction.",
            },
            stopping_rules=[
                "Lock target alpha levels, trace counts, monitor thresholds, seeds, and sequential correction before main outcomes.",
                "If alpha=0.001 is infeasible, record a downgrade, drop, or defer decision before release claims.",
                "Do not claim publication readiness from an alpha target that is not powered.",
                "Release notes must state the alpha=0.001 decision.",
            ],
            sequential_multiple_testing_adjustment=(
                "Use conservative family-wise false-alarm interpretation for repeated sequential audit windows; "
                "reduce effective negative counts when windows are correlated or overlapping."
            ),
            feasibility_status=feasibility_status,
            provenance=Provenance(
                created_by_skill="selected-main-power",
                source_ids=[benchmark_id, spec.project_id],
                timestamp=now,
                reasoning_summary="Created v2.3 main-scale power plan and primary-alpha feasibility status.",
            ),
        )
        self._write_json(self._power_dir(spec.project_id) / "main_power_plan.json", plan)
        (self._power_dir(spec.project_id) / "main_power_plan.md").write_text(render_main_power_plan(plan), encoding="utf-8")
        return plan

    def load_plan(self, benchmark_id: str) -> MainPowerPlan:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._power_dir(spec.project_id) / "main_power_plan.json"
        if not path.exists():
            return self.create_plan(benchmark_id)
        return from_dict(MainPowerPlan, json.loads(path.read_text(encoding="utf-8")))

    def load_existing_plan(self, benchmark_id: str) -> MainPowerPlan | None:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._power_dir(spec.project_id) / "main_power_plan.json"
        if not path.exists():
            return None
        return from_dict(MainPowerPlan, json.loads(path.read_text(encoding="utf-8")))

    def decide_alpha(self, benchmark_id: str, *, alpha_level: float) -> MainPowerDecision:
        plan = self.load_plan(benchmark_id)
        key = _alpha_key(alpha_level)
        if key not in plan.required_negative_counts:
            raise ValueError(f"alpha={key} is not in the main power plan target alpha levels.")
        required = plan.required_negative_counts[key]
        planned = plan.planned_negative_count
        decision, reason, blockers = _decision_for_alpha(plan, alpha_level=alpha_level, required=required, planned=planned)
        now = utc_now_iso()
        alpha_slug = slugify(key.replace(".", "_"))
        power_decision = MainPowerDecision(
            id=f"main-alpha-decision-{slugify(benchmark_id)}-alpha-{alpha_slug}",
            benchmark_id=benchmark_id,
            alpha_level=alpha_level,
            decision=decision,
            reason=reason,
            required_count=required,
            planned_count=planned,
            blockers=blockers,
            provenance=Provenance(
                created_by_skill="selected-main-alpha-decision",
                source_ids=[benchmark_id, plan.id],
                timestamp=now,
                reasoning_summary=f"Recorded v2.3 alpha={key} decision as {decision}.",
            ),
        )
        spec = self.benchmark_manager.load_spec(benchmark_id)
        decision_path = self._decisions_dir(spec.project_id) / f"{power_decision.id}.json"
        self._write_json(decision_path, power_decision)
        (self._decisions_dir(spec.project_id) / f"{power_decision.id}.md").write_text(
            render_main_power_decision(power_decision, plan),
            encoding="utf-8",
        )
        self.write_report(benchmark_id)
        return power_decision

    def load_decisions(self, benchmark_id: str) -> list[MainPowerDecision]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        decisions: list[MainPowerDecision] = []
        for path in sorted(self._decisions_dir(spec.project_id).glob("main-alpha-decision-*.json")):
            try:
                decision = from_dict(MainPowerDecision, json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if decision.benchmark_id == benchmark_id:
                decisions.append(decision)
        decisions.sort(key=lambda item: (item.alpha_level, item.id))
        return decisions

    def latest_alpha_decision(self, benchmark_id: str, *, alpha_level: float) -> MainPowerDecision | None:
        decisions = [item for item in self.load_decisions(benchmark_id) if _alpha_key(item.alpha_level) == _alpha_key(alpha_level)]
        return decisions[-1] if decisions else None

    def report(self, benchmark_id: str) -> str:
        plan = self.load_plan(benchmark_id)
        decisions = self.load_decisions(benchmark_id)
        return render_main_power_report(plan, decisions)

    def write_report(self, benchmark_id: str) -> tuple[Path, Path]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        plan = self.load_plan(benchmark_id)
        decisions = self.load_decisions(benchmark_id)
        report = render_main_power_report(plan, decisions)
        md_path = self._power_dir(spec.project_id) / "main_power_report.md"
        json_path = self._power_dir(spec.project_id) / "main_power_report.json"
        md_path.write_text(report, encoding="utf-8")
        self._write_json(
            json_path,
            {
                "plan": to_plain(plan),
                "decisions": [to_plain(decision) for decision in decisions],
                "release_notes_alpha_decision": release_notes_alpha_decision(plan, decisions),
            },
        )
        return json_path, md_path

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _power_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "main_power"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _decisions_dir(self, project_id: str) -> Path:
        path = self._power_dir(project_id) / "decisions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_main_power_plan(plan: MainPowerPlan) -> str:
    lines = [
        "# Main-Scale Power Plan",
        "",
        f"- Benchmark ID: `{plan.benchmark_id}`",
        f"- Primary alpha: alpha={plan.primary_alpha:g}",
        f"- Planned negative traces: {plan.planned_negative_count}",
        f"- Planned positive traces: {plan.planned_positive_count}",
        f"- Feasibility status: `{plan.feasibility_status}`",
        f"- Sequential adjustment: {plan.sequential_multiple_testing_adjustment}",
        "",
        "## Required Negative Counts",
        "",
    ]
    for alpha, count in sorted(plan.required_negative_counts.items(), key=lambda item: float(item[0])):
        lines.append(f"- alpha={alpha}: {count} honest negative traces")
    lines.extend(["", "## Required Positive Counts", ""])
    for alpha, count in sorted(plan.required_positive_counts.items(), key=lambda item: float(item[0])):
        lines.append(f"- alpha={alpha}: {count} positive traces for sensitivity context")
    lines.extend(["", "## Confidence Interval Targets", ""])
    lines.extend(f"- {key}: {value}" for key, value in plan.confidence_interval_targets.items())
    lines.extend(["", "## Stopping Rules", ""])
    lines.extend(f"- {item}" for item in plan.stopping_rules)
    lines.extend(["", "## Claim Rule", ""])
    lines.append(f"- Publication claims must use primary alpha={plan.primary_alpha:g}.")
    return "\n".join(lines).rstrip() + "\n"


def render_main_power_decision(decision: MainPowerDecision, plan: MainPowerPlan) -> str:
    lines = [
        "# Main Alpha Decision",
        "",
        f"- Benchmark ID: `{decision.benchmark_id}`",
        f"- Alpha: alpha={decision.alpha_level:g}",
        f"- Decision: `{decision.decision}`",
        f"- Required negative traces: {decision.required_count}",
        f"- Planned negative traces: {decision.planned_count}",
        f"- Reason: {decision.reason}",
        f"- Publication primary alpha: alpha={plan.primary_alpha:g}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {blocker}" for blocker in decision.blockers] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_main_power_report(plan: MainPowerPlan, decisions: list[MainPowerDecision]) -> str:
    lines = [
        "# Main-Scale Power Report",
        "",
        f"- Benchmark ID: `{plan.benchmark_id}`",
        f"- Primary alpha: alpha={plan.primary_alpha:g}",
        f"- Feasibility status: `{plan.feasibility_status}`",
        f"- Planned negatives: {plan.planned_negative_count}",
        f"- Planned positives: {plan.planned_positive_count}",
        "",
        "## Alpha Requirements",
        "",
    ]
    for alpha, required in sorted(plan.required_negative_counts.items(), key=lambda item: float(item[0])):
        status = "powered" if plan.planned_negative_count >= required else "not powered"
        lines.append(f"- alpha={alpha}: {required} required; {plan.planned_negative_count} planned; {status}")
    lines.extend(["", "## Alpha Decisions", ""])
    if decisions:
        for decision in decisions:
            lines.append(
                f"- alpha={decision.alpha_level:g}: `{decision.decision}`; "
                f"{decision.planned_count} planned / {decision.required_count} required; {decision.reason}"
            )
    else:
        lines.append("- none recorded")
    lines.extend(["", "## Release Notes Alpha Decision", ""])
    lines.append(f"- {release_notes_alpha_decision(plan, decisions)}")
    lines.extend(["", "## Publication Claim Alignment", ""])
    lines.append(f"- Publication claims must use primary alpha={plan.primary_alpha:g}.")
    lines.append("- alpha=0.001 claims require a `power` decision; downgrade, drop, or defer decisions block that claim.")
    lines.extend(["", "## Sequential Multiple-Testing Adjustment", ""])
    lines.append(f"- {plan.sequential_multiple_testing_adjustment}")
    return "\n".join(lines).rstrip() + "\n"


def release_notes_alpha_decision(plan: MainPowerPlan, decisions: list[MainPowerDecision]) -> str:
    alpha_001 = [decision for decision in decisions if _alpha_key(decision.alpha_level) == "0.001"]
    if not alpha_001:
        return "alpha=0.001 decision missing; v2.3 release gate must block main-scale/publication claims."
    decision = alpha_001[-1]
    if decision.decision == "power":
        return f"alpha=0.001 powered with {decision.planned_count} planned negative traces against {decision.required_count} required."
    return (
        f"alpha=0.001 {decision.decision}: {decision.planned_count} planned negative traces "
        f"against {decision.required_count} required; publication claims use primary alpha={plan.primary_alpha:g}."
    )


def _decision_for_alpha(
    plan: MainPowerPlan,
    *,
    alpha_level: float,
    required: int,
    planned: int,
) -> tuple[str, str, list[str]]:
    key = _alpha_key(alpha_level)
    if planned >= required:
        return "power", f"Planned negative count supports alpha={key}.", []
    if key == "0.001":
        primary_key = _alpha_key(plan.primary_alpha)
        reason = (
            f"Planned negative count is below alpha=0.001 requirement; downgrade publication claims to "
            f"primary alpha={primary_key} unless alpha=0.001 is later powered."
        )
        blockers = [
            f"alpha=0.001 requires {required} negative traces but only {planned} are planned.",
            f"Publication claims must use primary alpha={primary_key} until alpha=0.001 is powered.",
        ]
        return "downgrade", reason, blockers
    return (
        "defer",
        f"Planned negative count is below alpha={key} requirement.",
        [f"alpha={key} requires {required} negative traces but only {planned} are planned."],
    )


def _primary_powered_alpha(planned_negative_count: int, required_negative_counts: dict[str, int]) -> float:
    powered = [float(alpha) for alpha, required in required_negative_counts.items() if planned_negative_count >= required]
    if not powered:
        return 0.01
    return min(powered)


def _feasibility_status(planned_negative_count: int, required_negative_counts: dict[str, int]) -> str:
    if planned_negative_count >= required_negative_counts["0.001"]:
        return "alpha_0_001_powered"
    if planned_negative_count >= required_negative_counts["0.01"]:
        return "alpha_0_001_infeasible"
    return "main_power_underpowered"


def _alpha_key(alpha: float) -> str:
    return f"{alpha:g}"
