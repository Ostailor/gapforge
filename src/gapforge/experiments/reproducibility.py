"""Reproducibility checklist generation for experiment protocols."""

from __future__ import annotations

from gapforge.models import ExperimentPlan, ReproducibilityChecklist


def checklist_for_experiment(experiment: ExperimentPlan) -> ReproducibilityChecklist:
    return ReproducibilityChecklist(
        random_seeds=[0, 1, 2, 3, 4],
        dataset_versioning="Record dataset source, checksum, split manifest, label provenance, and excluded examples before running.",
        environment_spec="Commit Python version, package lockfile, hardware notes, and all experiment configuration files.",
        logging_plan=(
            "Log one structured JSONL row per run with seed, dataset version, baseline/proposed method, metrics, and artifact paths."
        ),
        metric_definitions=experiment.metrics or ["Define primary and secondary metrics before implementation."],
        preregistered_analysis=(
            "Freeze primary metric, strongest baseline, ablations, and falsification threshold before inspecting final results."
        ),
        negative_controls=_negative_controls(experiment),
        error_analysis_plan="Inspect false positives, false negatives, and failed subgroups; save representative cases with provenance.",
    )


def render_reproducibility_checklist(checklist: ReproducibilityChecklist) -> str:
    lines = [
        "# Reproducibility Checklist",
        "",
        f"- Random seeds: {', '.join(str(seed) for seed in checklist.random_seeds) or 'not specified'}",
        f"- Dataset versioning: {checklist.dataset_versioning or 'not specified'}",
        f"- Environment spec: {checklist.environment_spec or 'not specified'}",
        f"- Logging plan: {checklist.logging_plan or 'not specified'}",
        f"- Preregistered analysis: {checklist.preregistered_analysis or 'not specified'}",
        f"- Error analysis plan: {checklist.error_analysis_plan or 'not specified'}",
        "",
        "## Metric Definitions",
        "",
    ]
    lines.extend([f"- {metric}" for metric in checklist.metric_definitions] or ["- none"])
    lines.extend(["", "## Negative Controls", ""])
    lines.extend([f"- {control}" for control in checklist.negative_controls] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _negative_controls(experiment: ExperimentPlan) -> list[str]:
    controls = ["shuffle labels or outcomes to verify the pipeline does not report spurious signal"]
    text = " ".join([experiment.title, experiment.hypothesis, " ".join(experiment.metrics)]).lower()
    if "false" in text or "alert" in text:
        controls.append("run a no-collusion/no-event slice and verify alert rate stays within the predefined false-positive budget")
    if "dataset" in text or experiment.datasets or experiment.datasets_needed:
        controls.append("run a leakage control with identifiers removed or randomized")
    return controls
