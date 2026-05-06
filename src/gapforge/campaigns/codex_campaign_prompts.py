"""Prompt renderers for campaign-level Codex/GPT-5.4 task packs."""

from __future__ import annotations

from gapforge.campaigns import CampaignState


def render_campaign_task_markdown(campaign_state: CampaignState, task_id: str, task_type: str, expected_outputs: list[str]) -> str:
    campaign = campaign_state.campaign
    lines = [
        f"# GapForge Campaign Task: {task_type}",
        "",
        "You are Codex/GPT-5.4 working inside a GapForge research campaign task pack.",
        "",
        "## Objective",
        "",
        _task_objective(task_type),
        "",
        "## Campaign Context",
        "",
        f"- Campaign ID: `{campaign.id}`",
        f"- Project ID: `{campaign.project_id}`",
        f"- Topic: {campaign.topic}",
        f"- Mode: `{campaign.mode}`",
        f"- Source profile: `{campaign.source_profile}`",
        f"- Runs: {', '.join(campaign.run_ids) or 'none'}",
        f"- Existing task IDs: {', '.join(campaign.task_ids) or 'none'}",
        "",
        "## Inputs To Inspect",
        "",
        "- Read `campaign_context.json` first.",
        "- Read `task_context.json` next; it contains retrieval-selected papers, sections, evidence spans, valid IDs, and context limits.",
        "- Read `input_manifest.json` and only use listed artifacts. Use `artifact_summaries` before opening large files.",
        "- Use `expected_outputs.json` as the output contract.",
        "- Use `schema_examples.json` for shape examples, not as facts.",
        "- Follow `validation_rules.md`, `evidence_rules.md`, `novelty_rules.md`, and `stop_rules.md`.",
        "",
        "## Required Output Files",
        "",
    ]
    lines.extend(f"- `outputs/{name}`" for name in expected_outputs)
    lines.extend(
        [
            "",
            "## Grounding Rules",
            "",
            "- Never invent citations, URLs, paper IDs, evidence spans, datasets, metrics, or results.",
            "- Cite only known paper IDs and EvidenceSpan locators from the input manifest.",
            "- Output JSON patches only for required JSON files.",
            "- Store concise public reasoning summaries only; do not store hidden chain-of-thought.",
            "- Mark uncertainty explicitly.",
            "- Reject or downgrade unsupported ideas.",
            "- Explicitly list missing searches when coverage is insufficient.",
            "- Stop or recommend a stop condition if evidence is insufficient.",
            "",
            "## Failure Conditions",
            "",
            "- Any fake citation or unknown paper ID will be rejected.",
            "- Any high-confidence result without evidence will be rejected.",
            "- Any novelty claim without closest prior work or explicit unknown status will be rejected.",
            "",
            "## Validate And Import",
            "",
            "After writing outputs, run:",
            "",
            "```bash",
            f"gapforge validate-import-all --task-id {task_id}",
            f"gapforge repair-agent-output --task-id {task_id} --latest-invalid --handoff",
            "```",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_rules(title: str, rules: list[str]) -> str:
    return "# " + title + "\n\n" + "\n".join(f"- {rule}" for rule in rules).rstrip() + "\n"


def _task_objective(task_type: str) -> str:
    objectives = {
        "campaign_planning": "Create a cautious campaign plan with proposed next steps and a risk register.",
        "literature_scout": "Propose source searches and paper-prioritization requests without fabricating results.",
        "deep_reader_batch": "Produce evidence-located notes, claims, and evidence spans for a batch of known papers.",
        "gap_synthesis": "Synthesize evidence-backed gaps and counterevidence requests from known artifacts.",
        "novelty_reviewer": "Compare candidate ideas against closest prior work and list missing searches.",
        "experiment_architect": "Draft executable experiment protocols, baseline requests, and reproducibility checklists.",
        "reviewer_panel": "Attack the campaign's strongest direction with reviewer-style objections and required fixes.",
        "campaign_stop_decision": "Decide whether the campaign should stop, continue, or refuse recommendation under weak evidence.",
    }
    return objectives.get(task_type, "Complete the campaign task using only listed artifacts and validated JSON patches.")
