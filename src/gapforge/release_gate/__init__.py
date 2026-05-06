"""Release-gate helpers for GapForge."""

from gapforge.release_gate.parser import ReleaseGateStatus, parse_release_gate
from gapforge.release_gate.report import render_v04_release_gate_markdown
from gapforge.release_gate.v04 import V04CampaignGateAssessment, V04ReleaseGateEnforcer, V04ReleaseGateResult
from gapforge.release_gate.v05 import (
    V05CampaignQualityAssessment,
    V05ReleaseGateEnforcer,
    V05ReleaseGateResult,
    render_v05_release_gate_markdown,
)
from gapforge.release_gate.v06 import (
    V06ReleaseGateEnforcer,
    V06ReleaseGateResult,
    V06WorkspaceEmpiricalAssessment,
    render_v06_release_gate_markdown,
)

__all__ = [
    "ReleaseGateStatus",
    "V04CampaignGateAssessment",
    "V04ReleaseGateEnforcer",
    "V04ReleaseGateResult",
    "V05CampaignQualityAssessment",
    "V05ReleaseGateEnforcer",
    "V05ReleaseGateResult",
    "V06ReleaseGateEnforcer",
    "V06ReleaseGateResult",
    "V06WorkspaceEmpiricalAssessment",
    "parse_release_gate",
    "render_v04_release_gate_markdown",
    "render_v05_release_gate_markdown",
    "render_v06_release_gate_markdown",
]
