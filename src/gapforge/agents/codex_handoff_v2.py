"""Concrete Codex/GPT-5.4 handoff bundles for task-pack workflows."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
from pathlib import Path
from typing import Any

from gapforge.agents.schema_validator import expected_output_files
from gapforge.models import AgentTaskSpec
from gapforge.redaction import redact_text


def write_codex_handoff_bundle(
    pack_dir: Path,
    *,
    task_id: str,
    required_files: list[str],
    schema_path: Path,
    task_file: str,
    artifact_manifest: str,
    validate_command: str,
    import_command: str,
    attestation_command: str,
    review_command: str = "",
    model: str = "gpt-5.4",
    run_id: str = "",
    campaign_id: str = "",
    repo_dir: Path | None = None,
) -> dict[str, Path]:
    """Write the v2 handoff bundle into an existing task-pack directory."""

    pack_dir = pack_dir.resolve()
    repo_dir = (repo_dir or Path.cwd()).resolve()
    outputs_dir = pack_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    minimal_dir = pack_dir / "expected_minimal_outputs"
    examples_dir = pack_dir / "output_examples"
    minimal_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    schema = _load_json(schema_path)
    skeletons = _minimal_skeletons(required_files, schema)
    examples = _example_outputs(required_files, skeletons)
    for filename in required_files:
        value = skeletons.get(filename, "")
        example_value = examples.get(filename, value)
        _write_example_file(minimal_dir / filename, value)
        _write_example_file(examples_dir / filename, example_value)
    _copy_relevant_examples(examples_dir, required_files)

    output_contract = render_output_contract(required_files, schema_path, skeletons)
    codex_prompt = render_codex_prompt(
        pack_dir,
        outputs_dir,
        required_files=required_files,
        schema_path=schema_path,
        task_file=task_file,
        artifact_manifest=artifact_manifest,
        skeletons=skeletons,
        model=model,
        run_id=run_id,
        campaign_id=campaign_id,
    )
    readme = render_readme_first(
        task_id=task_id,
        pack_dir=pack_dir,
        outputs_dir=outputs_dir,
        model=model,
        validate_command=validate_command,
        import_command=import_command,
        attestation_command=attestation_command,
        review_command=review_command,
    )
    script = render_validate_and_import_script(
        validate_command=validate_command,
        import_command=import_command,
        attestation_command=attestation_command,
        review_command=review_command,
        doctor_command=f"gapforge codex-doctor --task-id {task_id}",
        repo_dir=repo_dir,
    )
    handoff = render_handoff_v2(
        task_id=task_id,
        pack_dir=pack_dir,
        outputs_dir=outputs_dir,
        required_files=required_files,
        model=model,
        validate_command=validate_command,
        import_command=import_command,
        attestation_command=attestation_command,
        review_command=review_command,
    )

    paths = {
        "handoff": pack_dir / "HANDOFF.md",
        "prompt": pack_dir / "CODEX_PROMPT.md",
        "contract": pack_dir / "OUTPUT_CONTRACT.md",
        "script": pack_dir / "VALIDATE_AND_IMPORT.sh",
        "readme": pack_dir / "README_FIRST.md",
    }
    paths["handoff"].write_text(handoff, encoding="utf-8")
    paths["prompt"].write_text(redact_text(codex_prompt), encoding="utf-8")
    paths["contract"].write_text(output_contract, encoding="utf-8")
    paths["readme"].write_text(readme, encoding="utf-8")
    paths["script"].write_text(script, encoding="utf-8")
    paths["script"].chmod(paths["script"].stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return paths


def write_run_codex_handoff_v2(task_spec: AgentTaskSpec, pack_dir: Path, *, model: str = "gpt-5.4") -> dict[str, Path]:
    required_files = expected_output_files(task_spec)
    validate_command = f"gapforge validate-import-all --task-id {task_spec.id}"
    import_command = validate_command
    attestation_command = (
        f'gapforge attest-agent-run --task-id {task_spec.id} --agent codex --model {model} --method task_pack --attester "<name>"'
    )
    return write_codex_handoff_bundle(
        pack_dir,
        task_id=task_spec.id,
        required_files=required_files,
        schema_path=pack_dir / "expected_output_schema.json",
        task_file="TASK.md",
        artifact_manifest="artifact_links.json",
        validate_command=validate_command,
        import_command=import_command,
        attestation_command=attestation_command,
        model=model,
        run_id=task_spec.run_id,
        campaign_id=task_spec.project_id,
    )


def write_campaign_codex_handoff_v2(
    *,
    campaign_id: str,
    task_id: str,
    pack_dir: Path,
    expected_outputs: list[str],
    model: str = "gpt-5.4",
) -> dict[str, Path]:
    validate_command = f"gapforge validate-import-all --task-id {task_id}"
    import_command = validate_command
    attestation_command = (
        f'gapforge attest-agent-run --task-id {task_id} --agent codex --model {model} --method task_pack --attester "<name>"'
    )
    review_command = f'gapforge campaign-review --campaign-id {campaign_id} --accept --reviewer "<name>"'
    return write_codex_handoff_bundle(
        pack_dir,
        task_id=task_id,
        required_files=expected_outputs,
        schema_path=pack_dir / "expected_outputs.json",
        task_file="CAMPAIGN_TASK.md",
        artifact_manifest="input_manifest.json",
        validate_command=validate_command,
        import_command=import_command,
        attestation_command=attestation_command,
        review_command=review_command,
        model=model,
        campaign_id=campaign_id,
    )


def render_handoff_v2(
    *,
    task_id: str,
    pack_dir: Path,
    outputs_dir: Path,
    required_files: list[str],
    model: str,
    validate_command: str,
    import_command: str,
    attestation_command: str,
    review_command: str = "",
) -> str:
    files = "\n".join(f"- `{filename}`" for filename in required_files) or "- none"
    command_lines = _dedupe_commands(
        [validate_command, import_command, attestation_command, review_command, f"gapforge codex-doctor --task-id {task_id}"]
    )
    commands = "\n".join(command_lines)
    return f"""# GapForge Codex/GPT-5.4 Handoff

