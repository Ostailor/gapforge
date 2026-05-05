"""Executable experiment protocol generation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.baselines import baseline_candidates_from_matrix, baseline_candidates_from_strings, has_strong_baseline
from gapforge.experiments.reproducibility import checklist_for_experiment, render_reproducibility_checklist
from gapforge.experiments.stats import power_or_sample_size_notes, statistical_tests_for_metrics
from gapforge.models import (
    BaselineCandidate,
    ExperimentPlan,
    ExperimentProtocol,
    Provenance,
    RelatedWorkMatrix,
    ReproducibilityChecklist,
    ResearchDirection,
    ResearchRunState,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso


class ExperimentProtocolBuilder:
    """Convert high-level plans and directions into implementation-ready protocols."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.state_manager = ResearchStateManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def build_for_project(self, project_id: str, direction_id: str) -> ExperimentProtocol:
        program = self.project_manager.load_project(project_id)
        direction = _require_direction(program.research_directions, direction_id)
        loaded_runs = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        state, experiment = _find_project_experiment(loaded_runs, direction)
        if state is None or experiment is None:
            raise KeyError(f"Direction {direction_id} has no linked experiment plan in attached runs.")
        matrix = _matrix_for_direction(program.related_work_matrices, direction.id) or _matrix_for_gaps(
            state.related_work_matrices, direction.linked_gap_ids
        )
        protocol = build_protocol_from_state(state, experiment, direction_id=direction.id, matrix=matrix)
        program.experiment_protocols = _replace_protocol(program.experiment_protocols, protocol)
        program.baseline_candidates = _replace_baselines(program.baseline_candidates, protocol.baselines)
        state.experiment_protocols = _replace_protocol(state.experiment_protocols, protocol)
        state.baseline_candidates = _replace_baselines(state.baseline_candidates, protocol.baselines)
        self.state_manager.save_run(state)
        self.project_manager.save_project(program)
        _write_protocol_card(Path(program.project.root_dir), protocol)
        return protocol

    def build_for_run(self, run_id: str, experiment_id: str) -> ExperimentProtocol:
        state = self.state_manager.load_run(run_id)
        experiment = _require_experiment(state.experiments, experiment_id)
        direction_id = experiment.linked_gap_ids[0] if experiment.linked_gap_ids else experiment.id
        matrix = _matrix_for_gaps(state.related_work_matrices, experiment.linked_gap_ids)
        protocol = build_protocol_from_state(state, experiment, direction_id=direction_id, matrix=matrix)
        state.experiment_protocols = _replace_protocol(state.experiment_protocols, protocol)
        state.baseline_candidates = _replace_baselines(state.baseline_candidates, protocol.baselines)
        self.state_manager.save_run(state)
        return protocol

    def baseline_candidates_for_project(self, project_id: str, direction_id: str) -> list[BaselineCandidate]:
        program = self.project_manager.load_project(project_id)
        protocol = next((item for item in program.experiment_protocols if item.direction_id == direction_id), None)
        if protocol is None:
            protocol = self.build_for_project(project_id, direction_id)
        return protocol.baselines

    def reproducibility_for_run(self, run_id: str, experiment_id: str) -> ReproducibilityChecklist:
        state = self.state_manager.load_run(run_id)
        protocol = next((item for item in state.experiment_protocols if item.linked_experiment_plan_id == experiment_id), None)
        if protocol is None:
            protocol = self.build_for_run(run_id, experiment_id)
        return protocol.reproducibility_checklist


