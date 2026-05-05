"""Generate Codex-ready implementation tasks from experiment protocols."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.experiment_code.eval_scripts import baseline_names, metric_definitions, render_reproducibility_lines
from gapforge.models import (
    ExperimentCodeTask,
    ExperimentProtocol,
    Provenance,
    ResearchDirection,
    ResearchProgramState,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

READY_MATURITIES = {"experiment_ready", "manuscript_ready"}
TASK_TYPES = [
    "scaffold_repo",
    "implement_dataset",
    "implement_baseline",
    "implement_metric",
    "implement_ablation",
    "write_tests",
    "run_smoke",
]


@dataclass(slots=True)
class ExperimentCodeContext:
    program: ResearchProgramState
    direction: ResearchDirection
    protocol: ExperimentProtocol
    campaign_id: str


class ExperimentCodeTaskGenerator:
    """Create implementation handoff tasks without claiming experiment results."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.campaign_manager = CampaignManager(config)

    def generate_tasks(
        self,
        *,
        campaign_id: str,
        direction_id: str,
        allow_rejected: bool = False,
    ) -> list[ExperimentCodeTask]:
        context = load_experiment_code_context(
            self.config,
            campaign_id=campaign_id,
            direction_id=direction_id,
            allow_rejected=allow_rejected,
        )
        tasks = [_build_task(context, task_type) for task_type in TASK_TYPES]
        existing = [
            task
            for task in context.program.experiment_code_tasks
            if not (
                task.campaign_id == campaign_id and task.direction_id == direction_id and task.experiment_protocol_id == context.protocol.id
            )
        ]
        context.program.experiment_code_tasks = [*existing, *tasks]
        self.project_manager.save_project(context.program)
        return tasks

    def write_codex_task(self, code_task_id: str) -> Path:
        program, task = find_code_task(self.config, code_task_id)
        task_dir = Path(program.project.root_dir) / "experiment_code_tasks" / task.id
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / "CODEX_TASK.md"
        path.write_text(render_codex_code_task(program, task), encoding="utf-8")
        return path


def write_codex_code_task(config: GapForgeConfig, code_task_id: str) -> Path:
    return ExperimentCodeTaskGenerator(config).write_codex_task(code_task_id)


def load_experiment_code_context(
    config: GapForgeConfig,
    *,
    campaign_id: str,
    direction_id: str,
    allow_rejected: bool = False,
) -> ExperimentCodeContext:
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    program = ProjectMemoryManager(config).load_project(campaign_state.campaign.project_id)
    direction = _require_direction(program.research_directions, direction_id)
    _validate_direction_ready(direction, allow_rejected=allow_rejected)
    protocol = _require_protocol(program.experiment_protocols, direction_id)
    return ExperimentCodeContext(program=program, direction=direction, protocol=protocol, campaign_id=campaign_id)


def find_code_task(config: GapForgeConfig, code_task_id: str) -> tuple[ResearchProgramState, ExperimentCodeTask]:
    manager = ProjectMemoryManager(config)
    for project in manager.list_projects():
        program = manager.load_project(project.id)
        for task in program.experiment_code_tasks:
            if task.id == code_task_id:
                return program, task
    raise KeyError(f"No experiment code task found for {code_task_id}")


