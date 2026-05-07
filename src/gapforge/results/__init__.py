"""Experiment result parsing and empirical claim helpers."""

from gapforge.results.aggregate import ResultAggregator, render_aggregate_results_markdown
from gapforge.results.database import ResultDatabaseBuilder, render_result_table_markdown
from gapforge.results.error_analysis import ErrorAnalysisBuilder, render_error_analysis_report
from gapforge.results.parser import ResultParser
from gapforge.results.slices import SliceAnalysisBuilder, render_error_slice_markdown
from gapforge.results.statistics import (
    ResultStatisticsAnalyzer,
    binomial_confidence_interval,
    bootstrap_confidence_interval,
    render_analysis_report_markdown,
)
from gapforge.results.tables import render_empirical_claims_table, render_metric_results_table, render_result_summary_markdown

__all__ = [
    "ResultAggregator",
    "ResultDatabaseBuilder",
    "ErrorAnalysisBuilder",
    "ResultParser",
    "ResultStatisticsAnalyzer",
    "SliceAnalysisBuilder",
    "binomial_confidence_interval",
    "bootstrap_confidence_interval",
    "render_aggregate_results_markdown",
    "render_analysis_report_markdown",
    "render_empirical_claims_table",
    "render_error_analysis_report",
    "render_error_slice_markdown",
    "render_metric_results_table",
    "render_result_table_markdown",
    "render_result_summary_markdown",
]
