"""Diagnostics for actual Codex/GPT-5.4 real-run readiness."""

from gapforge.diagnostics.agent_path import inspect_agent_path
from gapforge.diagnostics.environment import inspect_agent_environment
from gapforge.diagnostics.real_run import (
    build_real_run_diagnostic,
    diagnose_canary_markdown,
    diagnose_run_agent_markdown,
    write_real_run_diagnostic,
)
from gapforge.diagnostics.report import render_real_run_diagnostic_markdown

__all__ = [
    "build_real_run_diagnostic",
    "diagnose_canary_markdown",
    "diagnose_run_agent_markdown",
    "inspect_agent_environment",
    "inspect_agent_path",
    "render_real_run_diagnostic_markdown",
    "write_real_run_diagnostic",
]
