"""Codex/GPT-5.4 implementation task packs for the selected benchmark."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaselineManager
from gapforge.selected_benchmark.metrics import SequentialMetricManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.tasks import BenchmarkTaskFamily
from gapforge.selected_benchmark.threat_model import CollusionThreatModel
from gapforge.selected_benchmark.trace_generator import AgentTrace, TraceDataset, TraceStep
from gapforge.state import utc_now_compact, utc_now_iso

SELECTED_BENCHMARK_CODEX_TASK_TYPES = {
    "implement_trace_generator",
    "implement_monitor_baseline",
    "implement_sequential_metrics",
    "implement_smoke_runner",
    "debug_selected_benchmark",
    "improve_benchmark_report",
}

NO_FAKE_RESULTS_RULE = (
    "Do not invent, hard-code, or import generated benchmark results. Metrics must be computed from persisted "
    "synthetic traces and monitor predictions; smoke failures must be recorded instead of replaced by fabricated success."
)


@dataclass(slots=True)
class SelectedBenchmarkCodexTask:
    id: str
    benchmark_id: str
    task_type: str
    task_dir: str
    outputs_dir: str
    code_workspace: str
    expected_files: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    benchmark_spec: dict[str, Any] = field(default_factory=dict)
    threat_model: dict[str, Any] = field(default_factory=dict)
    trace_schema: dict[str, Any] = field(default_factory=dict)
    baseline_requirements: list[str] = field(default_factory=list)
    metric_definitions: list[str] = field(default_factory=list)
    no_fake_results_rule: str = NO_FAKE_RESULTS_RULE
    model: str = "gpt-5.4"
    status: str = "planned"
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-codex-task"))


@dataclass(slots=True)
class SelectedBenchmarkCodexImportResult:
    id: str
    task_id: str
    status: str
    imported_files: list[str] = field(default_factory=list)
    rejected_files: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    smoke_status: str = ""
    issues: list[str] = field(default_factory=list)
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-codex-import"))


class SelectedBenchmarkCodexTaskManager:
    """Create, hand off, validate, and import selected-benchmark implementation task packs."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def create_task(self, benchmark_id: str, task_type: str) -> SelectedBenchmarkCodexTask:
        normalized = _normalize_task_type(task_type)
        spec = self.benchmark_manager.load_spec(benchmark_id)
        threat_model = self.benchmark_manager.load_threat_model(benchmark_id) or self.benchmark_manager.create_threat_model(benchmark_id)
        task_families = self.benchmark_manager.load_task_families(benchmark_id) or self.benchmark_manager.create_task_families(benchmark_id)
        baseline_manager = MonitorBaselineManager(self.config)
        baselines = baseline_manager.load_baselines(benchmark_id) or baseline_manager.create_baselines(benchmark_id)
        metric_plan = SequentialMetricManager(self.config).create_plan(benchmark_id)
        task_id = f"selected-benchmark-codex-task-{utc_now_compact()}-{normalized}-{_stable_id(benchmark_id, normalized)}"
        task_dir = self._task_dir(spec.project_id, task_id)
        code_workspace = task_dir / "code_workspace"
        outputs_dir = code_workspace / "outputs"
        imported_dir = code_workspace / "imported"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        imported_dir.mkdir(parents=True, exist_ok=True)
        task = SelectedBenchmarkCodexTask(
            id=task_id,
            benchmark_id=benchmark_id,
            task_type=normalized,
            task_dir=str(task_dir),
            outputs_dir=str(outputs_dir),
            code_workspace=str(code_workspace),
            expected_files=_expected_files(normalized),
            validation_commands=_validation_commands(normalized),
            benchmark_spec=to_plain(spec),
            threat_model=to_plain(threat_model),
            trace_schema=_trace_schema(),
            baseline_requirements=[
                f"{baseline.name} ({baseline.baseline_type}, input_mode={baseline.input_mode})" for baseline in baselines
            ],
            metric_definitions=[
                f"target alpha {alpha} requires {count} honest negative traces for zero-FP upper-bound support"
                for alpha, count in metric_plan.required_negative_counts.items()
            ]
            + [
                "per-step false positive rate",
                "per-episode false positive rate",
                "family-wise false alarm probability",
                "time-to-detection",
                "detection delay",
                "true positive rate at fixed false positive budget",
                "specificity at alpha",
                "sequential calibration error",
                "abstention/uncertain rate",
                "exact/binomial confidence intervals",
                "zero-false-positive upper bound",
            ],
            created_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="selected-benchmark-codex-task",
                source_ids=[benchmark_id, spec.project_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created a constrained Codex/GPT-5.4 implementation task pack for the selected benchmark.",
            ),
        )
        self._write_task_pack(task, threat_model=threat_model, task_families=task_families)
        return task

    def load_task(self, task_id: str) -> SelectedBenchmarkCodexTask:
        for project in self.project_manager.list_projects():
            path = Path(project.root_dir) / "selected_benchmark" / "codex_tasks" / task_id / "task.json"
            if path.exists():
                return from_dict(SelectedBenchmarkCodexTask, json.loads(path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No selected benchmark Codex task found for {task_id}")

    def handoff(self, task_id: str) -> str:
        task = self.load_task(task_id)
        return (Path(task.task_dir) / "HANDOFF.md").read_text(encoding="utf-8")

    def import_outputs(self, task_id: str) -> SelectedBenchmarkCodexImportResult:
        task = self.load_task(task_id)
        output_path = Path(task.outputs_dir) / "selected_benchmark_patch.json"
        result = self._validate_patch(task, output_path)
        if result.status in {"valid", "partial"} and result.imported_files:
            result.status = "imported" if not result.issues and not result.rejected_files else "partial"
        elif not result.imported_files:
            result.status = "rejected"
        self._write_import_result(task, result)
        return result

    def _write_task_pack(
        self,
        task: SelectedBenchmarkCodexTask,
        *,
        threat_model: CollusionThreatModel,
        task_families: list[BenchmarkTaskFamily],
    ) -> None:
        task_dir = Path(task.task_dir)
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(json.dumps(to_plain(task), indent=2) + "\n", encoding="utf-8")
        (task_dir / "TASK.md").write_text(_render_task(task), encoding="utf-8")
        (task_dir / "HANDOFF.md").write_text(_render_handoff(task), encoding="utf-8")
        (task_dir / "OUTPUT_CONTRACT.md").write_text(_render_output_contract(task), encoding="utf-8")
        (task_dir / "validation_commands.md").write_text(_render_validation_commands(task), encoding="utf-8")
        (task_dir / "safety_rules.md").write_text(_render_safety_rules(), encoding="utf-8")
        (task_dir / "benchmark_spec.json").write_text(json.dumps(task.benchmark_spec, indent=2) + "\n", encoding="utf-8")
        (task_dir / "threat_model.json").write_text(json.dumps(to_plain(threat_model), indent=2) + "\n", encoding="utf-8")
        (task_dir / "trace_schema.json").write_text(json.dumps(task.trace_schema, indent=2) + "\n", encoding="utf-8")
        (task_dir / "task_families.json").write_text(json.dumps(to_plain(task_families), indent=2) + "\n", encoding="utf-8")
        (task_dir / "baseline_requirements.json").write_text(json.dumps(task.baseline_requirements, indent=2) + "\n", encoding="utf-8")
        (task_dir / "metric_definitions.json").write_text(json.dumps(task.metric_definitions, indent=2) + "\n", encoding="utf-8")
        (Path(task.code_workspace) / "README.md").write_text(_render_workspace_readme(task), encoding="utf-8")

    def _validate_patch(self, task: SelectedBenchmarkCodexTask, output_path: Path) -> SelectedBenchmarkCodexImportResult:
        result = SelectedBenchmarkCodexImportResult(
            id=f"selected-benchmark-codex-import-{utc_now_compact()}-{_stable_id(task.id)}",
            task_id=task.id,
            status="valid",
            validation_commands=task.validation_commands,
            created_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="selected-benchmark-codex-import",
                source_ids=[task.benchmark_id, task.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Validated selected-benchmark Codex outputs before importing into the task code workspace.",
            ),
        )
        if not output_path.exists():
            result.status = "rejected"
            result.issues.append(f"No Codex output found at {output_path}.")
            return result
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result.status = "rejected"
            result.issues.append(f"Invalid JSON in {output_path}: {exc}")
            return result
        smoke_status = str(payload.get("smoke_tests") or payload.get("smoke_status") or "")
        result.smoke_status = smoke_status
        failure_recorded = bool(payload.get("failure_recorded")) or bool(payload.get("failure_log"))
        if smoke_status and smoke_status != "passed" and not failure_recorded:
            result.issues.append("Smoke tests must pass or a failure_recorded/failure_log entry must be provided.")
        source = str(payload.get("results_source") or "")
        if source and source != "computed_from_predictions_traces":
            result.issues.append("Generated results are accepted only when results_source is computed_from_predictions_traces.")
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            result.issues.append("Patch must include a non-empty files list.")
            result.status = "rejected"
            return result
        imported_root = Path(task.code_workspace) / "imported"
        imported_root.mkdir(parents=True, exist_ok=True)
        for item in files:
            if not isinstance(item, dict):
                result.rejected_files.append("<non-object>")
                result.issues.append("Rejected non-object file entry.")
                continue
            relative_path = str(item.get("path") or "")
            content = str(item.get("content") or "")
            issues = _validate_patch_file(relative_path, content)
            if issues:
                result.rejected_files.append(relative_path)
                result.issues.extend(issues)
                continue
            target = (imported_root / relative_path).resolve()
            if not _is_relative_to(target, imported_root.resolve()):
                result.rejected_files.append(relative_path)
                result.issues.append(f"Rejected `{relative_path}` because it resolves outside the task code workspace.")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            result.imported_files.append(relative_path)
        if result.rejected_files or result.issues:
            result.status = "partial" if result.imported_files else "rejected"
        return result

    def _write_import_result(self, task: SelectedBenchmarkCodexTask, result: SelectedBenchmarkCodexImportResult) -> None:
        path = Path(task.task_dir) / "import_result.json"
        path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (Path(task.task_dir) / "import_result.md").write_text(render_selected_benchmark_codex_import_result(result), encoding="utf-8")

    def _task_dir(self, project_id: str, task_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "codex_tasks" / task_id


def render_selected_benchmark_codex_import_result(result: SelectedBenchmarkCodexImportResult) -> str:
    lines = [
        f"# Selected Benchmark Codex Import `{result.task_id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Smoke status: `{result.smoke_status or 'not reported'}`",
        "",
        "## Imported Files",
        "",
    ]
    lines.extend([f"- `{item}`" for item in result.imported_files] or ["- none"])
    lines.extend(["", "## Rejected Files", ""])
    lines.extend([f"- `{item}`" for item in result.rejected_files] or ["- none"])
    lines.extend(["", "## Issues", ""])
    lines.extend([f"- {item}" for item in result.issues] or ["- none"])
    lines.extend(["", "## Validation Commands", ""])
    lines.extend([f"- `{item}`" for item in result.validation_commands] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _render_task(task: SelectedBenchmarkCodexTask) -> str:
    objectives = {
        "implement_trace_generator": "Improve synthetic trace generation while preserving synthetic labels and honest hard negatives.",
        "implement_monitor_baseline": "Improve baseline monitors without enabling optional LLM judge behavior in CI.",
        "implement_sequential_metrics": "Improve sequential specificity metrics while keeping low-FPR claims statistically cautious.",
        "implement_smoke_runner": "Improve the runnable smoke path from workspace manifest through parsed artifacts.",
        "debug_selected_benchmark": "Diagnose selected-benchmark failures using persisted artifacts and record failures honestly.",
        "improve_benchmark_report": "Improve benchmark reports without adding unsupported empirical or real-world validity claims.",
    }
    lines = [
        f"# Selected Benchmark Codex Task `{task.id}`",
        "",
        f"- Benchmark ID: `{task.benchmark_id}`",
        f"- Task type: `{task.task_type}`",
        f"- Model: `{task.model}`",
        f"- Code workspace: `{task.code_workspace}`",
        f"- Outputs dir: `{task.outputs_dir}`",
        "",
        "## Objective",
        "",
        objectives[task.task_type],
        "",
        "## Required Context",
        "",
        "- Read `benchmark_spec.json`.",
        "- Read `threat_model.json`.",
        "- Read `trace_schema.json`.",
        "- Read `task_families.json`.",
        "- Read `baseline_requirements.json`.",
        "- Read `metric_definitions.json`.",
        "- Read `OUTPUT_CONTRACT.md` and `safety_rules.md` before producing a patch.",
        "",
        "## Expected Files",
        "",
    ]
    lines.extend(f"- `{item}`" for item in task.expected_files)
    lines.extend(["", "## No Fake Results Rule", "", task.no_fake_results_rule, ""])
    return "\n".join(lines)


def _render_handoff(task: SelectedBenchmarkCodexTask) -> str:
    return "\n".join(
        [
            f"# Selected Benchmark Codex/GPT-5.4 Handoff `{task.id}`",
            "",
            "Copy/paste prompt for Codex/GPT-5.4:",
            "",
            "```text",
            f"Read the selected-benchmark task pack at {task.task_dir}.",
            f"Use model label {task.model}.",
            f"Work only inside the task code workspace: {task.code_workspace}.",
            f"Write output to {task.outputs_dir}/selected_benchmark_patch.json.",
            "Use the benchmark spec, threat model, trace schema, baseline requirements, and metric definitions from the task pack.",
            "Do not invent benchmark results, citations, datasets, or monitor performance claims.",
            "Metrics must be computed from persisted predictions/traces, and smoke failures must be recorded instead of hidden.",
            "Do not request or store hidden chain-of-thought; include concise public implementation notes only when useful.",
            "```",
            "",
            "After Codex writes output, run:",
            "",
            "```bash",
            f"gapforge selected-benchmark-codex-import --task-id {task.id}",
            "```",
            "",
        ]
    )


def _render_output_contract(task: SelectedBenchmarkCodexTask) -> str:
    lines = [
        "# Output Contract",
        "",
        "Write `selected_benchmark_patch.json` in the task outputs directory:",
        "",
        "```json",
        (
            '{ "smoke_tests": "passed", "results_source": "computed_from_predictions_traces", '
            '"files": [{ "path": "src/gapforge/selected_benchmark/metrics.py", "content": "...complete file content..." }] }'
        ),
        "```",
        "",
        "Rules:",
        "",
        "- `path` must be relative and must stay inside the task code workspace when imported.",
        "- Absolute paths and `..` path traversal are rejected.",
        "- Result artifacts, hard-coded metric values, and fabricated benchmark summaries are rejected.",
        "- Smoke tests must pass or the output must include `failure_recorded: true` or `failure_log`.",
        "- Generated metrics must be computed from predictions/traces, declared by `results_source`.",
        "- Expected validation commands:",
        "",
    ]
    lines.extend(f"  - `{command}`" for command in task.validation_commands)
    lines.extend(["", "Expected implementation files:", ""])
    lines.extend(f"- `{item}`" for item in task.expected_files)
    return "\n".join(lines).rstrip() + "\n"


def _render_validation_commands(task: SelectedBenchmarkCodexTask) -> str:
    lines = ["# Validation Commands", ""]
    lines.extend([f"- `{command}`" for command in task.validation_commands])
    return "\n".join(lines).rstrip() + "\n"


def _render_safety_rules() -> str:
    return f"""# Safety Rules

- {NO_FAKE_RESULTS_RULE}
- Keep all Codex-generated code changes inside the task code workspace until human review.
- Do not write generated benchmark result artifacts as implementation proof.
- Do not weaken novelty, prior-work, synthetic-data, or low-FPR power warnings.
- Optional LLM judge monitors must remain disabled in CI unless explicitly configured outside this task pack.
- Oracle monitors are analysis-only and must not be represented as deployable methods.
"""


def _render_workspace_readme(task: SelectedBenchmarkCodexTask) -> str:
    return "\n".join(
        [
            f"# Code Workspace `{task.id}`",
            "",
            "Use this directory for generated Codex implementation patches only.",
            "",
            f"- Output patch: `{Path(task.outputs_dir) / 'selected_benchmark_patch.json'}`",
            "- Imported, validated files are copied under `imported/`.",
            "- Do not place generated metric/result artifacts here as proof of benchmark performance.",
            "",
        ]
    )


def _normalize_task_type(task_type: str) -> str:
    normalized = task_type.strip().replace("-", "_")
    if normalized not in SELECTED_BENCHMARK_CODEX_TASK_TYPES:
        raise ValueError(f"Unsupported selected benchmark Codex task type: {task_type}")
    return normalized


def _expected_files(task_type: str) -> list[str]:
    by_type = {
        "implement_trace_generator": [
            "src/gapforge/selected_benchmark/trace_generator.py",
            "src/gapforge/selected_benchmark/scenarios.py",
            "src/gapforge/selected_benchmark/labels.py",
            "tests/test_selected_benchmark.py",
        ],
        "implement_monitor_baseline": [
            "src/gapforge/selected_benchmark/monitors.py",
            "src/gapforge/selected_benchmark/baselines.py",
            "tests/test_selected_benchmark.py",
        ],
        "implement_sequential_metrics": [
            "src/gapforge/selected_benchmark/metrics.py",
            "src/gapforge/selected_benchmark/sequential.py",
            "src/gapforge/selected_benchmark/power.py",
            "tests/test_selected_benchmark.py",
        ],
        "implement_smoke_runner": [
            "src/gapforge/selected_benchmark/workspace.py",
            "src/gapforge/selected_benchmark/experiment.py",
            "src/gapforge/results/parser.py",
            "tests/test_selected_benchmark.py",
        ],
        "debug_selected_benchmark": [
            "src/gapforge/selected_benchmark/",
            "tests/test_selected_benchmark.py",
        ],
        "improve_benchmark_report": [
            "src/gapforge/selected_benchmark/spec.py",
            "src/gapforge/selected_benchmark/baselines.py",
            "src/gapforge/selected_benchmark/experiment.py",
            "tests/test_selected_benchmark.py",
        ],
    }
    return by_type[task_type]


def _validation_commands(task_type: str) -> list[str]:
    commands = ["python -m pytest tests/test_selected_benchmark.py"]
    if task_type in {"implement_sequential_metrics", "implement_smoke_runner", "debug_selected_benchmark"}:
        commands.append("gapforge selected-benchmark-run --workspace-id <workspace-id> --run-type smoke")
    commands.append("make ci")
    return commands


def _trace_schema() -> dict[str, Any]:
    return {
        "AgentTrace": _dataclass_fields(AgentTrace),
        "TraceStep": _dataclass_fields(TraceStep),
        "TraceDataset": _dataclass_fields(TraceDataset),
        "required_labels": [
            "synthetic",
            "honest",
            "collusive",
            "ambiguous",
            "benign_coordination",
            "explicit_collusion",
        ],
        "observability_modes": ["transcript_visible", "action_only"],
        "main_metric_rule": "Ambiguous traces are excluded from main low-FPR metrics unless explicitly specified.",
    }


def _dataclass_fields(cls: type[Any]) -> list[str]:
    return list(getattr(cls, "__dataclass_fields__", {}).keys())


def _validate_patch_file(relative_path: str, content: str) -> list[str]:
    issues: list[str] = []
    path = Path(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        issues.append(f"Invalid output path `{relative_path}`; path must stay inside the task code workspace.")
    if path.parts and path.parts[0] not in {"src", "tests", "docs", "configs", "scripts", "README.md"}:
        issues.append(f"Invalid output path `{relative_path}`; expected source, tests, docs, configs, scripts, or README.")
    lowered_path = relative_path.lower()
    lowered = content.lower()
    if any(part in lowered_path for part in ("/results/", "results/", "/reports/result_summary", "metric_results.json")):
        issues.append(f"Rejected `{relative_path}` because generated result artifacts must not be imported from Codex patches.")
    fake_terms = [
        "fake result",
        "fabricated result",
        "mock result",
        "hard-coded result",
        '"fake": true',
        "'fake': true",
        '"accuracy": 0.',
        "'accuracy': 0.",
        '"f1": 0.',
        "'f1': 0.",
        '"auroc": 0.',
        "'auroc': 0.",
        "we achieved",
        "results show",
        "outperforms",
    ]
    if any(term in lowered for term in fake_terms):
        issues.append(f"Rejected `{relative_path}` because it appears to contain fake or unsupported result claims.")
    if "sequentialmetricresult(" in lowered and "prediction" not in lowered and "trace" not in lowered:
        issues.append(f"Rejected `{relative_path}` because metric results must be computed from predictions/traces.")
    return issues


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:8]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