def build_protocol_from_state(
    state: ResearchRunState,
    experiment: ExperimentPlan,
    *,
    direction_id: str,
    matrix: RelatedWorkMatrix | None = None,
) -> ExperimentProtocol:
    matrix_baselines = baseline_candidates_from_matrix(matrix, state.papers) if matrix is not None else []
    fallback_baselines = baseline_candidates_from_strings(experiment.baselines)
    baselines = _dedupe_baselines([*matrix_baselines, *fallback_baselines])
    metrics = experiment.metrics or ["primary metric must be defined before running"]
    tests = _dedupe([*experiment.statistical_tests, *statistical_tests_for_metrics(metrics)])
    checklist = checklist_for_experiment(experiment)
    checklist.metric_definitions = metrics
    warnings = _protocol_warnings(experiment, baselines, matrix)
    return ExperimentProtocol(
        id=f"protocol-{_stable_id(direction_id, experiment.id)}",
        direction_id=direction_id,
        linked_experiment_plan_id=experiment.id,
        objective=experiment.core_claim_being_tested or experiment.minimum_viable_experiment or experiment.title,
        hypothesis=experiment.hypothesis or experiment.hypothesis_id,
        datasets=experiment.datasets_needed or experiment.datasets,
        baselines=baselines,
        metrics=metrics,
        statistical_tests=tests,
        power_or_sample_size_notes=power_or_sample_size_notes(metrics, experiment.datasets_needed or experiment.datasets),
        ablations=_dedupe([*experiment.ablations, "negative-control run", "seed sensitivity sweep"]),
        implementation_modules=_implementation_modules(experiment, baselines),
        expected_artifacts=_expected_artifacts(experiment),
        evaluation_script_outline=_evaluation_script_outline(experiment, metrics, tests),
        failure_modes=_dedupe(
            [*warnings, *experiment.failure_modes, *experiment.expected_failure_modes, experiment.what_result_would_falsify_the_idea]
        ),
        safety_ethics_notes=experiment.ethical_or_safety_considerations or _default_safety_notes(experiment),
        reproducibility_checklist=checklist,
        compute_budget=experiment.compute_requirements or _default_compute_budget(experiment),
        timeline=_timeline(experiment),
        provenance=Provenance(
            created_by_skill="experiment-protocol",
            source_ids=[direction_id, experiment.id, *[candidate.paper_id for candidate in baselines if candidate.paper_id]],
            timestamp=utc_now_iso(),
            reasoning_summary=(
                "Converted an ExperimentPlan into an executable protocol using related-work baselines, metric-aware "
                "statistical tests, reproducibility controls, expected artifacts, and falsification criteria."
            ),
        ),
    )


