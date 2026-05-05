"""Handoff instructions for campaign-level Codex/GPT-5.4 tasks."""

from __future__ import annotations

from pathlib import Path

from gapforge.campaigns import CampaignState

_TASK_TYPES = {
    "campaign_planning",
    "literature_scout",
    "deep_reader_batch",
    "gap_synthesis",
    "novelty_reviewer",
    "experiment_architect",
    "reviewer_panel",
    "campaign_stop_decision",
}


def write_campaign_handoff(
    state: CampaignState,
    task_id: str,
    pack_dir: Path,
    *,
    model: str = "gpt-5.4",
    expected_outputs: list[str] | None = None,
) -> Path:
    path = pack_dir / "HANDOFF.md"
    path.write_text(render_campaign_handoff(state, task_id, pack_dir, model=model, expected_outputs=expected_outputs), encoding="utf-8")
    return path


def render_campaign_handoff(
    state: CampaignState,
    task_id: str,
    pack_dir: Path,
    *,
    model: str = "gpt-5.4",
    expected_outputs: list[str] | None = None,
) -> str:
    task_type = _task_type_from_id(task_id)
    outputs = expected_outputs or []
    output_lines = "\n".join(f"- `outputs/{name}`" for name in outputs) or "- See `expected_outputs.json`"
    return f"""# GapForge Campaign Codex/GPT-5.4 Handoff

Campaign ID: `{state.campaign.id}`
Project ID: `{state.campaign.project_id}`
Task ID: `{task_id}`
Task type: `{task_type}`
Recommended model: `{model}`

## Codex Instructions

1. Open this task pack directory:
   `{pack_dir}`
2. Read `CAMPAIGN_TASK.md`, `task_context.json`, `input_manifest.json`, `expected_outputs.json`,
   `schema_examples.json`, `evidence_rules.md`, `novelty_rules.md`, `validation_rules.md`, and `stop_rules.md`.
3. Inspect only the artifacts listed in `input_manifest.json`.
4. Write the expected JSON files into:
   `{pack_dir / "outputs"}`
5. Do not invent citations, prior work, paper IDs, EvidenceSpan IDs, results, datasets, or metrics.
6. Use public reasoning summaries only; do not store hidden chain-of-thought.
7. If evidence is insufficient, write a stop condition or missing-search request instead of overclaiming.

## Required Output Files

{output_lines}

## Validate, Import, Attest, Review

Run these after Codex writes the outputs:

```bash
gapforge campaign-validate-output --campaign-id {state.campaign.id} --task-id {task_id}
gapforge campaign-import-output --campaign-id {state.campaign.id} --task-id {task_id}
gapforge validate-import-all --campaign-id {state.campaign.id}
gapforge attest-agent-run --task-id {task_id} --agent codex --model {model} --method task_pack --attester "<name>"
gapforge campaign-review --campaign-id {state.campaign.id}
gapforge campaign-report --campaign-id {state.campaign.id}
```

This task-pack handoff can count as actual Codex/GPT-5.4 validation only after validated import, attestation, and human review.
"""


def _task_type_from_id(task_id: str) -> str:
    for task_type in _TASK_TYPES:
        if task_id.endswith(task_type):
            return task_type
    return task_id.rsplit("-", 1)[-1]
