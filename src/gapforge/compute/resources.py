"""Resource request validation for experiment manifests."""

from __future__ import annotations

from gapforge.compute.environments import detect_compute_environments
from gapforge.models import ComputeCheckResult, ComputeEnvironment, Provenance, ResourceRequest
from gapforge.state import utc_now_iso


def validate_resource_request(
    request: ResourceRequest,
    environments: list[ComputeEnvironment] | None = None,
) -> ComputeCheckResult:
    envs = environments if environments is not None else detect_compute_environments()
    environment_type = request.environment_type or "local"
    target = _find_environment(envs, environment_type)
    checks = {
        "requested_environment": environment_type,
        "requested_cpu_count": str(request.cpu_count),
        "requested_memory_gb": str(request.memory_gb),
        "requested_gpu_count": str(request.gpu_count),
        "requested_wall_time_minutes": str(request.wall_time_minutes),
        "requested_disk_gb": str(request.disk_gb),
    }
    warnings: list[str] = []
    blockers: list[str] = []
    if target is None:
        blockers.append(f"Requested compute environment `{environment_type}` is not known.")
        status = "unavailable"
    else:
        checks.update(
            {
                "available": str(target.available).lower(),
                "available_cpu_count": str(target.cpu_count),
                "available_memory_gb": str(target.memory_gb),
                "available_gpu_count": str(target.gpu_count),
            }
        )
        if not target.available:
            blockers.append(f"Requested compute environment `{environment_type}` is unavailable.")
        if request.cpu_count > 0 and target.cpu_count > 0 and request.cpu_count > target.cpu_count:
            blockers.append(f"Requested {request.cpu_count} CPUs but only {target.cpu_count} are visible.")
        if request.memory_gb > 0 and target.memory_gb > 0 and request.memory_gb > target.memory_gb:
            blockers.append(f"Requested {request.memory_gb:g} GB memory but only {target.memory_gb:g} GB are visible.")
        if request.gpu_count > 0 and (not target.cuda_available or target.gpu_count < request.gpu_count):
            blockers.append(f"GPU request requires {request.gpu_count} GPU(s), but {target.gpu_count} CUDA GPU(s) are available.")
        if environment_type in {"docker", "slurm"}:
            warnings.append(f"`{environment_type}` manifests are not executed by the local runner yet; use dry-run or a future runner.")
        status = "available" if not blockers else "unavailable"
        if warnings and not blockers:
            status = "degraded"
    return ComputeCheckResult(
        environment_id=environment_type,
        status=status,
        checks=checks,
        warnings=warnings,
        blockers=blockers,
        provenance=Provenance(
            created_by_skill="resource-validation",
            timestamp=utc_now_iso(),
            reasoning_summary="Validated an experiment manifest resource request against detected compute environments.",
        ),
    )


def resource_request_is_default(request: ResourceRequest) -> bool:
    return (
        request.cpu_count == 1
        and request.memory_gb == 0
        and request.gpu_count == 0
        and request.wall_time_minutes == 0
        and request.disk_gb == 0
        and request.environment_type == "local"
    )


def _find_environment(environments: list[ComputeEnvironment], environment_type: str) -> ComputeEnvironment | None:
    normalized = "gpu_local" if environment_type == "gpu" else environment_type
    return next((item for item in environments if item.id == normalized or item.environment_type == normalized), None)
