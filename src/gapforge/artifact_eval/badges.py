"""Conservative artifact badge assessment."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.artifact_eval.checklist import ArtifactEvaluationChecklistManager
from gapforge.artifact_eval.package import artifact_evaluation_package_dir, load_artifact_evaluation_package
from gapforge.config import GapForgeConfig
from gapforge.models import BadgeAssessment, Provenance, ReplicationManifest, from_dict, to_plain
from gapforge.state import utc_now_iso

BADGE_TYPES = {"available", "functional", "reusable", "reproducible", "custom"}


class ArtifactBadgeAssessor:
    """Assess artifact badges only from package evidence."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def assess(self, package_id: str) -> list[BadgeAssessment]:
        package = load_artifact_evaluation_package(self.config, package_id)
        package_dir = artifact_evaluation_package_dir(self.config, package_id)
        checklist = ArtifactEvaluationChecklistManager(self.config).check(package_id)
        manifest = _load_manifest(package_dir / "replication_package" / "replication_manifest.json")
        assessments = [
            _available(package_id, package, checklist),
            _functional(package_id, package, checklist, manifest),
            _reusable(package_id, package, checklist, manifest),
            _reproducible(package_id, package, checklist, manifest, package_dir),
        ]
        (package_dir / "badge_assessments.json").write_text(json.dumps(to_plain(assessments), indent=2) + "\n", encoding="utf-8")
        (package_dir / "badge_assessments.md").write_text(render_badge_assessments_markdown(assessments), encoding="utf-8")
        return assessments

    def render_markdown(self, assessments: list[BadgeAssessment]) -> str:
        return render_badge_assessments_markdown(assessments)


def render_badge_assessments_markdown(assessments: list[BadgeAssessment]) -> str:
    lines = ["# Artifact Badge Assessments", ""]
    for assessment in assessments:
        lines.extend(
            [
                f"## {assessment.badge_type.title()}",
                "",
                f"- Eligible: {str(assessment.eligible).lower()}",
                "",
                "Evidence:",
                *([f"- {item}" for item in assessment.evidence] or ["- none"]),
                "",
                "Blockers:",
                *([f"- {item}" for item in assessment.blockers] or ["- none"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _available(package_id: str, package, checklist) -> BadgeAssessment:
    blockers = []
    evidence = []
    if package.files:
        evidence.append(f"Package lists {len(package.files)} files.")
    else:
        blockers.append("No artifact package files are listed.")
    if not package.replication_package_id:
        blockers.append("No replication package is included.")
    if checklist.blockers:
        evidence.append("Checklist was run.")
    return _assessment(package_id, "available", not blockers, evidence, blockers)


def _functional(
    package_id: str,
    package,
    checklist,
    manifest: ReplicationManifest | None,
) -> BadgeAssessment:
    evidence: list[str] = []
    blockers: list[str] = []
    if manifest and manifest.commands:
        evidence.append(f"Replication manifest records {len(manifest.commands)} command(s).")
    else:
        blockers.append("No executable commands are recorded.")
    if checklist.blockers:
        blockers.append("Artifact evaluation checklist has blockers.")
    if package.install_instructions and package.run_instructions:
        evidence.append("Install and run instructions are present.")
    else:
        blockers.append("Install/run instructions are incomplete.")
    return _assessment(package_id, "functional", not blockers, evidence, blockers)


def _reusable(
    package_id: str,
    package,
    checklist,
    manifest: ReplicationManifest | None,
) -> BadgeAssessment:
    evidence: list[str] = []
    blockers: list[str] = []
    if package.replication_package_id:
        evidence.append(f"Replication package `{package.replication_package_id}` is included.")
    else:
        blockers.append("No replication package is included.")
    if manifest and manifest.dataset_download_instructions:
        evidence.append("Dataset download instructions are included for excluded/restricted data.")
    if checklist.warnings:
        blockers.append("Warnings require human review before reusable badge.")
    return _assessment(package_id, "reusable", not blockers and not checklist.blockers, evidence, blockers)


def _reproducible(
    package_id: str,
    package,
    checklist,
    manifest: ReplicationManifest | None,
    package_dir: Path,
) -> BadgeAssessment:
    evidence: list[str] = []
    blockers: list[str] = []
    if manifest and manifest.result_hashes:
        evidence.append(f"Expected result hashes are recorded for {len(manifest.result_hashes)} file(s).")
    else:
        blockers.append("No expected result hashes are recorded.")
    smoke_records = list((package_dir / "smoke").glob("*.json"))
    if smoke_records:
        evidence.append("Artifact evaluation smoke dry-run has been recorded.")
    else:
        blockers.append("No artifact evaluation smoke dry-run record exists.")
    if checklist.blockers:
        blockers.append("Artifact evaluation checklist has blockers.")
    return _assessment(package_id, "reproducible", not blockers, evidence, blockers)


def _assessment(
    package_id: str,
    badge_type: str,
    eligible: bool,
    evidence: list[str],
    blockers: list[str],
) -> BadgeAssessment:
    if badge_type not in BADGE_TYPES:
        raise ValueError(f"Unsupported badge type: {badge_type}")
    return BadgeAssessment(
        package_id=package_id,
        badge_type=badge_type,
        eligible=eligible,
        evidence=evidence,
        blockers=blockers,
        provenance=Provenance(
            created_by_skill="artifact-badge-assessment",
            source_ids=[package_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Assessed artifact badge eligibility from package/checklist evidence without inventing badge claims.",
        ),
    )


def _load_manifest(path: Path) -> ReplicationManifest | None:
    if not path.exists():
        return None
    return from_dict(ReplicationManifest, json.loads(path.read_text(encoding="utf-8")))
