"""Offline v0.9 pilot, review, v1-readiness, and release-gate smoke test."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import IdeaGateAssessment, PilotRunRecord, Provenance, to_plain
from gapforge.pilots import ExternalPilotReviewManager, PilotStore
from gapforge.release_gate.v09 import V09ReleaseGateEnforcer
from gapforge.release_gate.v1 import V1ReadinessGate
from gapforge.state import utc_now_iso


def main() -> int:
    config = _smoke_config(Path.cwd())
    config.ensure_dirs()
    _write_release_prerequisites(config)
    record = _write_accepted_refusal_pilot(config)
    _write_audits(config)

    v1_gate = V1ReadinessGate(config)
    v1_result = v1_gate.evaluate()
    v1_json, v1_md = v1_gate.write_outputs(v1_result)
    if not v1_result.passed:
        raise RuntimeError("v1 readiness did not pass for v0.9 smoke: " + "; ".join(v1_result.blockers))

    v9_gate = V09ReleaseGateEnforcer(config)
    v9_result = v9_gate.evaluate()
    v9_json, v9_md = v9_gate.write_outputs(v9_result)
    if not v9_result.passed:
        raise RuntimeError("v0.9 release gate did not pass for smoke fixture: " + "; ".join(v9_result.blockers))

    print("v0.9 smoke completed")
    print(f"pilot: {record.id}")
    print(f"outcome: {record.outcome_type}")
    print(f"v1 readiness: {v1_result.status} next={v1_result.recommended_next_version}")
    print(f"v1 readiness report: {v1_json} {v1_md}")
    print(f"v9 release gate: {v9_result.status} next={v9_result.recommended_next_version}")
    print(f"v9 release gate report: {v9_json} {v9_md}")
    return 0


def _smoke_config(root: Path) -> GapForgeConfig:
    smoke_root = root / "data" / "v9_smoke"
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    return GapForgeConfig(
        root=smoke_root,
        runs_dir=smoke_root / "runs",
        project_root=smoke_root / "projects",
        data_dir=smoke_root / "data",
        skills_dir=smoke_root / "skills",
        cache_dir=smoke_root / ".gapforge_cache",
    )


def _write_release_prerequisites(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text(json.dumps({"passed": True}) + "\n", encoding="utf-8")
    for version in ["v0.4", "v0.5", "v0.6", "v0.7", "v0.8"]:
        (release_dir / f"{version}_latest.json").write_text(
            json.dumps({"passed": True, "status": "pass", "scope": "v9-smoke-prerequisite"}) + "\n",
            encoding="utf-8",
        )


def _write_accepted_refusal_pilot(config: GapForgeConfig) -> PilotRunRecord:
    record = PilotRunRecord(
        id=f"pilot-v09-smoke-{utc_now_iso().replace(':', '').replace('.', '')}",
        pilot_id="low_fpr_collusion",
        project_id="v9-smoke-project",
        status="refusal_ready",
        outcome_type="correct_refusal",
        artifact_paths={
            "explicit_missing_searches_or_experiments": "reports/refusal.md",
            "final_pilot_report": "reports/final_pilot_report.md",
        },
        blockers=["research_refusal: fixture smoke preserves an accepted refusal without inventing a direction"],
        created_at=utc_now_iso(),
    )
    store = PilotStore(config)
    store.save_record(record)
    _write_idea_gate(config, record.id)
    ExternalPilotReviewManager(config).create_review(
        record.id,
        reviewer_name="v9 smoke reviewer",
        reviewer_role="user",
        review_scope=["source_coverage", "novelty", "experiment_tractability", "refusal"],
        accept_outcome=True,
        notes="Smoke reviewer accepts the refusal as the correct pilot outcome.",
    )
    accepted_record = store.load_record(record.id)
    project_report = config.project_root / "v9-smoke-project" / "reports" / "final_pilot_report.md"
    project_report.parent.mkdir(parents=True, exist_ok=True)
    project_report.write_text(
        "# v0.9 Smoke Final Pilot Report\n\nAccepted correct refusal fixture; no research direction is claimed.\n",
        encoding="utf-8",
    )
    return accepted_record


def _write_idea_gate(config: GapForgeConfig, pilot_id: str) -> None:
    assessment = IdeaGateAssessment(
        pilot_id=pilot_id,
        candidate_direction_ids=[],
        selected_direction_id="",
        rejected_direction_ids=[],
        selection_reason="No candidate direction was selected; smoke fixture records correct refusal.",
        acceptance_status="refusal",
        blockers=["No candidate direction passed the smoke idea gate."],
        provenance=Provenance(
            created_by_skill="idea-gate",
            source_ids=[pilot_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Smoke gate verifies refusal handling.",
        ),
    )
    path = config.data_dir / "pilots" / pilot_id / "idea_gate_assessment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")


def _write_audits(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    for name in ["migration_audit", "cli_audit", "docs_audit", "artifact_hygiene_audit"]:
        (release_dir / f"{name}.json").write_text(
            json.dumps({"passed": True, "status": "pass", "scope": "v9-smoke"}) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
