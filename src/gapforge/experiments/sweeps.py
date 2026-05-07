"""Experiment sweeps, seed plans, and ablation plans."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.jobs.scheduler import JobScheduler
from gapforge.models import AblationPlan, ExperimentRunManifest, ExperimentSweep, JobQueue, Provenance, SeedPlan, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso

DEFAULT_MAX_GENERATED_MANIFESTS = 25


class ExperimentSweepManager:
    """Create and inspect systematic experiment variations."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def create_parameter_sweep(
        self,
        *,
        workspace_id: str,
        base_manifest_id: str,
        name: str,
        parameters: dict[str, list[str]],
        confirm_large: bool = False,
    ) -> ExperimentSweep:
        base_manifest = self._require_manifest(workspace_id, base_manifest_id)
        combinations = _parameter_combinations(parameters)
        if len(combinations) > DEFAULT_MAX_GENERATED_MANIFESTS and not confirm_large:
            raise ValueError(f"Sweep would generate {len(combinations)} manifests; rerun with confirm_large=True or CLI --confirm-large.")
        generated_ids: list[str] = []
        for index, parameter_diff in enumerate(combinations, start=1):
            generated_ids.append(
                self._create_variant_manifest(workspace_id, base_manifest, parameter_diff, run_type="sweep", index=index).id
            )
        sweep = ExperimentSweep(
            id=_unique_record_id(self._sweeps_dir(workspace_id), "sweep", name),
            workspace_id=workspace_id,
            name=name,
            base_manifest_id=base_manifest_id,
            parameters=parameters,
            generated_manifest_ids=generated_ids,
            status="planned",
            provenance=_provenance(
                "experiment-sweep",
                [workspace_id, base_manifest_id],
                "Generated experiment manifests for an explicit parameter sweep.",
            ),
        )
        self._write_record(workspace_id, "sweep", sweep)
        return sweep

    def create_seed_plan(
        self,
        *,
        workspace_id: str,
        seeds: list[int],
        rationale: str = "",
        base_manifest_id: str = "",
    ) -> SeedPlan:
        base_manifest = self._require_manifest(workspace_id, base_manifest_id) if base_manifest_id else self._latest_manifest(workspace_id)
        generated_ids: list[str] = []
        for seed in seeds:
            generated = self.workspace_manager.create_manifest(
                workspace_id=workspace_id,
                run_type="seed",
                run_name=f"{base_manifest.run_name or base_manifest.id} seed {seed}",
                dataset_ids=list(base_manifest.dataset_ids),
                baseline_ids=list(base_manifest.baseline_ids),
                metric_ids=list(base_manifest.metric_ids),
                config_path=base_manifest.config_path,
                command=base_manifest.command,
                expected_outputs=list(base_manifest.expected_outputs),
                random_seed=seed,
                resource_request=base_manifest.resource_request,
            )
            generated_ids.append(generated.id)
        seed_plan = SeedPlan(
            id=_unique_record_id(self._sweeps_dir(workspace_id), "seed-plan", "seeds"),
            workspace_id=workspace_id,
            seeds=seeds,
            rationale=rationale,
            generated_manifest_ids=generated_ids,
            provenance=_provenance(
                "seed-plan",
                [workspace_id, base_manifest.id],
                "Generated seeded experiment manifests for stochastic evaluation.",
            ),
        )
        self._write_record(workspace_id, "seed-plan", seed_plan)
        return seed_plan

    def create_ablation_plan(
        self,
        *,
        workspace_id: str,
        name: str,
        factors: list[str],
        controls: list[str],
        expected_comparisons: list[str],
        base_manifest_id: str = "",
    ) -> AblationPlan:
        generated_ids: list[str] = []
        if base_manifest_id:
            base_manifest = self._require_manifest(workspace_id, base_manifest_id)
            for index, factor in enumerate(factors, start=1):
                generated_ids.append(
                    self._create_variant_manifest(
                        workspace_id,
                        base_manifest,
                        {f"ablation.disable_{slugify(factor)}": True},
                        run_type="ablation",
                        index=index,
                    ).id
                )
        plan = AblationPlan(
            id=_unique_record_id(self._sweeps_dir(workspace_id), "ablation", name),
            workspace_id=workspace_id,
            name=name,
            factors=factors,
            controls=controls,
            expected_comparisons=expected_comparisons,
            generated_manifest_ids=generated_ids,
            provenance=_provenance(
                "ablation-plan",
                [workspace_id, base_manifest_id],
                "Recorded an ablation plan with explicit controls and expected comparisons.",
            ),
        )
        self._write_record(workspace_id, "ablation", plan)
        return plan

    def submit_sweep(self, sweep_id: str) -> JobQueue:
        sweep = self.load_sweep(sweep_id)
        scheduler = JobScheduler(self.config)
        queue: JobQueue | None = None
        for manifest_id in sweep.generated_manifest_ids:
            job = scheduler.submit(workspace_id=sweep.workspace_id, manifest_id=manifest_id)
            queue = scheduler.load_queue(job.queue_id)
        if queue is None:
            raise ValueError(f"Sweep {sweep_id} has no generated manifests to submit.")
        sweep.status = "submitted"
        self._write_record(sweep.workspace_id, "sweep", sweep)
        return queue

    def sweep_status(self, sweep_id: str) -> dict[str, Any]:
        sweep = self.load_sweep(sweep_id)
        jobs = JobScheduler(self.config).list_jobs(sweep.workspace_id)
        relevant = [job for job in jobs if job.manifest_id in set(sweep.generated_manifest_ids)]
        counts = {
            status: len([job for job in relevant if job.status == status])
            for status in ["queued", "running", "complete", "failed", "cancelled"]
        }
        status = "complete" if relevant and counts["complete"] == len(sweep.generated_manifest_ids) else sweep.status
        if counts["failed"]:
            status = "failed"
        elif counts["queued"] or counts["running"]:
            status = "running"
        return {"sweep_id": sweep.id, "workspace_id": sweep.workspace_id, "status": status, **counts}

    def load_sweep(self, sweep_id: str) -> ExperimentSweep:
        path = self._find_record_path("sweep", sweep_id)
        return from_dict(ExperimentSweep, json.loads(path.read_text(encoding="utf-8")))

    def _create_variant_manifest(
        self,
        workspace_id: str,
        base_manifest: ExperimentRunManifest,
        parameter_diff: dict[str, Any],
        *,
        run_type: str,
        index: int,
    ) -> ExperimentRunManifest:
        config_path = self._write_variant_config(workspace_id, base_manifest, parameter_diff, run_type=run_type, index=index)
        command = _replace_config_path(base_manifest.command, base_manifest.config_path, config_path)
        return self.workspace_manager.create_manifest(
            workspace_id=workspace_id,
            run_type=run_type,
            run_name=f"{base_manifest.run_name or base_manifest.id} {run_type} {index}",
            dataset_ids=list(base_manifest.dataset_ids),
            baseline_ids=list(base_manifest.baseline_ids),
            metric_ids=list(base_manifest.metric_ids),
            config_path=str(config_path),
            command=command,
            expected_outputs=list(base_manifest.expected_outputs),
            random_seed=base_manifest.random_seed,
            resource_request=base_manifest.resource_request,
        )

    def _write_variant_config(
        self,
        workspace_id: str,
        base_manifest: ExperimentRunManifest,
        parameter_diff: dict[str, Any],
        *,
        run_type: str,
        index: int,
    ) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        base_config = _load_base_config(base_manifest)
        for key, value in parameter_diff.items():
            _set_dotted(base_config, key, _coerce_value(value))
        base_config["_gapforge"] = {
            "base_manifest_id": base_manifest.id,
            "parameter_diff": parameter_diff,
            "generated_by": run_type,
        }
        config_path = Path(workspace.root_dir) / "configs" / f"{run_type}-{base_manifest.id}-{index}.json"
        config_path.write_text(json.dumps(base_config, indent=2) + "\n", encoding="utf-8")
        return config_path

    def _require_manifest(self, workspace_id: str, manifest_id: str) -> ExperimentRunManifest:
        for manifest in self.workspace_manager.list_manifests(workspace_id):
            if manifest.id == manifest_id:
                return manifest
        raise FileNotFoundError(f"No experiment manifest found for {manifest_id}")

    def _latest_manifest(self, workspace_id: str) -> ExperimentRunManifest:
        manifests = self.workspace_manager.list_manifests(workspace_id)
        if not manifests:
            raise ValueError(f"Workspace {workspace_id} has no manifest to use as a base.")
        return manifests[-1]

    def _sweeps_dir(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        path = Path(workspace.root_dir) / "sweeps"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_record(self, workspace_id: str, record_type: str, record: ExperimentSweep | AblationPlan | SeedPlan) -> None:
        path = self._sweeps_dir(workspace_id) / f"{record_type}-{record.id}.json"
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        if isinstance(record, AblationPlan):
            (self._sweeps_dir(workspace_id) / f"{record.id}.md").write_text(render_ablation_plan_markdown(record), encoding="utf-8")

    def _find_record_path(self, record_type: str, record_id: str) -> Path:
        pattern = f"experiment_workspaces/*/sweeps/{record_type}-{record_id}.json"
        for project_dir in self.config.project_root.glob("*"):
            for path in project_dir.glob(pattern):
                return path
        raise FileNotFoundError(f"No {record_type} record found for {record_id}")


def render_ablation_plan_markdown(plan: AblationPlan) -> str:
    lines = [f"# Ablation Plan `{plan.id}`", "", f"- Workspace ID: `{plan.workspace_id}`", f"- Name: {plan.name}", "", "## Factors", ""]
    lines.extend([f"- {item}" for item in plan.factors] or ["- none"])
    lines.extend(["", "## Controls", ""])
    lines.extend([f"- {item}" for item in plan.controls] or ["- none"])
    lines.extend(["", "## Expected Comparisons", ""])
    lines.extend([f"- {item}" for item in plan.expected_comparisons] or ["- none"])
    lines.extend(["", "## Generated Manifests", ""])
    lines.extend([f"- `{item}`" for item in plan.generated_manifest_ids] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_sweep_status(status: dict[str, Any]) -> str:
    lines = [
        f"# Sweep Status `{status['sweep_id']}`",
        "",
        f"- Workspace ID: `{status['workspace_id']}`",
        f"- Status: `{status['status']}`",
        "",
    ]
    for key in ["queued", "running", "complete", "failed", "cancelled"]:
        lines.append(f"- {key}: {status.get(key, 0)}")
    return "\n".join(lines).rstrip() + "\n"


def parse_parameter_specs(specs: list[str]) -> dict[str, list[str]]:
    parameters: dict[str, list[str]] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"Invalid parameter spec `{spec}`; expected dotted.path=value1,value2.")
        key, raw_values = spec.split("=", 1)
        values = [value.strip() for value in raw_values.split(",") if value.strip()]
        if not key.strip() or not values:
            raise ValueError(f"Invalid parameter spec `{spec}`; key and at least one value are required.")
        parameters[key.strip()] = values
    return parameters


def parse_seed_list(raw_seeds: str) -> list[int]:
    seeds: list[int] = []
    for raw_seed in raw_seeds.split(","):
        stripped = raw_seed.strip()
        if stripped:
            seeds.append(int(stripped))
    if not seeds:
        raise ValueError("At least one seed is required.")
    return seeds


def _parameter_combinations(parameters: dict[str, list[str]]) -> list[dict[str, str]]:
    keys = list(parameters)
    value_lists = [parameters[key] for key in keys]
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*value_lists)]


def _load_base_config(base_manifest: ExperimentRunManifest) -> dict[str, Any]:
    path = Path(base_manifest.config_path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"base_config": data}
    return {"base_manifest_id": base_manifest.id}


def _set_dotted(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.setdefault(part, {})
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _coerce_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _replace_config_path(command: str, old_config: str, new_config: Path) -> str:
    if old_config and old_config in command:
        return command.replace(old_config, str(new_config))
    if command:
        return command
    return f"python -m run_experiment --config {new_config}"


def _unique_record_id(base_dir: Path, prefix: str, name: str) -> str:
    base = f"{prefix}-{slugify(name) or 'default'}"
    candidate = base
    suffix = 2
    while any(base_dir.glob(f"*-{candidate}.json")):
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _provenance(skill: str, source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill=skill, source_ids=[item for item in source_ids if item], timestamp=utc_now_iso(), reasoning_summary=summary
    )
