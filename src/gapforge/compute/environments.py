"""Compute environment inventory and reporting."""

from __future__ import annotations

from gapforge.compute.docker import detect_docker
from gapforge.compute.gpu import detect_cuda
from gapforge.compute.local import detect_local_environment
from gapforge.compute.slurm import detect_slurm
from gapforge.models import ComputeCheckResult, ComputeEnvironment, Provenance
from gapforge.state import utc_now_iso


def detect_compute_environments() -> list[ComputeEnvironment]:
    local_env = detect_local_environment()
    cuda_available, gpu_count, gpu_notes = detect_cuda()
    docker_available, docker_notes = detect_docker()
    slurm_available, slurm_notes = detect_slurm()
    return [
        local_env,
        ComputeEnvironment(
            id="gpu_local",
            name="Local CUDA/GPU",
            environment_type="gpu_local",
            available=cuda_available,
            python_version=local_env.python_version,
            cuda_available=cuda_available,
            gpu_count=gpu_count,
            cpu_count=local_env.cpu_count,
            memory_gb=local_env.memory_gb,
            notes=gpu_notes,
            provenance=_provenance("compute-gpu", "Detected optional local CUDA/GPU resources."),
        ),
        ComputeEnvironment(
            id="docker",
            name="Docker",
            environment_type="docker",
            available=docker_available,
            python_version=local_env.python_version,
            cpu_count=local_env.cpu_count,
            memory_gb=local_env.memory_gb,
            docker_available=docker_available,
            notes=docker_notes,
            provenance=_provenance("compute-docker", "Detected optional Docker command availability."),
        ),
        ComputeEnvironment(
            id="slurm",
            name="Slurm",
            environment_type="slurm",
            available=slurm_available,
            python_version=local_env.python_version,
            cpu_count=local_env.cpu_count,
            memory_gb=local_env.memory_gb,
            slurm_available=slurm_available,
            notes=slurm_notes,
            provenance=_provenance("compute-slurm", "Detected optional Slurm command availability."),
        ),
    ]


def check_environment(environment: str) -> ComputeCheckResult:
    environment_id = _normalize_environment(environment)
    env = next((item for item in detect_compute_environments() if item.id == environment_id), None)
    if env is None:
        return ComputeCheckResult(
            environment_id=environment_id,
            status="unavailable",
            blockers=[f"Unknown compute environment: {environment}"],
            provenance=_provenance("compute-check", "Rejected an unknown compute environment."),
        )
    checks = {
        "available": str(env.available).lower(),
        "environment_type": env.environment_type,
        "cpu_count": str(env.cpu_count),
        "memory_gb": str(env.memory_gb),
        "gpu_count": str(env.gpu_count),
        "cuda_available": str(env.cuda_available).lower(),
        "docker_available": str(env.docker_available).lower(),
        "slurm_available": str(env.slurm_available).lower(),
    }
    blockers = [] if env.available else [env.notes[0] if env.notes else f"{env.name} is unavailable."]
    return ComputeCheckResult(
        environment_id=env.id,
        status="available" if env.available else "unavailable",
        checks=checks,
        warnings=[] if env.available else env.notes[1:],
        blockers=blockers,
        provenance=_provenance("compute-check", f"Checked compute environment {env.id}."),
    )


def render_compute_status(environments: list[ComputeEnvironment] | None = None) -> str:
    envs = environments if environments is not None else detect_compute_environments()
    lines = ["# Compute Status", ""]
    for env in envs:
        lines.extend(
            [
                f"## {env.name}",
                "",
                f"- ID: `{env.id}`",
                f"- Type: `{env.environment_type}`",
                f"- Available: {str(env.available).lower()}",
                f"- Python: `{env.python_version or 'unknown'}`",
                f"- CPU count: {env.cpu_count}",
                f"- Memory GB: {env.memory_gb}",
                f"- CUDA available: {str(env.cuda_available).lower()}",
                f"- GPU count: {env.gpu_count}",
                f"- Docker available: {str(env.docker_available).lower()}",
                f"- Slurm available: {str(env.slurm_available).lower()}",
                "",
                "Notes:",
            ]
        )
        lines.extend([f"- {note}" for note in env.notes] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_compute_check(result: ComputeCheckResult) -> str:
    lines = [
        f"# Compute Check `{result.environment_id}`",
        "",
        f"- Status: `{result.status}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(result.checks.items())] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _normalize_environment(environment: str) -> str:
    if environment == "gpu":
        return "gpu_local"
    return environment


def _provenance(skill: str, summary: str) -> Provenance:
    return Provenance(created_by_skill=skill, timestamp=utc_now_iso(), reasoning_summary=summary)
