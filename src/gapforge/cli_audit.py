"""CLI usability audit for v0.9 and v1 readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import CLICommandAudit, Provenance, to_plain
from gapforge.state import utc_now_iso

REQUIRED_GROUPS = [
    "project",
    "campaign",
    "literature",
    "codex",
    "experiment",
    "benchmark",
    "manuscript",
    "release-gate",
    "safety",
]

DEPRECATED_COMMANDS = {
    "list-projects": "Prefer `project-list` for project command grouping.",
    "use-project": "Prefer `project-use` for project command grouping.",
    "v1-gate": "Prefer `v1-readiness`; `v1-gate` is a compatibility alias.",
}

RECOMMENDED_ALIASES = {
    "project-list": "Alias for `list-projects`.",
    "project-use": "Alias for `use-project`.",
    "v1-gate": "Compatibility alias for `v1-readiness`.",
}


class CLICommandAuditor:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def audit(self, parser: argparse.ArgumentParser, *, write: bool = False) -> CLICommandAudit:
        commands = _command_help(parser)
        canonical_commands = sorted(commands)
        groups: dict[str, list[str]] = {group: [] for group in REQUIRED_GROUPS}
        groups["other"] = []
        for command in canonical_commands:
            groups[_group_for_command(command)].append(command)
        missing_help = [command for command, help_text in commands.items() if not help_text or help_text == argparse.SUPPRESS]
        duplicate_or_confusing = _confusing_commands(canonical_commands)
        audit = CLICommandAudit(
            command_count=len(canonical_commands),
            command_groups={group: items for group, items in groups.items() if items},
            duplicate_or_confusing_commands=duplicate_or_confusing,
            missing_help=missing_help,
            deprecated_commands=[f"{command}: {reason}" for command, reason in DEPRECATED_COMMANDS.items() if command in commands],
            recommended_aliases=[f"{alias}: {reason}" for alias, reason in RECOMMENDED_ALIASES.items()],
            provenance=Provenance(
                created_by_skill="cli-audit",
                source_ids=["gapforge.cli.build_parser"],
                timestamp=utc_now_iso(),
                reasoning_summary="Inspected argparse command help, command grouping, aliases, and deprecated compatibility names.",
            ),
        )
        if write:
            self.write_outputs(audit)
        return audit

    def write_outputs(self, audit: CLICommandAudit) -> tuple[Path, Path]:
        audit_dir = self.config.data_dir / "cli_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        json_path = audit_dir / "cli_audit_latest.json"
        md_path = audit_dir / "cli_audit_latest.md"
        report = render_cli_command_audit(audit)
        json_path.write_text(json.dumps(to_plain(audit), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(report, encoding="utf-8")
        release_dir = self.config.data_dir / "release_gate"
        release_dir.mkdir(parents=True, exist_ok=True)
        required_groups_present = all(group in audit.command_groups and audit.command_groups[group] for group in REQUIRED_GROUPS)
        passed = not audit.missing_help and required_groups_present
        release_payload = {
            "passed": passed,
            "status": "pass" if passed else "fail",
            "command_count": audit.command_count,
            "missing_help": audit.missing_help,
            "required_groups_present": required_groups_present,
            "report_path": str(md_path),
        }
        (release_dir / "cli_audit.json").write_text(json.dumps(release_payload, indent=2) + "\n", encoding="utf-8")
        return json_path, md_path


def render_cli_command_audit(audit: CLICommandAudit) -> str:
    lines = [
        "# GapForge CLI Usability Audit",
        "",
        f"- Commands: {audit.command_count}",
        f"- Missing help entries: {len(audit.missing_help)}",
        f"- Deprecated compatibility commands: {len(audit.deprecated_commands)}",
        "",
        "## Command Groups",
        "",
    ]
    for group, commands in audit.command_groups.items():
        lines.extend([f"### {group}", ""])
        lines.extend(f"- `{command}`" for command in commands)
        lines.append("")
    lines.extend(["## Duplicate Or Confusing Commands", ""])
    lines.extend([f"- {item}" for item in audit.duplicate_or_confusing_commands] or ["- none"])
    lines.extend(["", "## Missing Help", ""])
    lines.extend([f"- `{item}`" for item in audit.missing_help] or ["- none"])
    lines.extend(["", "## Deprecated Commands", ""])
    lines.extend([f"- {item}" for item in audit.deprecated_commands] or ["- none"])
    lines.extend(["", "## Recommended Aliases", ""])
    lines.extend([f"- {item}" for item in audit.recommended_aliases] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _command_help(parser: argparse.ArgumentParser) -> dict[str, str]:
    commands: dict[str, str] = {}
    for action in parser._actions:  # argparse exposes no public subparser iterator.
        if isinstance(action, argparse._SubParsersAction):
            for choice in action._choices_actions:
                commands[choice.dest] = str(choice.help or "")
    return commands


def _group_for_command(command: str) -> str:
    if command in {"init-project", "project-list", "list-projects", "use-project", "project-use", "project-status", "project-report"}:
        return "project"
    if command.startswith("campaign") or command in {"run-active", "active-status", "active-decisions"}:
        return "campaign"
    if command.startswith(("real-literature", "source-", "live-source", "search", "plan-search", "execute-search")):
        return "literature"
    if command in {
        "map",
        "triage",
        "rank-papers",
        "read",
        "read-llm",
        "mine-gaps",
        "mine-gaps-llm",
        "analogies",
        "novelty-check",
        "novelty-check-llm",
        "novelty-dossier",
        "download-pdfs",
        "parse-fulltext",
        "parse-structure",
        "parse-references",
        "parse-tables",
        "ocr-status",
        "add-paper",
        "add-arxiv",
        "add-doi",
        "add-pdf",
        "add-url",
        "coverage",
        "assess-coverage",
        "next-searches",
        "canonicalize-papers",
        "paper-merge-report",
        "build-citation-graph",
        "expand-related-work",
        "prior-work-recall",
        "prior-work-recall-report",
    }:
        return "literature"
    if command.startswith(("agent", "codex", "repair", "attest")) or command in {
        "prompt-pack",
        "setup-real-run",
        "setup-codex",
        "task-handoff",
        "validate-agent-output",
        "import-agent-output",
        "list-agent-tasks",
        "list-task-outputs",
        "latest-codex-task",
        "actual-run-status",
        "attestation-status",
        "diagnose-agent",
        "diagnose-real-run",
    }:
        return "codex"
    if command.startswith(("experiment", "job", "sweep", "ablation", "seed", "result", "results", "parse-results")):
        return "experiment"
    if command in {
        "design-experiments",
        "design-experiment",
        "compute-status",
        "compute-check",
        "analyze-results",
        "low-fpr-power-check",
        "low-fpr-plan",
        "low-fpr-check",
        "reproducibility-check",
        "empirical-review",
        "dataset-register",
        "dataset-card",
        "dataset-validate",
        "dataset-list",
        "dataset-download-plan",
        "dataset-download",
        "dataset-cache-info",
        "dataset-cache-clean",
        "dataset-consent",
        "baseline-register",
        "baseline-from-related-work",
        "baseline-list",
        "baseline-card",
        "metric-register",
        "metric-list",
        "generate-code-tasks",
        "scaffold-experiment-repo",
        "scaffold-experiment-code",
        "stats-plan",
    }:
        return "experiment"
    if command.startswith(("benchmark", "leaderboard")) or command in {
        "export-replication",
        "verify-replication",
        "replication-status",
        "reproduce",
        "reproduce-status",
        "reproducibility-matrix",
        "results-aggregate",
    }:
        return "benchmark"
    if command.startswith(("manuscript", "submission", "artifact-eval", "artifact-badge", "anonym", "deanonym")):
        return "manuscript"
    if command in {
        "bibliography-build",
        "bibliography-export",
        "citation-check",
        "citation-list",
        "venue-list",
        "revision-plan",
        "revision-status",
        "mark-rebuttal-item",
        "export-manuscript",
        "export-bib",
        "export-paper-package",
        "export-paper-package-v2",
        "review-panel",
        "reviewer-loop",
        "rebuttal-plan",
        "rebuttal-tasks",
        "meta-review",
    }:
        return "manuscript"
    if command.startswith(("v4-", "v5-", "v6-", "v7-", "v8-", "v9-", "v1-", "pilot-", "idea-gate", "selected-idea")):
        return "release-gate"
    if command in {
        "compatibility-audit",
        "migrate-project",
        "migrate-run",
        "migrate-all",
        "migration-blockers",
        "migration-fixtures-list",
        "migration-report",
        "cli-audit",
        "docs-audit",
        "eval",
        "release-gate-dashboard",
    }:
        return "release-gate"
    if command.startswith(("audit", "clean", "export-safe")) or command in {
        "validate-state",
        "rollback-import",
        "review-queue",
        "complete-review-item",
        "dismiss-review-item",
        "lock-object",
        "cache-info",
        "show-state",
        "llm-status",
        "llm-test",
        "llm-usage",
        "llm-transcripts",
    }:
        return "safety"
    return "other"


def _confusing_commands(commands: list[str]) -> list[str]:
    issues: list[str] = []
    if "run" in commands and "run-active" in commands:
        issues.append("`run` and `run-active` are distinct; help should keep the default full workflow obvious.")
    if "review" in commands and "review-panel" in commands:
        issues.append("`review` is run-level reviewer simulation; `review-panel` is project-direction review.")
    return issues
