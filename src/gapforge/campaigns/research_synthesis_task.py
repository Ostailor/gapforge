"""Codex task pack for real-literature research synthesis."""

from __future__ import annotations

from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.config import GapForgeConfig


def create_research_synthesis_task(config: GapForgeConfig, campaign_id: str) -> Path:
    """Create a validation-gated Codex/GPT-5.4 task pack for research synthesis."""

    pack_dir = create_campaign_task_pack(config, campaign_id, "research_synthesis")
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    prompt = render_research_synthesis_prompt(campaign_state.campaign.topic, pack_dir)
    (pack_dir / "RESEARCH_SYNTHESIS_PROMPT.md").write_text(prompt, encoding="utf-8")
    task_path = pack_dir / "CAMPAIGN_TASK.md"
    existing = task_path.read_text(encoding="utf-8")
    task_path.write_text(
        existing.rstrip() + "\n\n## Research Synthesis Instructions\n\nSee `RESEARCH_SYNTHESIS_PROMPT.md`.\n", encoding="utf-8"
    )
    return pack_dir


def render_research_synthesis_prompt(topic: str, pack_dir: Path) -> str:
    """Render the task-specific prompt contract for Codex handoff."""

    outputs = [
        "research_directions_patch.json",
        "gap_evidence_matrices_patch.json",
        "novelty_dossiers_patch.json",
        "related_work_matrix_patch.json",
        "uncertainty_register.json",
        "search_requests.json",
    ]
    lines = [
        "# Research Synthesis Task",
        "",
        "You are Codex/GPT-5.4 synthesizing research directions for a GapForge real-literature campaign.",
        "",
        f"Topic: {topic}",
        f"Task pack: `{pack_dir}`",
        "",
        "## Inputs You Must Inspect",
        "",
        "- `task_context.json`: source coverage, search rounds, top papers, evidence spans, closest prior candidates, "
        "counterevidence, source policy gaps, rejected ideas, and human constraints.",
        "- `input_manifest.json`: allowed artifact links, known paper IDs, known EvidenceSpan IDs, and known locators.",
        "- `expected_outputs.json` and `schema_examples.json`: exact file contracts and minimal shapes.",
        "- `validation_rules.md`, `evidence_rules.md`, `novelty_rules.md`, and `stop_rules.md`.",
        "",
        "## Output Files",
        "",
    ]
    lines.extend(f"- Write JSON only to `outputs/{name}`." for name in outputs)
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Propose at most 3 research directions.",
            "- Every direction must cite known evidence spans or locators.",
            "- Every direction must list closest prior work using known paper IDs.",
            "- Every direction must include a risk that it is not novel.",
            "- Unknown novelty must remain `unknown`; do not upgrade it rhetorically.",
            "- Do not invent citations, paper IDs, URLs, datasets, metrics, or results.",
            "- Do not write fake experimental results. Expected outcomes must remain hypothetical.",
            "- Include missing searches in `search_requests.json` or the relevant patch object.",
            "- Store only concise public reasoning summaries; do not store hidden chain-of-thought.",
            "",
            "## Validation Consequences",
            "",
            "- Directions without evidence are rejected.",
            "- Directions with fake prior work are rejected.",
            "- Strong novelty without a passing prior-work recall gate is rejected.",
            "- More than 3 directions causes partial rejection.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
