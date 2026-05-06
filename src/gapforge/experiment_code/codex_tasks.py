"""Codex/GPT-5.4 task packs for workspace experiment-code implementation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code.scaffold_v2 import ExperimentCodeScaffolderV2
from gapforge.experiment_code.smoke import smoke_script_path
from gapforge.experiment_code.validation import validate_experiment_code
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import BaselineRecord, DatasetRecord, ExperimentProtocol, MetricRecord, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_compact, utc_now_iso

TASK_TYPES = {
    "implement_dataset_loader",
    "implement_baseline",
    "implement_metric",
    "implement_experiment_runner",
    "implement_ablation",
    "write_tests",
    "debug_smoke_run",
    "analyze_results",
}


@dataclass(slots=True)
class ExperimentCodeTaskPack:
    id: str
    workspace_id: str
    task_type: str
    task_dir: str
    outputs_dir: str
    code_root: str
    expected_output_files: list[str]
    validation_commands: list[str]
    status: str = "planned"
    created_at: str = ""


@dataclass(slots=True)
class ExperimentCodeImportResult:
    task_id: str
    status: str
    applied_files: list[str] = field(default_factory=list)
    rejected_files: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    validation_status: str = ""
    smoke_returncode: int | None = None


class ExperimentCodeTaskManager:
    """Create, hand off, validate, and import experiment-code implementation tasks."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.dataset_registry = DatasetRegistry(config)
        self.baseline_registry = BaselineRegistry(config)
        self.metric_registry = MetricRegistry(config)

    def create_task(self, *, workspace_id: str, task_type: str) -> ExperimentCodeTaskPack:
        if task_type not in TASK_TYPES:
            raise ValueError(f"Unsupported experiment code task type: {task_type}")
        workspace = self.workspace_manager.load_workspace(workspace_id)
        code_root = Path(workspace.root_dir) / "code"
        if not (code_root / "pyproject.toml").exists():
            ExperimentCodeScaffolderV2(self.config).scaffold(workspace_id)
        protocol = self._protocol_for_workspace(workspace.project_id, workspace.direction_id, workspace.experiment_protocol_id)
        datasets = self.dataset_registry.list_datasets(workspace_id)
        baselines = self.baseline_registry.list_baselines(workspace_id)
        metrics = self.metric_registry.list_metrics(workspace_id)
        task_id = f"experiment-code-task-{utc_now_compact()}-{slugify(task_type)}-{_stable_id(workspace_id, task_type)}"
        task_dir = Path(workspace.root_dir) / "code_tasks" / task_id
        outputs_dir = task_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        pack = ExperimentCodeTaskPack(
            id=task_id,
            workspace_id=workspace_id,
            task_type=task_type,
            task_dir=str(task_dir),
            outputs_dir=str(outputs_dir),
            code_root=str(code_root),
            expected_output_files=["experiment_code_patch.json", "files/"],
            validation_commands=_validation_commands(code_root),
            status="planned",
            created_at=utc_now_iso(),
        )
        _write_task_pack(pack, protocol=protocol, datasets=datasets, baselines=baselines, metrics=metrics)
        return pack

    def load_task(self, task_id: str) -> ExperimentCodeTaskPack:
        for project_dir in self.config.project_root.glob("*"):
            for path in (project_dir / "experiment_workspaces").glob(f"*/code_tasks/{task_id}/task.json"):
                return _load_task(path)
        raise FileNotFoundError(f"No experiment code task found for {task_id}")

    def write_handoff(self, task_id: str) -> Path:
        pack = self.load_task(task_id)
        handoff = Path(pack.task_dir) / "HANDOFF.md"
        handoff.write_text(_render_handoff(pack), encoding="utf-8")
        return handoff

    def import_outputs(self, task_id: str) -> ExperimentCodeImportResult:
        pack = self.load_task(task_id)
        code_root = Path(pack.code_root)
        outputs_dir = Path(pack.outputs_dir)
        candidates = _candidate_outputs(outputs_dir)
        if not candidates:
            result = ExperimentCodeImportResult(
                task_id=task_id,
                status="rejected",
                issues=[f"No Codex outputs found in {outputs_dir}. Expected experiment_code_patch.json or files/."],
            )
            _write_import_result(pack, result)
            return result
        applied: list[str] = []
        rejected: list[str] = []
        issues: list[str] = []
        for relative_path, content in candidates:
            validation_issues = _validate_output_file(relative_path, content)
            if validation_issues:
                rejected.append(relative_path)
                issues.extend(validation_issues)
                continue
            target = (code_root / relative_path).resolve()
            if not _is_relative_to(target, code_root.resolve()):
                rejected.append(relative_path)
                issues.append(f"Rejected `{relative_path}` because it resolves outside workspace/code.")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied.append(relative_path)
        validation = validate_experiment_code(workspace_id=pack.workspace_id, code_root=code_root, run_smoke=True)
        status = "applied" if applied and not issues and validation.status in {"valid", "warning"} else "partial" if applied else "rejected"
        result = ExperimentCodeImportResult(
            task_id=task_id,
            status=status,
            applied_files=applied,
            rejected_files=rejected,
            issues=issues,
            validation_status=validation.status,
            smoke_returncode=validation.smoke_returncode,
        )
        _write_import_result(pack, result)
        return result

    def _protocol_for_workspace(self, project_id: str, direction_id: str, protocol_id: str) -> ExperimentProtocol | None:
        program = self.project_manager.load_project(project_id)
        if protocol_id:
            return next((item for item in program.experiment_protocols if item.id == protocol_id), None)
        return next((item for item in program.experiment_protocols if item.direction_id == direction_id), None)


