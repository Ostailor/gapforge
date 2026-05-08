"""Versioned pilot specifications."""

from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import PilotSpec, Provenance
from gapforge.state import utc_now_iso

LOW_FPR_COLLUSION = "low_fpr_collusion"
LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"

PILOT_DOCUMENTS = {
    "spec": "PILOT_SPEC.md",
    "acceptance": "ACCEPTANCE_CRITERIA.md",
    "review": "REVIEW_CHECKLIST.md",
}

LOW_FPR_REQUIRED_ARTIFACTS = [
    "project_record",
    "campaign_record",
    "live_source_diagnostics",
    "search_strategy",
    "search_rounds",
    "source_coverage_report",
    "paper_canonicalization_report",
    "prior_work_recall_assessment",
    "codex_synthesis_task_outputs",
    "novelty_dossiers",
    "related_work_matrix",
    "research_direction_or_refusal",
    "experiment_protocol",
    "benchmark_or_fixture_experiment_plan",
    "empirical_artifact_status",
    "manuscript_draft_or_refusal_report",
    "reviewer_panel",
    "rebuttal_revision_plan",
    "final_pilot_report",
]


def default_pilot_specs() -> list[PilotSpec]:
    return [low_fpr_collusion_spec()]


def low_fpr_collusion_spec() -> PilotSpec:
    return PilotSpec(
        id=LOW_FPR_COLLUSION,
        name=LOW_FPR_COLLUSION,
        topic=LOW_FPR_TOPIC,
        project_name="v0.9 low-FPR collusion pilot",
        source_profile="ai_safety",
        required_artifacts=list(LOW_FPR_REQUIRED_ARTIFACTS),
        acceptance_modes=["defensible_direction", "correct_refusal", "product_failure"],
        required_reviews=["human_research_quality_review", "external_pilot_review"],
        provenance=Provenance(
            created_by_skill="pilot-spec",
            source_ids=["docs/pilots/low_fpr_collusion/PILOT_SPEC.md"],
            timestamp=utc_now_iso(),
            reasoning_summary="Defined the v0.9 low-FPR collusion external pilot specification.",
        ),
    )


def get_pilot_spec(name: str) -> PilotSpec:
    normalized = name.strip()
    for spec in default_pilot_specs():
        if normalized in {spec.id, spec.name}:
            return spec
    raise ValueError(f"Unknown pilot {name!r}. Available pilot: {LOW_FPR_COLLUSION}.")


def render_pilot_list() -> str:
    lines = ["# Pilot Specs", ""]
    for spec in default_pilot_specs():
        lines.extend(
            [
                f"- `{spec.id}`: {spec.topic}",
                f"  - Source profile: `{spec.source_profile}`",
                f"  - Project name: {spec.project_name}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_pilot_document(config: GapForgeConfig, name: str, document: str = "spec") -> str:
    spec = get_pilot_spec(name)
    if document == "all":
        return "\n\n".join(render_pilot_document(config, name, item) for item in PILOT_DOCUMENTS)
    filename = PILOT_DOCUMENTS.get(document)
    if filename is None:
        raise ValueError(f"Unknown pilot document {document!r}. Expected one of: {', '.join(sorted(PILOT_DOCUMENTS))}.")
    path = pilot_docs_dir(config, spec.id) / filename
    if not path.exists():
        raise FileNotFoundError(f"Pilot document not found: {path}")
    return path.read_text(encoding="utf-8")


def pilot_docs_dir(config: GapForgeConfig, name: str) -> Path:
    workspace_docs = config.root / "docs" / "pilots" / name
    if workspace_docs.exists():
        return workspace_docs
    return Path(__file__).resolve().parents[3] / "docs" / "pilots" / name
