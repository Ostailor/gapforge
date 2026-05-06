"""Experiment result parsing and empirical claim helpers."""

from gapforge.results.parser import ResultParser
from gapforge.results.statistics import (
    ResultStatisticsAnalyzer,
    binomial_confidence_interval,
    bootstrap_confidence_interval,
    render_analysis_report_markdown,
)
from gapforge.results.tables import render_empirical_claims_table, render_metric_results_table, render_result_summary_markdown

__all__ = [
    "ResultParser",
    "ResultStatisticsAnalyzer",
    "binomial_confidence_interval",
    "bootstrap_confidence_interval",
    "render_analysis_report_markdown",
    "render_empirical_claims_table",
    "render_metric_results_table",
    "render_result_summary_markdown",
]