Task ID: `{task_id}`
Recommended model: `{model}`
Task pack: `{pack_dir}`
Outputs directory: `{outputs_dir}`

This handoff does not count as an actual Codex/GPT-5.4 run by itself. Actual-run evidence requires Codex execution,
validation, import, attestation, and human review where applicable.

## Start Here

1. Open `README_FIRST.md`.
2. Copy the full contents of `CODEX_PROMPT.md` into Codex/GPT-5.4.
3. Ensure Codex writes only these files into `outputs/`:

{files}

4. Run `./VALIDATE_AND_IMPORT.sh` from this task-pack directory.

## Manual Commands

```bash
{commands}
```
"""


def render_codex_prompt(
    pack_dir: Path,
    outputs_dir: Path,
    *,
    required_files: list[str],
    schema_path: Path,
    task_file: str,
    artifact_manifest: str,
    skeletons: dict[str, Any],
    model: str,
    run_id: str = "",
    campaign_id: str = "",
) -> str:
    file_list = "\n".join(f"- `{filename}`" for filename in required_files) or "- none"
    skeleton_text = "\n\n".join(_format_inline_skeleton(filename, skeletons[filename]) for filename in required_files)
    scope = f"Run ID: {run_id or 'none'}\nCampaign ID: {campaign_id or 'none'}"
    return f"""You are Codex/GPT-5.4 executing a GapForge validated task-pack workflow.

{scope}
Task pack directory:
`{pack_dir}`

Output directory:
`{outputs_dir}`

Required output files:
{file_list}

Instructions:
1. Read `{task_file}` first.
2. Read `{schema_path.name}` and obey the schema for each required output file.
3. Inspect `{artifact_manifest}` and only the task artifacts it links to.
4. Write outputs only into `{outputs_dir}`.
5. Use only known paper IDs, evidence span IDs, and EvidenceSpan locators from the task pack.
6. Do not invent citations, prior work, paper IDs, evidence spans, datasets, metrics, results, or reviewer evidence.
7. Emit JSON only for required `.json` output files. Do not put Markdown prose inside JSON files.
8. Use `unknown`, `uncertain`, low confidence, or search requests when evidence is insufficient.
9. Store concise public reasoning summaries only. Do not store hidden chain-of-thought.
10. If you cannot produce a supported object, leave the relevant list empty and explain uncertainty in `public_reasoning_summary`.

Minimal valid JSON skeletons for the required files:

{skeleton_text}

After writing outputs, stop. Do not run validation yourself unless the user explicitly asks.

Recommended model label for attestation: `{model}`.
"""


def render_output_contract(required_files: list[str], schema_path: Path, skeletons: dict[str, Any]) -> str:
    files = "\n".join(f"- `{filename}`" for filename in required_files) or "- none"
    skeleton_text = "\n\n".join(_format_inline_skeleton(filename, skeletons[filename]) for filename in required_files)
    return f"""# Output Contract

Schema file: `{schema_path}`

## Required Files

{files}

Every JSON file must parse, include the required top-level key, and cite only known IDs/locators. Unsupported claims,
fake citations, unknown paper IDs, and strong novelty claims without closest prior work will be rejected.

## Minimal Valid Skeletons

{skeleton_text}
"""


def render_readme_first(
    *,
    task_id: str,
    pack_dir: Path,
    outputs_dir: Path,
    model: str,
    validate_command: str,
    import_command: str,
    attestation_command: str,
    review_command: str,
) -> str:
    if validate_command == import_command:
        validation_import_lines = f"2. Validate and import must pass: `{validate_command}`."
        next_index = 3
    else:
        validation_import_lines = f"2. Validation must pass: `{validate_command}`.\n3. Import must run: `{import_command}`."
        next_index = 4
    review_line = f"\n{next_index + 1}. Human review: `{review_command}`" if review_command else ""
    return f"""# README First

This directory is a GapForge Codex/GPT-5.4 task handoff for `{task_id}`.