def render_codex_code_task(program: ResearchProgramState, task: ExperimentCodeTask) -> str:
    lines = [
        f"# Codex Experiment Code Task `{task.id}`",
        "",
        "## Objective",
        "",
        "Implement only the requested experiment scaffold or code slice. Do not claim that experiments were run.",
        "",
        "## Project Context",
        "",
        f"- Project ID: `{program.project.id}`",
        f"- Campaign ID: `{task.campaign_id}`",
        f"- Direction ID: `{task.direction_id}`",
        f"- Experiment protocol ID: `{task.experiment_protocol_id}`",
        f"- Task type: `{task.task_type}`",
        "",
        "## Instructions",
        "",
        task.instructions,
        "",
        "## Required Files",
        "",
        *[f"- `{item}`" for item in task.required_files],
        "",
        "## Expected Outputs",
        "",
        *[f"- `{item}`" for item in task.expected_outputs],
        "",
        "## Validation Commands",
        "",
        *[f"- `{item}`" for item in task.validation_commands],
        "",
        "## Evidence And Honesty Rules",
        "",
        "- Do not invent unavailable datasets, baselines, metrics, citations, or experiment results.",
        "- Synthetic placeholder data must be labeled as synthetic placeholder data in code and docs.",
        "- Expected results are hypotheses only; do not write measured values unless a real experiment has been run.",
        "- Keep smoke tests focused on wiring and schema checks.",
        "- Store concise public reasoning summaries only; do not include hidden chain-of-thought.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _build_task(context: ExperimentCodeContext, task_type: str) -> ExperimentCodeTask:
    protocol = context.protocol
    direction = context.direction
    base_dir = f"experiment_repos/{direction.id}"
    instructions = _instructions_for(task_type, protocol)
    required_files, expected_outputs = _files_for(task_type, base_dir, protocol)
    validation_commands = _validation_for(task_type)
    return ExperimentCodeTask(
        id=f"code-task-{_stable_id(context.campaign_id, direction.id, protocol.id, task_type)}",
        campaign_id=context.campaign_id,
        direction_id=direction.id,
        experiment_protocol_id=protocol.id,
        task_type=task_type,
        instructions=instructions,
        required_files=required_files,
        expected_outputs=expected_outputs,
        validation_commands=validation_commands,
        status="planned",
        provenance=Provenance(
            created_by_skill="experiment-code-task",
            source_ids=[context.campaign_id, direction.id, protocol.id],
            timestamp=utc_now_iso(),
            reasoning_summary=(
                "Generated a Codex implementation handoff task from an experiment-ready direction and protocol. "
                "The task is scoped to code scaffolding or validation only and does not assert experiment results."
            ),
        ),
    )


def _instructions_for(task_type: str, protocol: ExperimentProtocol) -> str:
    dataset_text = "; ".join(protocol.datasets) if protocol.datasets else "No real dataset is available yet."
    baseline_text = "; ".join(baseline_names(protocol.baselines))
    metric_text = "; ".join(metric_definitions(protocol))
    repro_text = "; ".join(render_reproducibility_lines(protocol.reproducibility_checklist))
    if task_type == "scaffold_repo":
        return (
            "Create the experiment repository skeleton with README, pyproject, src, tests, configs, data, metrics, "
            "baselines, and evals directories. State clearly that no experiment results exist yet."
        )
    if task_type == "implement_dataset":
        return (
            f"Implement dataset loading interfaces for: {dataset_text} "
            "If real data is unavailable, create only synthetic placeholder fixtures and label them explicitly."
        )
    if task_type == "implement_baseline":
        return f"Implement baseline interfaces or TODO stubs for required baselines: {baseline_text}."
    if task_type == "implement_metric":
        return f"Implement metric definitions and validation checks from the protocol: {metric_text}."
    if task_type == "implement_ablation":
        ablations = "; ".join(protocol.ablations) if protocol.ablations else "No ablations specified; add placeholders only."
        return f"Create ablation configuration hooks for: {ablations} Do not fabricate ablation outcomes."
    if task_type == "write_tests":
        return f"Write smoke and unit tests for dataset, baseline, metric, and eval wiring. Reproducibility: {repro_text}."
    if task_type == "run_smoke":
        return (
            "Run smoke validation commands and record only pass/fail wiring status. Do not write research conclusions "
            "or measured performance values."
        )
    raise ValueError(f"Unknown experiment code task type: {task_type}")


def _files_for(task_type: str, base_dir: str, protocol: ExperimentProtocol) -> tuple[list[str], list[str]]:
    common = [f"{base_dir}/README.md", f"{base_dir}/pyproject.toml"]
    if task_type == "scaffold_repo":
        outputs = [
            *common,
            f"{base_dir}/src/",
            f"{base_dir}/tests/",
            f"{base_dir}/configs/",
            f"{base_dir}/data/README.md",
            f"{base_dir}/metrics/",
            f"{base_dir}/baselines/",
            f"{base_dir}/evals/",
        ]
        return common, outputs
    if task_type == "implement_dataset":
        return [f"{base_dir}/data/README.md", f"{base_dir}/src/datasets.py"], [
            f"{base_dir}/src/datasets.py",
            f"{base_dir}/tests/test_datasets.py",
        ]
    if task_type == "implement_baseline":
        return [f"{base_dir}/baselines/README.md", f"{base_dir}/src/baselines.py"], [
            f"{base_dir}/src/baselines.py",
            f"{base_dir}/tests/test_baselines.py",
        ]
    if task_type == "implement_metric":
        required = [f"{base_dir}/metrics/definitions.py", f"{base_dir}/src/metrics.py"]
        expected = [*required, f"{base_dir}/tests/test_metrics.py"]
        return required, expected
    if task_type == "implement_ablation":
        return [f"{base_dir}/configs/default.json"], [f"{base_dir}/configs/ablations.json", f"{base_dir}/tests/test_ablation_configs.py"]
    if task_type == "write_tests":
        return [f"{base_dir}/tests/"], [f"{base_dir}/tests/test_smoke.py", f"{base_dir}/tests/test_no_fake_results.py"]
    if task_type == "run_smoke":
        expected = [f"{base_dir}/{item}" if not item.startswith(base_dir) else item for item in protocol.expected_artifacts]
        return [f"{base_dir}/evals/run_eval.py"], expected or [f"{base_dir}/artifacts/smoke_status.json"]
    return common, common


def _validation_for(task_type: str) -> list[str]:
    commands = ["python -m pytest tests -q"]
    if task_type in {"scaffold_repo", "run_smoke"}:
        commands.append("python evals/run_eval.py")
    return commands


def _require_direction(directions: list[ResearchDirection], direction_id: str) -> ResearchDirection:
    direction = next((item for item in directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"No research direction found for {direction_id}")
    return direction


def _require_protocol(protocols: list[ExperimentProtocol], direction_id: str) -> ExperimentProtocol:
    protocol = next((item for item in protocols if item.direction_id == direction_id), None)
    if protocol is None:
        raise KeyError(f"Direction {direction_id} has no experiment protocol. Run `gapforge experiment-protocol` first.")
    return protocol


def _validate_direction_ready(direction: ResearchDirection, *, allow_rejected: bool) -> None:
    if direction.maturity == "rejected" and not allow_rejected:
        raise ValueError(f"Direction {direction.id} is rejected; experiment code tasks require an explicit override.")
    if direction.maturity not in READY_MATURITIES and not allow_rejected:
        raise ValueError(
            f"Direction {direction.id} is {direction.maturity}; experiment code tasks require experiment_ready or manuscript_ready."
        )


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return digest
