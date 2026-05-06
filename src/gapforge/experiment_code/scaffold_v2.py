"""Workspace-based runnable experiment code scaffolding for v0.6."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiment_code.smoke import expected_smoke_files
from gapforge.experiment_code.templates import (
    render_baselines_py,
    render_config,
    render_data_py,
    render_metrics_py,
    render_pyproject,
    render_readme,
    render_run_experiment_py,
    render_run_smoke_sh,
    render_test_baselines_py,
    render_test_data_py,
    render_test_metrics_py,
)
from gapforge.experiment_code.validation import ExperimentCodeValidation, render_experiment_code_validation, validate_experiment_code
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import BaselineRecord, DatasetRecord, ExperimentProtocol, MetricRecord
from gapforge.project_memory import ProjectMemoryManager


class ExperimentCodeScaffolderV2:
    """Generate runnable code inside an existing experiment workspace."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.dataset_registry = DatasetRegistry(config)
        self.baseline_registry = BaselineRegistry(config)
        self.metric_registry = MetricRegistry(config)

    def scaffold(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        protocol = self._protocol_for_workspace(workspace.project_id, workspace.direction_id, workspace.experiment_protocol_id)
        datasets = self.dataset_registry.list_datasets(workspace_id)
        baselines = self.baseline_registry.list_baselines(workspace_id)
        metrics = self.metric_registry.list_metrics(workspace_id)
        if not metrics and protocol is not None:
            metrics = self.metric_registry.register_builtin_metrics(workspace_id, protocol.metrics)

        code_root = Path(workspace.root_dir) / "code"
        files = self._files(
            workspace_id=workspace_id,
            protocol=protocol,
            datasets=datasets,
            baselines=baselines,
            metrics=metrics,
        )
        for relative_path, content in files.items():
            path = code_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        script = code_root / "scripts" / "run_smoke.sh"
        script.chmod(0o755)
        (code_root / "SCAFFOLD_MANIFEST.json").write_text(
            json.dumps(
                {
                    "workspace_id": workspace_id,
                    "scaffold_version": "v0.6",
                    "files": sorted(files),
                    "results": "not run",
                    "fixture_data": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        workspace.status = "ready"
        self.workspace_manager._write_workspace(workspace)
        self.workspace_manager._update_project_workspace(workspace)
        return code_root

    def status(self, workspace_id: str) -> str:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        code_root = Path(workspace.root_dir) / "code"
        missing = [path.relative_to(code_root) for path in expected_smoke_files(code_root) if not path.exists()]
        lines = [
            f"# Experiment Code Status `{workspace_id}`",
            "",
            f"- Code root: `{code_root}`",
            f"- Scaffolded: {str((code_root / 'pyproject.toml').exists()).lower()}",
            f"- Missing expected files: {len(missing)}",
            "",
            "## Missing Files",
            "",
        ]
        lines.extend([f"- `{item}`" for item in missing] or ["- none"])
        lines.extend(
            [
                "",
                "## Execution Boundary",
                "",
                "This status describes code scaffold readiness only. It is not an experiment execution record.",
                "",
            ]
        )
        return "\n".join(lines)

    def validate(self, workspace_id: str, *, run_smoke: bool = True) -> ExperimentCodeValidation:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        code_root = Path(workspace.root_dir) / "code"
        result = validate_experiment_code(workspace_id=workspace_id, code_root=code_root, run_smoke=run_smoke)
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "experiment_code_validation.md").write_text(render_experiment_code_validation(result), encoding="utf-8")
        return result

    def _files(
        self,
        *,
        workspace_id: str,
        protocol: ExperimentProtocol | None,
        datasets: list[DatasetRecord],
        baselines: list[BaselineRecord],
        metrics: list[MetricRecord],
    ) -> dict[str, str]:
        return {
            "pyproject.toml": render_pyproject(),
            "README.md": render_readme(
                workspace_id=workspace_id,
                protocol=protocol,
                datasets=datasets,
                baselines=baselines,
                metrics=metrics,
            ),
            "src/__init__.py": '"""GapForge experiment scaffold package. No results are included."""\n',
            "src/data.py": render_data_py(datasets, protocol),
            "src/baselines.py": render_baselines_py(baselines, protocol),
            "src/metrics.py": render_metrics_py(metrics, protocol),
            "src/run_experiment.py": render_run_experiment_py(workspace_id),
            "tests/test_metrics.py": render_test_metrics_py(),
            "tests/test_baselines.py": render_test_baselines_py(),
            "tests/test_data.py": render_test_data_py(),
            "configs/smoke.json": render_config(run_type="smoke", workspace_id=workspace_id, metrics=metrics),
            "configs/pilot.json": render_config(run_type="pilot", workspace_id=workspace_id, metrics=metrics),
            "scripts/run_smoke.sh": render_run_smoke_sh(),
        }

    def _protocol_for_workspace(self, project_id: str, direction_id: str, protocol_id: str) -> ExperimentProtocol | None:
        program = self.project_manager.load_project(project_id)
        if protocol_id:
            return next((item for item in program.experiment_protocols if item.id == protocol_id), None)
        return next((item for item in program.experiment_protocols if item.direction_id == direction_id), None)
