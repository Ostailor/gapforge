"""Codex-facing task-pack prompt rendering."""

from __future__ import annotations

import json

from gapforge.models import AgentTaskSpec, ResearchRunState
from gapforge.redaction import redact_text


def render_task_markdown(state: ResearchRunState, task_spec: AgentTaskSpec, schema: dict[str, object]) -> str:
    objective = redact_text(task_spec.instructions).strip() or f"Complete the {task_spec.task_type} task."
    lines = [
        f"# GapForge Codex Research Task: {task_spec.skill_name}",
        "",
        "## Task Objective",
        "",
        objective,
        "",
        "## Exact Skill Role",
        "",
        f"You are acting as the GapForge `{task_spec.skill_name}` skill for task type `{task_spec.task_type}`.",
        "Use Codex/GPT-5.4 research-agent capabilities to inspect the supplied files and write only the expected outputs.",
        "",
        "## Inputs To Inspect",
        "",
    ]
    lines.extend(f"- `{path}`" for path in task_spec.input_artifacts)
    if not task_spec.input_artifacts:
        lines.append("- No input artifacts were found; report insufficient context instead of inventing facts.")
    lines.extend(
        [
            "",
            "## Output Files To Write",
            "",
        ]
    )
    lines.extend(f"- `outputs/{path}`" for path in task_spec.required_output_files)
    lines.extend(
        [
            "",
            "## JSON Schema",
            "",
            "The machine-readable schema is also written to `expected_output_schema.json`.",
            "",
            "```json",
            json.dumps(schema, indent=2),
            "```",
            "",
            "## Citation And Evidence Requirements",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in task_spec.evidence_rules)
    lines.extend(
        [
            "- Every `paper_id` must already exist in the run corpus or recorded search outputs.",
            "- Every `evidence_span_id` or locator must exist in `evidence_spans.json` "
            "unless it is introduced in `evidence_spans_patch.json`.",
            "- Every supported claim must include supporting evidence.",
            "- Every result claim marked high confidence must include an EvidenceSpan locator or explicit full-text locator.",
            "- Every novelty claim must list closest prior work or explicitly set novelty to unknown.",
            "",
            "## Rules Against Invented Citations",
            "",
            "- Do not invent citations, venues, URLs, DOI values, arXiv IDs, or paper IDs.",
            "- If a citation seems important but is not in the corpus, add it as a search request instead of citing it as prior work.",
            "- Do not present fixture or fallback data as real literature.",
            "",
            "## Uncertainty Rules",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in task_spec.uncertainty_rules)
    lines.extend(
        [
            "- If full text is missing, say so and lower confidence.",
            "- If closest prior work is missing, mark novelty unknown.",
            "",
            "## Reasoning Storage Rule",
            "",
            "Store only concise public reasoning summaries. Do not write hidden chain-of-thought.",
            "",
            "## Failure Conditions",
            "",
            "- Required output JSON does not parse.",
            "- Required top-level fields are missing.",
            "- Output cites papers or evidence spans not in the provided artifacts.",
            "- Output marks unsupported claims as supported or high confidence.",
            "- Output claims novelty without closest prior work or explicit unknown status.",
            "",
            "## Current Run Snapshot",
            "",
            f"- Topic: {state.topic.text}",
            f"- Papers: {len(state.papers)}",
            f"- Paper sections: {len(state.paper_sections)}",
            f"- Evidence spans: {len(state.evidence_spans)}",
            f"- Claims: {len(state.claims)}",
            f"- Gaps: {len(state.gaps)}",
            f"- Novelty dossiers: {len(state.novelty_dossiers)}",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_rules(title: str, rules: list[str]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines).rstrip() + "\n"
