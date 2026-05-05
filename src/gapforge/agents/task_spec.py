"""Agent task-spec construction."""

from __future__ import annotations

from pathlib import Path

from gapforge.agents.records import utc_now_iso
from gapforge.models import AgentTaskSpec, Provenance, ResearchRunState
from gapforge.state import slugify, utc_now_compact

_SKILL_TO_TASK = {
    "deep-reading": (
        "deep_reading",
        "agent-deep-reading-patch",
        ["paper_notes_patch.json", "claims_patch.json", "evidence_spans_patch.json"],
    ),
    "deep_reading": (
        "deep_reading",
        "agent-deep-reading-patch",
        ["paper_notes_patch.json", "claims_patch.json", "evidence_spans_patch.json"],
    ),
    "gap-mining": (
        "gap_mining",
        "agent-gap-mining-patch",
        ["gaps_patch.json", "gap_evidence_matrices_patch.json", "claims_patch.json"],
    ),
    "gap_mining": (
        "gap_mining",
        "agent-gap-mining-patch",
        ["gaps_patch.json", "gap_evidence_matrices_patch.json", "claims_patch.json"],
    ),
    "novelty-gate": (
        "novelty",
        "agent-novelty-dossier-patch",
        ["novelty_dossiers_patch.json", "novelty_assessments_patch.json", "rejected_ideas_patch.json"],
    ),
    "novelty_gate": (
        "novelty",
        "agent-novelty-dossier-patch",
        ["novelty_dossiers_patch.json", "novelty_assessments_patch.json", "rejected_ideas_patch.json"],
    ),
    "reviewer-simulation": (
        "reviewer",
        "agent-reviewer-patch",
        ["reviewer_objections_patch.json", "reviewer_summaries_patch.json"],
    ),
    "reviewer_simulation": (
        "reviewer",
        "agent-reviewer-patch",
        ["reviewer_objections_patch.json", "reviewer_summaries_patch.json"],
    ),
    "related-work": ("related_work", "agent-related-work-patch", ["related_work_matrix_patch.json"]),
    "related_work": ("related_work", "agent-related-work-patch", ["related_work_matrix_patch.json"]),
    "manuscript": ("manuscript", "agent-manuscript-patch", ["paper_package_patch.json", "manuscript_outline.md"]),
    "experiment-code": ("experiment_code", "agent-experiment-code-patch", ["experiment_code_patch.json"]),
}


def create_agent_task_spec(
    state: ResearchRunState,
    *,
    skill_name: str,
    gap_id: str = "",
    paper_id: str = "",
    project_id: str = "",
    instructions: str = "",
) -> AgentTaskSpec:
    normalized_skill = skill_name.strip().lower().replace("_", "-")
    task_type, schema_name, required_files = _SKILL_TO_TASK.get(
        normalized_skill,
        (normalized_skill.replace("-", "_"), f"agent-{slugify(normalized_skill)}", [f"{slugify(normalized_skill)}_agent_output.json"]),
    )
    target_parts = [part for part in [normalized_skill, gap_id, paper_id] if part]
    task_id = f"agent-{utc_now_compact()}-{slugify('-'.join(target_parts) or normalized_skill)}"
    task_instructions = instructions.strip() or _default_instructions(normalized_skill, gap_id=gap_id, paper_id=paper_id)
    return AgentTaskSpec(
        id=task_id,
        run_id=state.run_id,
        project_id=project_id or str(state.config.get("project_id", "")),
        skill_name=normalized_skill,
        task_type=task_type,
        instructions=task_instructions,
        input_artifacts=_existing_input_artifacts(state),
        output_schema_name=schema_name,
        required_output_files=required_files,
        evidence_rules=[
            "Cite existing EvidenceSpan locators for claims, results, limitations, and prior-work comparisons whenever available.",
            "Use only paper IDs present in papers.json or explicitly recorded search results.",
            "Do not invent citations, URLs, paper IDs, results, datasets, metrics, or prior work.",
            "High-confidence claims require locator-backed evidence.",
        ],
        uncertainty_rules=[
            "Mark unsupported or abstract-only conclusions as low confidence or unknown.",
            "Novelty must be unknown unless closest prior work is listed and compared.",
            "If coverage is weak or searches are missing, recommend next searches instead of overclaiming.",
            "Store concise public reasoning summaries only; do not store hidden chain-of-thought.",
        ],
        max_runtime_notes="Keep runtime notes concise and public. Do not include secrets or hidden chain-of-thought.",
        created_at=utc_now_iso(),
        provenance=Provenance(
            created_by_skill="agent-task",
            source_ids=[item for item in [gap_id, paper_id] if item],
            timestamp=utc_now_iso(),
            reasoning_summary="Created a validation-gated agent task spec for optional Codex/GPT-5.4 research assistance.",
        ),
    )


def agent_handoff_checklist(task_spec: AgentTaskSpec, *, execution_method: str = "task_pack") -> list[str]:
    method = execution_method.strip().lower().replace("-", "_")
    if method == "direct":
        return [
            "Confirm GAPFORGE_ENABLE_REAL_RUNS=1 and a configured direct runner command.",
            "Run the task through Codex/GPT-5.4.",
            "Validate imported output patches before any research-state mutation.",
            "Record actual-run status and human acceptance.",
        ]
    if method == "fake":
        return [
            "Run FakeAgentClient only for deterministic integration testing.",
            "Do not count fake outputs as actual-run acceptance.",
        ]
    return [
        "Generate the task pack.",
        "Have Codex/GPT-5.4 inspect TASK.md and the linked artifacts externally.",
        "Place output files in the task outputs directory or pass explicit output paths.",
        "Run validation before import.",
        "Record an attestation naming Codex/GPT-5.4 and the execution method.",
        "Review actual-run status before claiming acceptance.",
    ]


def _existing_input_artifacts(state: ResearchRunState) -> list[str]:
    run_dir = Path(state.run_dir)
    candidates = [
        "topic.md",
        "papers.json",
        "paper_sections.json",
        "evidence_spans.json",
        "paper_notes.json",
        "claims.json",
        "gaps.json",
        "gap_evidence_matrix.json",
        "novelty_dossiers.json",
        "source_coverage.md",
        "coverage_stopping_assessment.md",
        "claim_ledger.md",
        "final_report.md",
    ]
    return [str(run_dir / name) for name in candidates if (run_dir / name).exists()]


def _default_instructions(skill_name: str, *, gap_id: str, paper_id: str) -> str:
    target = f" Target gap: {gap_id}." if gap_id else ""
    target += f" Target paper: {paper_id}." if paper_id else ""
    if skill_name == "deep-reading":
        return (
            "Produce a structured, evidence-located paper reading note from the provided artifacts."
            f"{target} Distinguish full-text evidence from abstract-only metadata."
        )
    if skill_name == "novelty-gate":
        return (
            "Compare the target idea against closest prior work from provided papers, retrieval results, and dossiers."
            f"{target} Reject or mark unknown when prior-work coverage is insufficient."
        )
    if skill_name == "gap-mining":
        return (
            "Propose only evidence-backed gaps with supporting and counterevidence locators."
            f"{target} Unsupported model ideas should be rejected or low confidence."
        )
    return f"Complete the {skill_name} research task using only the provided artifacts.{target}"