def render_protocols_markdown(protocols: list[ExperimentProtocol]) -> str:
    if not protocols:
        return "# Experiment Protocols\n\nNo experiment protocols generated yet.\n"
    lines = ["# Experiment Protocols", ""]
    for protocol in protocols:
        lines.append(render_protocol_markdown(protocol).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_protocol_markdown(protocol: ExperimentProtocol) -> str:
    lines = [
        f"## Protocol `{protocol.id}`",
        "",
        f"- Direction ID: `{protocol.direction_id}`",
        f"- Linked experiment: `{protocol.linked_experiment_plan_id}`",
        "",
        "### Objective",
        "",
        protocol.objective or "Not specified.",
        "",
        "### Hypothesis",
        "",
        protocol.hypothesis or "Not specified.",
        "",
    ]
    _extend_list(lines, "Datasets", protocol.datasets)
    _extend_list(lines, "Baselines", [f"{item.baseline_name} (`{item.paper_id or 'manual'}`)" for item in protocol.baselines])
    _extend_list(lines, "Metrics", protocol.metrics)
    _extend_list(lines, "Statistical Tests", protocol.statistical_tests)
    lines.extend(["### Power Or Sample Size Notes", "", protocol.power_or_sample_size_notes or "Not specified.", ""])
    _extend_list(lines, "Ablations", protocol.ablations)
    _extend_list(lines, "Implementation Modules", protocol.implementation_modules)
    _extend_list(lines, "Expected Artifacts", protocol.expected_artifacts)
    _extend_list(lines, "Evaluation Script Outline", protocol.evaluation_script_outline)
    _extend_list(lines, "Failure Modes And Warnings", protocol.failure_modes)
    _extend_list(lines, "Safety Ethics Notes", protocol.safety_ethics_notes)
    lines.extend(["### Compute Budget", "", protocol.compute_budget or "Not specified.", ""])
    _extend_list(lines, "Timeline", protocol.timeline)
    lines.extend(["### Reproducibility Checklist", "", render_reproducibility_checklist(protocol.reproducibility_checklist).strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _protocol_warnings(experiment: ExperimentPlan, baselines: list[BaselineCandidate], matrix: RelatedWorkMatrix | None) -> list[str]:
    warnings = []
    if not has_strong_baseline(baselines):
        warnings.append("Major warning: no strong related-work baseline candidate is linked.")
    if matrix is None:
        warnings.append("Major warning: no related-work matrix was available when generating the protocol.")
    if not experiment.what_result_would_falsify_the_idea:
        warnings.append("Major warning: falsification condition is missing from the experiment plan.")
    if not experiment.metrics:
        warnings.append("Major warning: metric definitions must be completed before implementation.")
    return warnings


def _implementation_modules(experiment: ExperimentPlan, baselines: list[BaselineCandidate]) -> list[str]:
    modules = [
        "data_manifest.py: validate datasets, labels, splits, and leakage checks",
        "metrics.py: implement primary and secondary metric definitions",
        "run_experiment.py: orchestrate proposed method, baselines, seeds, and artifact logging",
        "analysis.py: compute statistical tests, confidence intervals, and error analysis tables",
    ]
    if baselines:
        modules.append("baselines/: implement or wrap each baseline candidate with a common interface")
    if experiment.ablations:
        modules.append("ablations.py: run component removal and stress-test configurations")
    return modules


def _expected_artifacts(experiment: ExperimentPlan) -> list[str]:
    return [
        "dataset_manifest.json",
        "config/*.yaml",
        "runs/results.jsonl",
        "metrics_summary.csv",
        "statistical_tests.md",
        "error_analysis.md",
        "reproducibility_manifest.md",
        f"falsification_check_{experiment.id}.md",
    ]


def _evaluation_script_outline(experiment: ExperimentPlan, metrics: list[str], tests: list[str]) -> list[str]:
    return [
        "Load frozen dataset manifest and verify checksums.",
        "Run each baseline and proposed method across preregistered seeds.",
        f"Compute metrics: {', '.join(metrics[:5])}.",
        f"Run uncertainty tests: {', '.join(tests[:4])}.",
        "Write tables for main result, ablations, negative controls, and failure cases.",
        f"Evaluate falsification condition: {experiment.what_result_would_falsify_the_idea or 'not specified'}.",
    ]


def _default_safety_notes(experiment: ExperimentPlan) -> list[str]:
    text = " ".join([experiment.title, experiment.hypothesis]).lower()
    notes = ["Report limitations and avoid presenting pilot evidence as deployment-ready."]
    if any(term in text for term in ["false positive", "false-positive", "detection", "monitor"]):
        notes.append("Audit false positives because detection errors can cause harmful accusations or unnecessary intervention.")
    return notes


def _default_compute_budget(experiment: ExperimentPlan) -> str:
    if experiment.compute_requirements:
        return experiment.compute_requirements
    return "Small-to-moderate budget: CPU-compatible pilot plus repeated seeds; document hardware before scaling."


def _timeline(experiment: ExperimentPlan) -> list[str]:
    return [
        "Day 1-2: freeze protocol, dataset manifest, metric definitions, and baseline interfaces.",
        "Day 3-5: implement baselines, proposed method wrapper, and logging.",
        "Day 6-7: run pilot seeds and validate metric outputs.",
        "Week 2: run full baseline/proposed/ablation matrix and write error analysis.",
        f"Final checkpoint: verify falsification condition for `{experiment.id}`.",
    ]


def _find_project_experiment(
    states: list[ResearchRunState], direction: ResearchDirection
) -> tuple[ResearchRunState | None, ExperimentPlan | None]:
    linked = set(direction.linked_experiment_ids)
    for state in states:
        for experiment in state.experiments:
            if experiment.id in linked or set(experiment.linked_gap_ids).intersection(direction.linked_gap_ids):
                return state, experiment
    return None, None


def _matrix_for_direction(matrices: list[RelatedWorkMatrix], direction_id: str) -> RelatedWorkMatrix | None:
    return next((item for item in matrices if item.direction_id == direction_id), None)


def _matrix_for_gaps(matrices: list[RelatedWorkMatrix], gap_ids: list[str]) -> RelatedWorkMatrix | None:
    return next((item for item in matrices if item.direction_id in gap_ids), None)


def _require_direction(directions: list[ResearchDirection], direction_id: str) -> ResearchDirection:
    direction = next((item for item in directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _require_experiment(experiments: list[ExperimentPlan], experiment_id: str) -> ExperimentPlan:
    experiment = next((item for item in experiments if item.id == experiment_id), None)
    if experiment is None:
        raise KeyError(f"Unknown experiment: {experiment_id}")
    return experiment


def _replace_protocol(protocols: list[ExperimentProtocol], protocol: ExperimentProtocol) -> list[ExperimentProtocol]:
    return [item for item in protocols if item.id != protocol.id] + [protocol]


def _replace_baselines(existing: list[BaselineCandidate], candidates: list[BaselineCandidate]) -> list[BaselineCandidate]:
    by_key = {(item.paper_id, item.baseline_name): item for item in existing}
    for candidate in candidates:
        by_key[(candidate.paper_id, candidate.baseline_name)] = candidate
    return list(by_key.values())


def _dedupe_baselines(candidates: list[BaselineCandidate]) -> list[BaselineCandidate]:
    return _replace_baselines([], candidates)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _extend_list(lines: list[str], title: str, values: list[str]) -> None:
    lines.extend([f"### {title}", ""])
    lines.extend([f"- {value}" for value in values] or ["- none specified"])
    lines.append("")


def _write_protocol_card(project_dir: Path, protocol: ExperimentProtocol) -> Path:
    protocols_dir = project_dir / "experiment_protocols"
    protocols_dir.mkdir(parents=True, exist_ok=True)
    path = protocols_dir / f"{protocol.id}.md"
    path.write_text(render_protocol_markdown(protocol), encoding="utf-8")
    return path


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
