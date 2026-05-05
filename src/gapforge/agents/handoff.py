"""Manual Codex/GPT-5.4 handoff instructions for agent task packs."""

from __future__ import annotations

from pathlib import Path

from gapforge.models import AgentTaskSpec


def write_handoff(task_spec: AgentTaskSpec, pack_dir: Path, *, model: str = "gpt-5.4") -> Path:
    """Write a concrete handoff file for external Codex execution."""

    handoff_path = pack_dir / "HANDOFF.md"
    handoff_path.write_text(render_handoff(task_spec, pack_dir, model=model), encoding="utf-8")
    return handoff_path


def render_handoff(task_spec: AgentTaskSpec, pack_dir: Path, *, model: str = "gpt-5.4") -> str:
    outputs_dir = pack_dir / "outputs"
    expected_files = "\n".join(f"- `{filename}`" for filename in task_spec.required_output_files) or "- See `expected_output_schema.json`"
    return f"""# GapForge Codex/GPT-5.4 Handoff

Task ID: `{task_spec.id}`
Run ID: `{task_spec.run_id}`
Project ID: `{task_spec.project_id or "none"}`
Skill: `{task_spec.skill_name}`
Task type: `{task_spec.task_type}`
Recommended model: `{model}`

## What To Do

1. Open this task pack directory:
   `{pack_dir}`
2. Use Codex with `{model}` to inspect:
   - `TASK.md`
   - `input_manifest.json`
   - `artifact_links.json`
   - `expected_output_schema.json`
   - schema examples in `expected_output_schema.json`
   - `evidence_rules.md`
   - `uncertainty_rules.md`
3. Write only the expected output files into:
   `{outputs_dir}`
4. Do not invent citations, paper IDs, evidence span IDs, results, or prior work.
5. Use only known paper IDs and EvidenceSpan locators from the task pack.
6. Store concise public reasoning summaries only. Do not store hidden chain-of-thought.
7. Mark uncertainty explicitly and downgrade unsupported claims.

## Expected Output Files

{expected_files}

## Validate And Import

After Codex writes outputs, run:

```bash
gapforge validate-agent-output --task-id {task_spec.id}
gapforge import-agent-output --task-id {task_spec.id}
gapforge repair-agent-output --task-id {task_spec.id} --path <output-file.json>
gapforge attest-agent-run --task-id {task_spec.id} --agent codex --model {model} --method task_pack --attester "<name>"
gapforge actual-run-status --run-id {task_spec.run_id}
```

This handoff counts as an actual Codex/GPT-5.4 run only after validation passes, the output is imported, a human attests
that Codex/GPT-5.4 produced it, and human review accepts the result.
"""
