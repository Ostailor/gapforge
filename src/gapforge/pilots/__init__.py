"""Pilot specifications, runner, status, and reports."""

from gapforge.pilots.external_review import ExternalPilotReviewManager, render_external_review_report
from gapforge.pilots.idea_gate import IdeaGate, render_idea_gate
from gapforge.pilots.outcome import assess_pilot_outcome, render_pilot_outcome
from gapforge.pilots.reports import render_pilot_acceptance, render_pilot_report
from gapforge.pilots.runner import PilotRunner
from gapforge.pilots.specs import (
    LOW_FPR_COLLUSION,
    LOW_FPR_TOPIC,
    default_pilot_specs,
    get_pilot_spec,
    render_pilot_document,
    render_pilot_list,
)
from gapforge.pilots.status import (
    PilotStore,
    build_acceptance_summary,
    build_status_payload,
    classify_record,
    render_pilot_status_json,
)

__all__ = [
    "LOW_FPR_COLLUSION",
    "LOW_FPR_TOPIC",
    "IdeaGate",
    "ExternalPilotReviewManager",
    "PilotRunner",
    "PilotStore",
    "assess_pilot_outcome",
    "build_acceptance_summary",
    "build_status_payload",
    "classify_record",
    "default_pilot_specs",
    "get_pilot_spec",
    "render_pilot_acceptance",
    "render_idea_gate",
    "render_external_review_report",
    "render_pilot_document",
    "render_pilot_list",
    "render_pilot_outcome",
    "render_pilot_report",
    "render_pilot_status_json",
]
