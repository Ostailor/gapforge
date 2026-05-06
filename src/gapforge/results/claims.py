"""Empirical claim construction from parsed metric results."""

from __future__ import annotations

import hashlib

from gapforge.models import EmpiricalClaim, ExperimentExecutionRecord, MetricResult, Provenance
from gapforge.state import utc_now_iso


def claims_from_metric_results(
    *,
    execution: ExperimentExecutionRecord,
    metric_results: list[MetricResult],
    limitations: list[str],
) -> list[EmpiricalClaim]:
    """Create empirical claims only when artifact-backed metric results exist."""

    if not metric_results:
        return []
    claims: list[EmpiricalClaim] = []
    for result in metric_results:
        status = _claim_status(execution)
        claim_limitations = list(limitations)
        if execution.status == "failed":
            claim_limitations.append("Execution failed; metric output is preserved as a failed or incomplete empirical result.")
        confidence = "medium" if status == "supported" and result.confidence_interval else "low"
        claims.append(
            EmpiricalClaim(
                id=f"empirical-claim-{_stable_id(execution.id, result.id)}",
                text=_claim_text(execution, result),
                execution_id=execution.id,
                metric_result_ids=[result.id],
                status=status,
                confidence=confidence,
                limitations=claim_limitations,
                provenance=Provenance(
                    created_by_skill="empirical-claim-ledger",
                    source_ids=[execution.id, result.id, result.raw_artifact_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Created an empirical claim from an artifact-backed metric result.",
                ),
            )
        )
    return claims


def _claim_status(execution: ExperimentExecutionRecord) -> str:
    if execution.status == "complete":
        return "supported"
    if execution.status == "failed":
        return "failed"
    return "uncertain"


def _claim_text(execution: ExperimentExecutionRecord, result: MetricResult) -> str:
    base = f"Execution `{execution.id}` recorded `{result.metric_id}` = {result.value:g}"
    if result.dataset_id:
        base += f" on dataset `{result.dataset_id}`"
    if result.baseline_id:
        base += f" against baseline `{result.baseline_id}`"
    if execution.status == "failed":
        return base + ", but the execution failed and cannot support a positive result claim."
    return base + "."


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