1. Paste `CODEX_PROMPT.md` into Codex/GPT-5.4.
2. Confirm Codex writes outputs into `{outputs_dir}`.
3. Run:

```bash
cd {shlex.quote(str(pack_dir))}
./VALIDATE_AND_IMPORT.sh
```

What still must happen before actual-run acceptance:

1. Codex/GPT-5.4 must produce the outputs.
{validation_import_lines}
{next_index}. Attestation must be recorded: `{attestation_command}`.{review_line}

Fake-agent success never counts as actual Codex/GPT-5.4 acceptance. Recommended model label: `{model}`.
"""


def render_validate_and_import_script(
    *,
    validate_command: str,
    import_command: str,
    attestation_command: str,
    review_command: str = "",
    doctor_command: str,
    repo_dir: Path,
) -> str:
    review_echo = f'echo "  {review_command}"\n' if review_command else ""
    if validate_command == import_command:
        validation_block = f"""if {validate_command}; then
  echo "Validation/import completed."
else
  echo "Validation/import failed. Run doctor/repair before importing:" >&2
  echo "  {doctor_command}" >&2
  echo "  gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff" >&2
  exit 1
fi"""
    else:
        validation_block = f"""if {validate_command}; then
  echo "Validation passed. Importing outputs..."
  {import_command}
else
  echo "Validation failed. Run doctor/repair before importing:" >&2
  echo "  {doctor_command}" >&2
  echo "  gapforge repair-agent-output --task-id <task-id> --latest-invalid --handoff" >&2
  exit 1
fi"""
    return f"""#!/usr/bin/env bash
set -euo pipefail

TASK_PACK_DIR="$(cd "$(dirname "$0")" && pwd)"
cd {shlex.quote(str(repo_dir))}

echo "Validating Codex/GPT-5.4 outputs..."
{validation_block}

echo
echo "Next required commands for actual-run acceptance:"
echo "  {attestation_command}"
{review_echo}echo "  {doctor_command}"
"""


def _dedupe_commands(commands: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for command in commands:
        cleaned = command.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _minimal_skeletons(required_files: list[str], schema: dict[str, Any]) -> dict[str, Any]:
    skeletons: dict[str, Any] = {}
    for filename in required_files:
        if filename.endswith(".md"):
            skeletons[filename] = "# GapForge Manuscript Outline\n\nNo evidence-backed manuscript content generated yet.\n"
            continue
        top_key = _top_key_for_file(filename, schema)
        skeletons[filename] = {
            top_key: [],
            "public_reasoning_summary": "No supported additions. Evidence was insufficient or the task produced no changes.",
        }
    return skeletons


def _example_outputs(required_files: list[str], skeletons: dict[str, Any]) -> dict[str, Any]:
    examples = dict(skeletons)
    for filename in required_files:
        if filename == "novelty_dossiers_patch.json":
            examples[filename] = {
                "novelty_dossiers": [
                    {
                        "target_id": "known-gap-or-direction-id",
                        "idea_summary": "Concise idea summary.",
                        "top_prior_work": ["known-paper-id"],
                        "verdict": "unknown",
                        "novelty_strength": "unknown",
                        "confidence": "low",
                        "missing_searches": ["specific search still needed"],
                    }
                ],
                "public_reasoning_summary": "Novelty remains unknown until closest prior work coverage improves.",
            }
        elif filename == "claims_patch.json":
            examples[filename] = {
                "claims": [],
                "public_reasoning_summary": "No claims were added because unsupported claims must not be imported.",
            }
    return examples


def _top_key_for_file(filename: str, schema: dict[str, Any]) -> str:
    file_schema = schema.get("files", {}).get(filename, {})
    required = file_schema.get("required", [])
    if isinstance(required, list) and required:
        return str(required[0])
    stem = filename.removesuffix(".json")
    if stem.endswith("_patch"):
        return stem[: -len("_patch")]
    return stem


def _write_example_file(path: Path, value: Any) -> None:
    if path.suffix == ".json":
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")


def _format_inline_skeleton(filename: str, value: Any) -> str:
    if filename.endswith(".json"):
        body = json.dumps(value, indent=2)
        return f"`{filename}`\n\n```json\n{body}\n```"
    return f"`{filename}`\n\n```markdown\n{value}\n```"


def _copy_relevant_examples(examples_dir: Path, required_files: list[str]) -> None:
    source_root = Path(__file__).resolve().parents[3] / "examples" / "codex_outputs"
    if not source_root.exists():
        return
    required = set(required_files)
    for example_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        output_dir = example_dir / "outputs"
        if not output_dir.exists():
            continue
        example_files = {path.name for path in output_dir.iterdir() if path.is_file()}
        if not (example_files & required):
            continue
        destination = examples_dir / example_dir.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(example_dir, destination)


def open_handoff_readme(path: Path) -> None:
    """Best-effort local open helper for interactive users."""

    if os.name == "posix":
        os.system(f"open {shlex.quote(str(path))} >/dev/null 2>&1 || true")
