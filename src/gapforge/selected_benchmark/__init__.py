"""Formal benchmark specification for the v2.1 selected idea."""

from gapforge.selected_benchmark.baselines import (
    MonitorBaselineManager,
    MonitorBaselineRun,
    MonitorCalibrationRecord,
    default_monitor_baselines,
    render_monitor_baseline_report,
    render_pilot_baseline_report,
)
from gapforge.selected_benchmark.codex_tasks import (
    SelectedBenchmarkCodexImportResult,
    SelectedBenchmarkCodexTask,
    SelectedBenchmarkCodexTaskManager,
    render_selected_benchmark_codex_import_result,
)
from gapforge.selected_benchmark.collusive_alternatives import (
    CollusiveAlternativeManager,
    CollusiveDistributionReport,
    CollusiveScenario,
    default_collusive_scenarios,
    render_collusive_distribution_report,
)
from gapforge.selected_benchmark.experiment import (
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkRunResult,
    render_selected_benchmark_run_report,
)
from gapforge.selected_benchmark.honest_null import (
    HonestNullDistributionReport,
    HonestNullManager,
    HonestNullScenario,
    default_honest_null_scenarios,
    render_honest_null_report,
)
from gapforge.selected_benchmark.manuscript import (
    SelectedBenchmarkManuscript,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkPaperPackage,
    render_selected_benchmark_manuscript,
)
from gapforge.selected_benchmark.metrics import (
    SequentialAuditMetricPlan,
    SequentialMetricManager,
    SequentialMetricResult,
    render_low_fpr_audit_check,
    render_metric_plan,
    render_sequential_metric_report,
)
from gapforge.selected_benchmark.monitors import MonitorBaseline, MonitorPrediction
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisManager, PilotAnalysisResult, render_selected_pilot_report
from gapforge.selected_benchmark.pilot_dataset import (
    PilotDatasetBuilder,
    PilotTraceDataset,
    render_pilot_dataset_card,
    render_pilot_trace_dataset_report,
)
from gapforge.selected_benchmark.pilot_manuscript import (
    SelectedPilotManuscript,
    SelectedPilotManuscriptManager,
    SelectedPilotPaperPackage,
    render_selected_pilot_manuscript,
)
from gapforge.selected_benchmark.pilot_power import (
    PilotPowerAssessment,
    PilotPowerManager,
    PilotPowerPlan,
    render_pilot_power_assessment,
    render_pilot_power_plan,
)
from gapforge.selected_benchmark.pilot_run import (
    PilotRunManager,
    SelectedPilotExecution,
    SelectedPilotRunManifest,
    render_selected_pilot_status,
)
from gapforge.selected_benchmark.related_work import (
    REQUIRED_RELATED_WORK_CATEGORIES,
    SelectedBenchmarkRelatedWorkManager,
    SelectedNoveltyPositioning,
    SelectedPriorWorkRecall,
    SelectedRelatedWorkEntry,
    SelectedRelatedWorkMatrix,
    render_novelty_positioning,
    render_prior_work_recall,
    render_related_work_matrix,
)
from gapforge.selected_benchmark.reviewer import (
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkReviewPanel,
    render_selected_benchmark_fix_list,
    render_selected_benchmark_review_panel,
)
from gapforge.selected_benchmark.scenarios import ScenarioDefinition, default_scenarios
from gapforge.selected_benchmark.spec import (
    SelectedBenchmarkManager,
    SequentialSpecificityBenchmarkSpec,
    render_selected_benchmark_report,
)
from gapforge.selected_benchmark.tasks import BenchmarkTaskFamily, default_task_families
from gapforge.selected_benchmark.threat_model import CollusionThreatModel, default_threat_model
from gapforge.selected_benchmark.trace_generator import (
    AgentTrace,
    SyntheticTraceGenerator,
    TraceDataset,
    TraceStep,
    render_trace_dataset_report,
    render_trace_list,
)
from gapforge.selected_benchmark.workspace import (
    SelectedBenchmarkWorkspaceConfig,
    SelectedBenchmarkWorkspaceManager,
    render_selected_workspace_readme,
)

__all__ = [
    "AgentTrace",
    "BenchmarkTaskFamily",
    "CollusiveAlternativeManager",
    "CollusiveDistributionReport",
    "CollusiveScenario",
    "CollusionThreatModel",
    "HonestNullDistributionReport",
    "HonestNullManager",
    "HonestNullScenario",
    "MonitorBaseline",
    "MonitorBaselineManager",
    "MonitorBaselineRun",
    "MonitorCalibrationRecord",
    "MonitorPrediction",
    "PilotPowerAssessment",
    "PilotPowerManager",
    "PilotPowerPlan",
    "PilotAnalysisManager",
    "PilotAnalysisResult",
    "PilotRunManager",
    "PilotDatasetBuilder",
    "PilotTraceDataset",
    "SelectedPilotExecution",
    "SelectedPilotManuscript",
    "SelectedPilotManuscriptManager",
    "SelectedPilotPaperPackage",
    "SelectedPilotRunManifest",
    "ScenarioDefinition",
    "SequentialAuditMetricPlan",
    "SequentialMetricManager",
    "SequentialMetricResult",
    "SequentialSpecificityBenchmarkSpec",
    "SelectedBenchmarkManager",
    "SelectedBenchmarkCodexImportResult",
    "SelectedBenchmarkCodexTask",
    "SelectedBenchmarkCodexTaskManager",
    "SelectedBenchmarkExperimentRunner",
    "SelectedBenchmarkManuscript",
    "SelectedBenchmarkManuscriptManager",
    "SelectedBenchmarkPaperPackage",
    "SelectedBenchmarkRunResult",
    "SelectedBenchmarkRelatedWorkManager",
    "SelectedBenchmarkReviewerPanelBuilder",
    "SelectedBenchmarkReviewPanel",
    "SelectedNoveltyPositioning",
    "SelectedPriorWorkRecall",
    "SelectedRelatedWorkEntry",
    "SelectedRelatedWorkMatrix",
    "SelectedBenchmarkWorkspaceConfig",
    "SelectedBenchmarkWorkspaceManager",
    "SyntheticTraceGenerator",
    "TraceDataset",
    "TraceStep",
    "default_monitor_baselines",
    "default_collusive_scenarios",
    "default_honest_null_scenarios",
    "default_scenarios",
    "default_task_families",
    "default_threat_model",
    "render_low_fpr_audit_check",
    "render_collusive_distribution_report",
    "render_honest_null_report",
    "render_metric_plan",
    "render_monitor_baseline_report",
    "render_pilot_baseline_report",
    "render_pilot_power_assessment",
    "render_pilot_power_plan",
    "render_selected_pilot_report",
    "render_selected_pilot_manuscript",
    "render_selected_pilot_status",
    "render_pilot_dataset_card",
    "render_pilot_trace_dataset_report",
    "render_selected_benchmark_fix_list",
    "render_selected_benchmark_manuscript",
    "render_selected_benchmark_review_panel",
    "render_selected_benchmark_run_report",
    "render_selected_benchmark_report",
    "render_selected_benchmark_codex_import_result",
    "REQUIRED_RELATED_WORK_CATEGORIES",
    "render_novelty_positioning",
    "render_prior_work_recall",
    "render_related_work_matrix",
    "render_selected_workspace_readme",
    "render_sequential_metric_report",
    "render_trace_dataset_report",
    "render_trace_list",
]
