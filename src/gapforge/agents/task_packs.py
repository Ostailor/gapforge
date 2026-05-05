"""Codex-compatible research task-pack generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.agents.codex_prompts import render_rules, render_task_markdown
from gapforge.agents.records import output_dir_for_task, task_pack_dir
from gapforge.agents.schema_validator import expected_output_files, expected_output_schema
from gapforge.models import AgentTaskSpec, ResearchRunState, to_plain


def write_codex_task_pack(state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
    pack_dir = task_pack_dir(state, task_spec)
    pack_dir.mkdir(parents=True, exist_ok=True)
    output_dir_for_task(state, task_spec).mkdir(parents=True, exist_ok=True)
    schema = expected_output_schema(task_spec)
    artifact_links = _artifact_links(state, task_spec)
    input_manifest = _input_manifest(state, task_spec, artifact_links)

    (pack_dir / "TASK.md").write_text(render_task_markdown(state, task_spec, schema), encoding="utf-8")
    (pack_dir / "task_spec.json").write_text(json.dumps(to_plain(task_spec), indent=2) + "\n", encoding="utf-8")
    (pack_dir / "input_manifest.json").write_text(json.dumps(input_manifest, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "expected_output_schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    (pack_dir / "evidence_rules.md").write_text(render_rules("Evidence Rules", task_spec.evidence_rules), encoding="utf-8")
    (pack_dir / "uncertainty_rules.md").write_text(render_rules("Uncertainty Rules", task_spec.uncertainty_rules), encoding="utf-8")
    (pack_dir / "artifact_links.json").write_text(json.dumps(artifact_links, indent=2) + "\n", encoding="utf-8")
    validation_path = pack_dir / "validation.json"
    if not validation_path.exists():
        validation_path.write_text(
            json.dumps({"task_id": task_spec.id, "status": "not_validated", "issues": []}, indent=2) + "\n",
            encoding="utf-8",
        )
    return pack_dir


def _input_manifest(state: ResearchRunState, task_spec: AgentTaskSpec, artifact_links: dict[str, str]) -> dict[str, Any]:
    return {
        "task_id": task_spec.id,
        "run_id": state.run_id,
        "project_id": task_spec.project_id,
        "topic": state.topic.text,
        "skill_name": task_spec.skill_name,
        "task_type": task_spec.task_type,
        "required_output_files": expected_output_files(task_spec),
        "artifact_links": artifact_links,
        "counts": {
            "papers": len(state.papers),
            "paper_sections": len(state.paper_sections),
            "evidence_spans": len(state.evidence_spans),
            "claims": len(state.claims),
            "gaps": len(state.gaps),
            "novelty_dossiers": len(state.novelty_dossiers),
        },
        "known_paper_ids": [paper.id for paper in state.papers],
        "known_evidence_span_ids": [span.id for span in state.evidence_spans],
        "known_evidence_locators": [span.locator for span in state.evidence_spans if span.locator],
    }


def _artifact_links(state: ResearchRunState, task_spec: AgentTaskSpec) -> dict[str, str]:
    run_dir = Path(state.run_dir)
    paths = {Path(path).name: str(Path(path)) for path in task_spec.input_artifacts}
    for name in [
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
        "run_report.md",
        "final_report.md",
    ]:
        path = run_dir / name
        if path.exists():
            paths[name] = str(path)
    return paths
