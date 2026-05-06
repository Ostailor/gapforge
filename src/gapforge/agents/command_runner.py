"""Direct command execution for opt-in Codex/GPT-5.4 runners."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from gapforge.models import CommandTemplateValidation
from gapforge.redaction import redact_text

RECOMMENDED_PLACEHOLDERS = ("task_pack", "outputs_dir", "model", "task_id", "run_id")
KNOWN_PLACEHOLDERS = set(RECOMMENDED_PLACEHOLDERS)
SHELL_RISK_PATTERNS = ("`", "$(", " > ", ">>", " 2>", " | ", " && ", " || ")


@dataclass(frozen=True, slots=True)
class CommandRunResult:
    command: str
    cwd: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_seconds: float = 0.0
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error


def validate_codex_command_template(
    template: str,
    *,
    task_pack: Path | str = "<task-pack>",
    outputs_dir: Path | str = "<outputs-dir>",
    task_id: str = "<task-id>",
    run_id: str = "<run-id>",
    model: str = "gpt-5.4",
    allow_unknown_placeholders: bool = False,
) -> CommandTemplateValidation:
    fields = _template_fields(template)
    unknown = sorted(field for field in fields if field not in KNOWN_PLACEHOLDERS)
    missing = [f"{{{name}}}" for name in RECOMMENDED_PLACEHOLDERS if name not in fields]
    warnings = _shell_risk_warnings(template)
    notes: list[str] = []
    if not template.strip():
        notes.append("No command template is configured.")
    if "{outputs_dir}" not in template:
        notes.append("Template should include {outputs_dir}; otherwise Codex may not write files where GapForge validates.")
    if "{task_pack}" not in template:
        notes.append("Template should include {task_pack}; otherwise Codex may not receive the task pack.")
    if unknown:
        notes.append("Unknown placeholders are not rendered by GapForge and should usually be removed.")
    rendered_preview = render_codex_command_template(
        template,
        task_pack=Path(task_pack),
        outputs_dir=Path(outputs_dir),
        task_id=task_id,
        run_id=run_id,
        model=model,
        allow_unknown_placeholders=True,
    )
    return CommandTemplateValidation(
        valid=bool(template.strip()) and (allow_unknown_placeholders or not unknown),
        missing_recommended_placeholders=missing,
        unknown_placeholders=[f"{{{name}}}" for name in unknown],
        shell_risk_warnings=warnings,
        rendered_preview=redact_text(rendered_preview),
        notes=notes,
    )


def render_codex_command_template(
    command_template: str,
    *,
    task_pack: Path,
    outputs_dir: Path,
    task_id: str,
    run_id: str,
    model: str,
    allow_unknown_placeholders: bool = False,
) -> str:
    values = {
        "task_pack": str(task_pack),
        "outputs_dir": str(outputs_dir),
        "task_id": task_id,
        "run_id": run_id,
        "model": model,
    }
    unknown = [field for field in _template_fields(command_template) if field not in KNOWN_PLACEHOLDERS]
    if unknown and not allow_unknown_placeholders:
        placeholders = ", ".join(f"{{{field}}}" for field in sorted(unknown))
        raise ValueError(f"Unknown placeholders in GAPFORGE_CODEX_COMMAND: {placeholders}")
    return command_template.format_map(_PreservingFormatMap(values))


def run_command_template(
    command_template: str,
    *,
    task_pack: Path,
    outputs_dir: Path,
    task_id: str,
    run_id: str,
    model: str,
    cwd: Path | None,
    timeout_seconds: int,
    allow_unknown_placeholders: bool = False,
) -> CommandRunResult:
    """Run an explicitly configured command template with redacted captured output."""

    try:
        rendered_command = render_codex_command_template(
            command_template,
            task_pack=task_pack,
            outputs_dir=outputs_dir,
            task_id=task_id,
            run_id=run_id,
            model=model,
            allow_unknown_placeholders=allow_unknown_placeholders,
        )
    except ValueError as exc:
        return CommandRunResult(
            command=redact_text(command_template),
            cwd=str(cwd or task_pack),
            returncode=-1,
            error=redact_text(str(exc)),
        )
    run_cwd = cwd or task_pack
    outputs_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        result = subprocess.run(
            rendered_command,
            cwd=run_cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.monotonic() - started
        return CommandRunResult(
            command=redact_text(rendered_command),
            cwd=str(run_cwd),
            returncode=result.returncode,
            stdout=redact_text(result.stdout),
            stderr=redact_text(result.stderr),
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - started
        stdout = _coerce_output(exc.stdout)
        stderr = _coerce_output(exc.stderr)
        return CommandRunResult(
            command=redact_text(rendered_command),
            cwd=str(run_cwd),
            returncode=-1,
            stdout=redact_text(stdout),
            stderr=redact_text(stderr),
            timed_out=True,
            duration_seconds=duration,
            error=f"Direct Codex command timed out after {timeout_seconds} seconds.",
        )
    except OSError as exc:
        duration = time.monotonic() - started
        return CommandRunResult(
            command=redact_text(rendered_command),
            cwd=str(run_cwd),
            returncode=-1,
            duration_seconds=duration,
            error=redact_text(str(exc)),
        )


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if not field_name:
            continue
        fields.add(field_name.split(".", 1)[0].split("[", 1)[0])
    return fields


def _shell_risk_warnings(template: str) -> list[str]:
    warnings: list[str] = []
    for pattern in SHELL_RISK_PATTERNS:
        if pattern in template:
            warnings.append(f"Template contains shell metacharacter pattern `{pattern.strip()}`; verify quoting and secret handling.")
    return warnings


class _PreservingFormatMap(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"