def render_import_result(result: ExperimentCodeImportResult) -> str:
    lines = [
        f"# Experiment Code Import `{result.task_id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Validation status: `{result.validation_status or 'not run'}`",
        f"- Smoke return code: `{result.smoke_returncode if result.smoke_returncode is not None else 'not run'}`",
        "",
        "## Applied Files",
        "",
    ]
    lines.extend([f"- `{item}`" for item in result.applied_files] or ["- none"])
    lines.extend(["", "## Rejected Files", ""])
    lines.extend([f"- `{item}`" for item in result.rejected_files] or ["- none"])
    lines.extend(["", "## Issues", ""])
    lines.extend([f"- {item}" for item in result.issues] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _write_task_pack(
    pack: ExperimentCodeTaskPack,
    *,
    protocol: ExperimentProtocol | None,
    datasets: list[DatasetRecord],
    baselines: list[BaselineRecord],
    metrics: list[MetricRecord],
) -> None:
    task_dir = Path(pack.task_dir)
    (task_dir / "task.json").write_text(json.dumps(to_plain(pack), indent=2) + "\n", encoding="utf-8")
    (task_dir / "TASK.md").write_text(_render_task(pack, protocol=protocol), encoding="utf-8")
    (task_dir / "OUTPUT_CONTRACT.md").write_text(_render_output_contract(pack), encoding="utf-8")
    (task_dir / "validation_commands.md").write_text(_render_validation_commands(pack), encoding="utf-8")
    (task_dir / "safety_rules.md").write_text(_render_safety_rules(), encoding="utf-8")
    (task_dir / "experiment_protocol.json").write_text(
        json.dumps(to_plain(protocol), indent=2) + "\n" if protocol else "{}\n", encoding="utf-8"
    )
    (task_dir / "metric_definitions.json").write_text(
        json.dumps([to_plain(metric) for metric in metrics], indent=2) + "\n", encoding="utf-8"
    )
    _write_cards(task_dir / "dataset_cards", "dataset", datasets)
    _write_cards(task_dir / "baseline_cards", "baseline", baselines)
    _write_scaffold_manifest(pack)
    (task_dir / "HANDOFF.md").write_text(_render_handoff(pack), encoding="utf-8")


def _render_task(pack: ExperimentCodeTaskPack, *, protocol: ExperimentProtocol | None) -> str:
    instructions = {
        "implement_dataset_loader": "Implement or improve dataset loading in `src/data.py` using only documented datasets.",
        "implement_baseline": "Implement baseline interfaces in `src/baselines.py`; keep missing baselines explicit.",
        "implement_metric": "Implement metric functions in `src/metrics.py` and update metric tests.",
        "implement_experiment_runner": (
            "Implement runner wiring in `src/run_experiment.py` without writing real results unless execution records exist."
        ),
        "implement_ablation": "Add ablation config hooks under `configs/` and tests; do not claim ablation outcomes.",
        "write_tests": "Add or improve tests under `tests/` for data, baselines, metrics, and runner wiring.",
        "debug_smoke_run": "Fix scaffold smoke failures using stderr/stdout and rerun validation.",
        "analyze_results": "Add analysis code only for existing result artifacts; do not fabricate result metrics.",
    }[pack.task_type]
    return "\n".join(
        [
            f"# Experiment Code Task `{pack.id}`",
            "",
            f"- Workspace ID: `{pack.workspace_id}`",
            f"- Task type: `{pack.task_type}`",
            f"- Code root: `{pack.code_root}`",
            f"- Outputs dir: `{pack.outputs_dir}`",
            f"- Protocol ID: `{protocol.id if protocol else 'none'}`",
            "",
            "## Objective",
            "",
            instructions,
            "",
            "## Required Context",
            "",
            "- Read `experiment_protocol.json`.",
            "- Read `dataset_cards/`, `baseline_cards/`, and `metric_definitions.json`.",
            "- Inspect `scaffold_files.json` and the files under workspace `code/`.",
            "",
            "## Output",
            "",
            "Write either `outputs/experiment_code_patch.json` or files under `outputs/files/`.",
            "",
        ]
    )


def _render_output_contract(pack: ExperimentCodeTaskPack) -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Preferred output file: `experiment_code_patch.json`",
            "",
            "```json",
            '{ "files": [{ "path": "src/metrics.py", "content": "...complete file content..." }] }',
            "```",
            "",
            "Rules:",
            "",
            "- `path` must be relative to `workspace/code/`.",
            "- Absolute paths and `..` path traversal are rejected.",
            "- Only source, test, config, README, and script files should be changed.",
            "- Generated outputs are imported only after validation.",
            "- Expected validation commands:",
            "",
            *[f"  - `{command}`" for command in pack.validation_commands],
            "",
        ]
    )


