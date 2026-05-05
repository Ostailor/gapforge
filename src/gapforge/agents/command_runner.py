"""Direct command execution for opt-in Codex/GPT-5.4 runners."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from gapforge.redaction import redact_text


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
) -> CommandRunResult:
    """Run an explicitly configured command template with redacted captured output."""

    rendered_command = command_template.format(
        task_pack=str(task_pack),
        outputs_dir=str(outputs_dir),
        task_id=task_id,
        run_id=run_id,
        model=model,
    )
    run_cwd = cwd or task_pack
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
