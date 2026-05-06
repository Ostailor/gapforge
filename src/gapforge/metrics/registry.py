"""Workspace-scoped metric registry and built-in templates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics.reporting import render_metric_card_markdown, render_metric_registry_markdown, render_statistical_plan_markdown
from gapforge.metrics.stats import build_statistical_test_plan
from gapforge.models import ExperimentProtocol, ExperimentWorkspace, MetricRecord, Provenance, StatisticalTestPlan, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso


class MetricRegistry:
    """Register metrics and write statistical plans for experiment workspaces."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def register_metric(
        self,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        metric_type: str = "custom",
        formula: str = "",
        higher_is_better: bool = True,
        required_inputs: list[str] | None = None,
        edge_cases: list[str] | None = None,
    ) -> MetricRecord:
        self.workspace_manager.load_workspace(workspace_id)
        template = builtin_metric_templates().get(_normalize_name(name))
        record = template if template is not None else None
        if record is None:
            record = MetricRecord(
                id=_unique_metric_id(self._metric_dir(workspace_id), name),
                name=name,
                description=description,
                metric_type=metric_type,
                formula=formula,
                higher_is_better=higher_is_better,
                required_inputs=required_inputs or [],
                edge_cases=edge_cases or [],
            )
        else:
            record = _copy_metric_record(
                record,
                metric_id=_unique_metric_id(self._metric_dir(workspace_id), record.name),
                description=description or record.description,
                source_ids=[workspace_id, _normalize_name(name)],
                reasoning_summary="Registered metric from built-in template.",
            )
        if template is None:
            record.provenance = Provenance(
                created_by_skill="metric-registry",
                source_ids=[workspace_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Registered an explicit experiment metric.",
            )
        return self._persist_record(workspace_id, record)

    def register_builtin_metrics(self, workspace_id: str, names: list[str]) -> list[MetricRecord]:
        return [self.register_metric(workspace_id=workspace_id, name=name) for name in names]

    def list_metrics(self, workspace_id: str) -> list[MetricRecord]:
        metric_dir = self._metric_dir(workspace_id)
        if not metric_dir.exists():
            return []
        return [
            from_dict(MetricRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(metric_dir.glob("metric-*.record.json"))
        ]

    def load_metric(self, metric_id: str) -> MetricRecord:
        for project_dir in self.config.project_root.glob("*"):
            for path in (project_dir / "experiment_workspaces").glob("*/metrics/metric-*.record.json"):
                record = from_dict(MetricRecord, json.loads(path.read_text(encoding="utf-8")))
                if record.id == metric_id:
                    return record
        raise FileNotFoundError(f"No metric registered with id {metric_id}")

    def render_card(self, metric_id: str) -> str:
        return render_metric_card_markdown(self.load_metric(metric_id))

    def create_stats_plan(self, *, workspace_id: str = "", experiment_id: str = "") -> StatisticalTestPlan:
        workspace = self.workspace_manager.load_workspace(workspace_id) if workspace_id else None
        protocol = self._protocol_for_workspace(workspace) if workspace is not None else self._protocol_by_id(experiment_id)
        metrics = self.list_metrics(workspace.id) if workspace is not None else []
        if not metrics and protocol is not None and workspace is not None:
            metrics = self.register_builtin_metrics(workspace.id, protocol.metrics)
        if not metrics and protocol is not None and workspace is None:
            metrics = metric_records_from_names(protocol.metrics)
        plan = build_statistical_test_plan(experiment_protocol=protocol, metrics=metrics, workspace_id=workspace.id if workspace else "")
        if workspace is not None:
            self._write_stats_plan(workspace.id, plan, metrics)
        return plan

    def readiness_blockers(self, workspace_id: str) -> list[str]:
        metrics = self.list_metrics(workspace_id)
        if not metrics:
            return ["No explicit metric records are registered for this experiment workspace."]
        if any("false positive" in (metric.name + " " + metric.description).lower() or "fpr" in metric.name.lower() for metric in metrics):
            return [
                "Low-FPR metric requires confidence intervals in the statistical plan."
                for plan in [self.create_stats_plan(workspace_id=workspace_id)]
                if "confidence" not in plan.confidence_interval_method.lower()
            ]
        return []

    def _persist_record(self, workspace_id: str, record: MetricRecord) -> MetricRecord:
        metric_dir = self._metric_dir(workspace_id)
        existing = next((item for item in self.list_metrics(workspace_id) if item.name.lower() == record.name.lower()), None)
        if existing is not None:
            record.id = existing.id
        (metric_dir / f"{record.id}.record.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        (metric_dir / f"{record.id}.card.md").write_text(render_metric_card_markdown(record), encoding="utf-8")
        self._write_registry_markdown(workspace_id)
        return record

    def _write_registry_markdown(self, workspace_id: str) -> None:
        records = self.list_metrics(workspace_id)
        (self._metric_dir(workspace_id) / "metric_registry.md").write_text(render_metric_registry_markdown(records), encoding="utf-8")

    def _write_stats_plan(self, workspace_id: str, plan: StatisticalTestPlan, metrics: list[MetricRecord]) -> None:
        plans_dir = self._metric_dir(workspace_id) / "stats_plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / f"{plan.id}.json").write_text(json.dumps(to_plain(plan), indent=2) + "\n", encoding="utf-8")
        (plans_dir / f"{plan.id}.md").write_text(render_statistical_plan_markdown(plan, metrics), encoding="utf-8")

    def _metric_dir(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        metric_dir = Path(workspace.root_dir) / "metrics"
        metric_dir.mkdir(parents=True, exist_ok=True)
        return metric_dir

    def _protocol_for_workspace(self, workspace: ExperimentWorkspace) -> ExperimentProtocol | None:
        program = self.project_manager.load_project(workspace.project_id)
        return next((item for item in program.experiment_protocols if item.id == workspace.experiment_protocol_id), None)

    def _protocol_by_id(self, experiment_id: str) -> ExperimentProtocol | None:
        for project in self.project_manager.list_projects():
            program = self.project_manager.load_project(project.id)
            protocol = next((item for item in program.experiment_protocols if item.id == experiment_id), None)
            if protocol is not None:
                return protocol
        return None


def builtin_metric_templates() -> dict[str, MetricRecord]:
    templates = [
        MetricRecord(
            id="template-false-positive-rate",
            name="false positive rate",
            description="Fraction of negative examples incorrectly flagged positive.",
            metric_type="detection",
            formula="FP / (FP + TN)",
            higher_is_better=False,
            required_inputs=["false_positive_count", "true_negative_count"],
            edge_cases=["Rare false positives require large negative pools.", "Always report confidence intervals."],
        ),
        MetricRecord(
            id="template-true-positive-rate",
            name="true positive rate",
            description="Fraction of positive examples correctly flagged positive.",
            metric_type="detection",
            formula="TP / (TP + FN)",
            higher_is_better=True,
            required_inputs=["true_positive_count", "false_negative_count"],
            edge_cases=["Undefined when there are no positives."],
        ),
        MetricRecord(
            id="template-precision",
            name="precision",
            description="Fraction of positive predictions that are correct.",
            metric_type="classification",
            formula="TP / (TP + FP)",
            higher_is_better=True,
            required_inputs=["true_positive_count", "false_positive_count"],
            edge_cases=["Can look high under very low alert rates; report support counts."],
        ),
        MetricRecord(
            id="template-recall",
            name="recall",
            description="Fraction of positives recovered.",
            metric_type="classification",
            formula="TP / (TP + FN)",
            higher_is_better=True,
            required_inputs=["true_positive_count", "false_negative_count"],
            edge_cases=["Must be interpreted with threshold and false-positive rate."],
        ),
        MetricRecord(
            id="template-auroc",
            name="AUROC",
            description="Area under ROC curve.",
            metric_type="ranking",
            formula="P(score_positive > score_negative)",
            higher_is_better=True,
            required_inputs=["scores", "labels"],
            edge_cases=["Can obscure low-FPR behavior."],
        ),
        MetricRecord(
            id="template-auprc",
            name="AUPRC",
            description="Area under precision-recall curve.",
            metric_type="ranking",
            formula="area under precision-recall curve",
            higher_is_better=True,
            required_inputs=["scores", "labels"],
            edge_cases=["Sensitive to class prevalence."],
        ),
        MetricRecord(
            id="template-calibration-error",
            name="calibration error",
            description="Expected or binned calibration error.",
            metric_type="calibration",
            formula="weighted average |confidence - empirical accuracy|",
            higher_is_better=False,
            required_inputs=["probabilities", "labels"],
            edge_cases=["Bin choice changes estimates."],
        ),
        MetricRecord(
            id="template-abstention-rate",
            name="abstention rate",
            description="Fraction of examples where the system abstains.",
            metric_type="detection",
            formula="abstentions / total_examples",
            higher_is_better=False,
            required_inputs=["abstention_count", "total_examples"],
            edge_cases=["Must be paired with quality metric on non-abstained examples."],
        ),
        MetricRecord(
            id="template-cost-weighted-error",
            name="cost-weighted error",
            description="Error weighted by user-specified cost matrix.",
            metric_type="cost",
            formula="sum(error_i * cost_i) / n",
            higher_is_better=False,
            required_inputs=["errors", "costs"],
            edge_cases=["Cost choices must be justified before results."],
        ),
        MetricRecord(
            id="template-runtime-latency",
            name="runtime/latency",
            description="Runtime or latency per example/request.",
            metric_type="runtime",
            formula="elapsed_time / units",
            higher_is_better=False,
            required_inputs=["elapsed_time", "unit_count"],
            edge_cases=["Report hardware, warmup, and repeated-run variance."],
        ),
    ]
    return {_normalize_name(metric.name): metric for metric in templates}


def metric_records_from_names(names: list[str]) -> list[MetricRecord]:
    """Build non-persisted metric records from protocol metric names."""
    records: list[MetricRecord] = []
    templates = builtin_metric_templates()
    for name in names:
        template = templates.get(_normalize_name(name))
        if template is not None:
            records.append(
                _copy_metric_record(
                    template,
                    metric_id=f"metric-{slugify(template.name)}",
                    source_ids=[_normalize_name(name)],
                    reasoning_summary="Planned metric from built-in template.",
                )
            )
            continue
        records.append(
            MetricRecord(
                id=f"metric-{slugify(name)}",
                name=name,
                description="Metric from experiment protocol.",
                metric_type=_infer_metric_type(name),
                formula="",
                higher_is_better=not _lower_is_better(name),
                provenance=Provenance(
                    created_by_skill="metric-registry",
                    source_ids=[_normalize_name(name)],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Planned metric from experiment protocol name.",
                ),
            )
        )
    return records


def _copy_metric_record(
    record: MetricRecord,
    *,
    metric_id: str,
    description: str | None = None,
    source_ids: list[str] | None = None,
    reasoning_summary: str = "",
) -> MetricRecord:
    return MetricRecord(
        id=metric_id,
        name=record.name,
        description=record.description if description is None else description,
        metric_type=record.metric_type,
        formula=record.formula,
        higher_is_better=record.higher_is_better,
        required_inputs=list(record.required_inputs),
        edge_cases=list(record.edge_cases),
        provenance=Provenance(
            created_by_skill="metric-registry",
            source_ids=source_ids or [],
            timestamp=utc_now_iso(),
            reasoning_summary=reasoning_summary,
        ),
    )


def _infer_metric_type(name: str) -> str:
    text = name.lower()
    if any(term in text for term in ["false positive", "true positive", "fpr", "tpr", "specificity", "abstention"]):
        return "detection"
    if any(term in text for term in ["auroc", "auprc", "ranking"]):
        return "ranking"
    if "calibration" in text:
        return "calibration"
    if any(term in text for term in ["runtime", "latency"]):
        return "runtime"
    if "cost" in text:
        return "cost"
    return "custom"


def _lower_is_better(name: str) -> bool:
    text = name.lower()
    return any(term in text for term in ["false positive", "error", "cost", "runtime", "latency"])


def _unique_metric_id(metric_dir: Path, name: str) -> str:
    base = f"metric-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (metric_dir / f"{candidate}.record.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")