def _render_handoff(pack: ExperimentCodeTaskPack) -> str:
    return "\n".join(
        [
            f"# Codex Handoff `{pack.id}`",
            "",
            "Copy/paste prompt for Codex/GPT-5.4:",
            "",
            "```text",
            f"Read the task pack at {pack.task_dir}.",
            f"Modify only files under {pack.code_root}.",
            (
                f"Write implementation output to {pack.outputs_dir}/experiment_code_patch.json, "
                f"or place files under {pack.outputs_dir}/files/."
            ),
            "Use only the experiment protocol, dataset cards, baseline cards, metric definitions, and scaffold files in the task pack.",
            "Do not invent datasets, baselines, metrics, citations, or experimental results.",
            "Do not request or store hidden chain-of-thought; include only concise public implementation notes if needed.",
            "```",
            "",
            "After Codex writes outputs, run:",
            "",
            "```bash",
            f"gapforge experiment-code-import --task-id {pack.id}",
            "```",
            "",
        ]
    )


def _render_validation_commands(pack: ExperimentCodeTaskPack) -> str:
    lines = ["# Validation Commands", ""]
    lines.extend([f"- `{command}`" for command in pack.validation_commands])
    return "\n".join(lines).rstrip() + "\n"


def _render_safety_rules() -> str:
    return """# Safety Rules

- Do not generate fake results.
- Do not mark smoke-test output as empirical evidence.
- Do not write files outside workspace/code/.
- Do not introduce secrets or hidden chain-of-thought.
- If data, baselines, or metrics are missing, write TODOs or warnings instead of inventing them.
"""


def _write_cards(cards_dir: Path, prefix: str, records: list[Any]) -> None:
    cards_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        (cards_dir / f"{prefix}-{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")


def _write_scaffold_manifest(pack: ExperimentCodeTaskPack) -> None:
    code_root = Path(pack.code_root)
    files = [str(path.relative_to(code_root)) for path in code_root.rglob("*") if path.is_file()]
    (Path(pack.task_dir) / "scaffold_files.json").write_text(json.dumps(sorted(files), indent=2) + "\n", encoding="utf-8")


def _candidate_outputs(outputs_dir: Path) -> list[tuple[str, str]]:
    patch_path = outputs_dir / "experiment_code_patch.json"
    candidates: list[tuple[str, str]] = []
    if patch_path.exists():
        payload = json.loads(patch_path.read_text(encoding="utf-8"))
        for item in payload.get("files", []):
            if isinstance(item, dict):
                candidates.append((str(item.get("path", "")), str(item.get("content", ""))))
        return candidates
    files_dir = outputs_dir / "files"
    if files_dir.exists():
        for path in sorted(item for item in files_dir.rglob("*") if item.is_file()):
            candidates.append((str(path.relative_to(files_dir)), path.read_text(encoding="utf-8")))
    return candidates


def _validate_output_file(relative_path: str, content: str) -> list[str]:
    issues: list[str] = []
    path = Path(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        issues.append(f"Invalid output path `{relative_path}`; path must stay under workspace/code.")
    if path.parts and path.parts[0] not in {"src", "tests", "configs", "scripts", "README.md", "pyproject.toml"}:
        issues.append(f"Invalid output path `{relative_path}`; expected source, tests, configs, scripts, README, or pyproject.")
    lowered = content.lower()
    fake_result_terms = [
        '"accuracy": 0.',
        "'accuracy': 0.",
        '"f1": 0.',
        "'f1': 0.",
        '"auroc": 0.',
        "'auroc': 0.",
        '"result": 0.',
        "'result': 0.",
        "measured result",
        "paper result",
    ]
    if any(term in lowered for term in fake_result_terms):
        issues.append(f"Rejected `{relative_path}` because it appears to contain fake result metrics.")
    return issues


def _write_import_result(pack: ExperimentCodeTaskPack, result: ExperimentCodeImportResult) -> None:
    path = Path(pack.task_dir) / "import_result.json"
    path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
    (Path(pack.task_dir) / "import_result.md").write_text(render_import_result(result), encoding="utf-8")


def _load_task(path: Path) -> ExperimentCodeTaskPack:
    return ExperimentCodeTaskPack(**json.loads(path.read_text(encoding="utf-8")))


def _validation_commands(code_root: Path) -> list[str]:
    return [f"bash {smoke_script_path(code_root)}"]


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:8]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
