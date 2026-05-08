"""Durable pilot run status and acceptance classification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import ExternalPilotReview, PilotAcceptanceSummary, PilotRunRecord, PilotSpec, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

PILOT_PROJECT_ALIASES = {
    "low_fpr_collusion",
    "low-fpr-collusion",
    "low-fpr-collusion-pilot",
    "v0-9-low-fpr-collusion-pilot",
}

REQUIRED_ARTIFACT_LOCATIONS = {
    "project_record": {"project": "project.json"},
    "campaign_record": {"project": "campaigns.json"},
    "live_source_diagnostics": {"data": "source_health/live_source_diagnostic_latest.md"},
    "search_strategy": {"run": "search_strategies.json"},
    "search_rounds": {"run": "search_rounds.md"},
    "source_coverage_report": {"run": "source_coverage.md"},
    "paper_canonicalization_report": {"run": "paper_merge_report.md"},
    "prior_work_recall_assessment": {"run": "prior_work_recall.md"},
    "codex_synthesis_task_outputs": {"project": "campaigns"},
    "novelty_dossiers": {"run": "novelty_dossiers.md"},
    "related_work_matrix": {"project": "related_work_matrix.md"},
    "research_direction_or_refusal": {"project": "research_directions.json"},
    "experiment_protocol": {"project": "experiment_protocols.md"},
    "benchmark_or_fixture_experiment_plan": {"project": "benchmark_suites.md"},
    "empirical_artifact_status": {"project": "experiment_workspaces.md"},
    "manuscript_draft_or_refusal_report": {"project": "manuscripts"},
    "reviewer_panel": {"project": "review_panel.md"},
    "rebuttal_revision_plan": {"project": "rebuttal_plan.md"},
    "final_pilot_report": {"project": "reports/final_pilot_report.md"},
}


class PilotStore:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.root = config.data_dir / "pilots"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_record(self, record: PilotRunRecord) -> Path:
        record.updated_at = utc_now_iso()
        record_dir = self.record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        path = record_dir / "pilot_run_record.json"
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        latest = self.root / record.pilot_id / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(json.dumps({"pilot_run_id": record.id}, indent=2) + "\n", encoding="utf-8")
        return path

    def load_record(self, pilot_id: str) -> PilotRunRecord:
        path = self.record_dir(pilot_id) / "pilot_run_record.json"
        if not path.exists():
            latest = self._latest_pointer(pilot_id)
            if latest:
                path = self.record_dir(latest) / "pilot_run_record.json"
        if not path.exists():
            raise FileNotFoundError(f"No pilot run record found for {pilot_id}")
        return from_dict(PilotRunRecord, json.loads(path.read_text(encoding="utf-8")))

    def save_acceptance(self, record: PilotRunRecord, summary: PilotAcceptanceSummary) -> Path:
        path = self.record_dir(record.id) / "pilot_acceptance_summary.json"
        path.write_text(json.dumps(to_plain(summary), indent=2) + "\n", encoding="utf-8")
        return path

    def load_acceptance(self, pilot_id: str) -> PilotAcceptanceSummary:
        record = self.load_record(pilot_id)
        path = self.record_dir(record.id) / "pilot_acceptance_summary.json"
        reviews = self.load_external_reviews(record.id)
        if not path.exists() or reviews:
            summary = build_acceptance_summary(record, reviews=reviews)
            self.save_acceptance(record, summary)
            return summary
        return from_dict(PilotAcceptanceSummary, json.loads(path.read_text(encoding="utf-8")))

    def save_external_review(self, record: PilotRunRecord, review: ExternalPilotReview) -> Path:
        reviews_dir = self.record_dir(record.id) / "external_reviews"
        reviews_dir.mkdir(parents=True, exist_ok=True)
        path = reviews_dir / f"{review.id}.json"
        path.write_text(json.dumps(to_plain(review), indent=2) + "\n", encoding="utf-8")
        return path

    def load_external_reviews(self, pilot_id: str) -> list[ExternalPilotReview]:
        record = self.load_record(pilot_id)
        reviews_dir = self.record_dir(record.id) / "external_reviews"
        if not reviews_dir.exists():
            return []
        reviews = []
        for path in sorted(reviews_dir.glob("*.json")):
            reviews.append(from_dict(ExternalPilotReview, json.loads(path.read_text(encoding="utf-8"))))
        return reviews

    def record_dir(self, pilot_run_id: str) -> Path:
        return self.root / pilot_run_id

    def _latest_pointer(self, pilot_id: str) -> str:
        path = self.root / pilot_id / "latest.json"
        if not path.exists():
            return ""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("pilot_run_id", ""))


def build_status_payload(config: GapForgeConfig, spec: PilotSpec, pilot_id: str = "") -> dict[str, Any]:
    store = PilotStore(config)
    try:
        record = store.load_record(pilot_id or spec.id)
    except FileNotFoundError:
        return _missing_project_status(config, spec)
    summary = store.load_acceptance(record.id)
    return {
        "name": spec.name,
        "topic": spec.topic,
        "status": record.status,
        "pilot_run_id": record.id,
        "project_id": record.project_id,
        "campaign_id": record.campaign_id,
        "workspace_id": record.workspace_id,
        "manuscript_id": record.manuscript_id,
        "outcome_type": record.outcome_type,
        "artifact_paths": record.artifact_paths,
        "blockers": record.blockers,
        "acceptance": to_plain(summary),
    }


def render_pilot_status_json(config: GapForgeConfig, spec: PilotSpec, pilot_id: str = "") -> str:
    return json.dumps(build_status_payload(config, spec, pilot_id=pilot_id), indent=2) + "\n"


def refresh_artifact_paths(config: GapForgeConfig, spec: PilotSpec, record: PilotRunRecord) -> PilotRunRecord:
    if not record.project_id:
        return record
    try:
        program = ProjectMemoryManager(config).load_project(record.project_id)
    except FileNotFoundError:
        record.blockers.append(f"product_failure: project {record.project_id} cannot be loaded")
        record.status = "product_failure"
        record.outcome_type = "product_failure"
        return record
    project_root = Path(program.project.root_dir)
    run_roots = _run_roots(config, program.run_ids)
    for artifact in spec.required_artifacts:
        path = _artifact_path(project_root, run_roots, config, artifact)
        if path:
            record.artifact_paths[artifact] = path
    return record


def classify_record(record: PilotRunRecord, spec: PilotSpec) -> PilotRunRecord:
    product_failures = _product_failures(record)
    if product_failures:
        record.status = "product_failure"
        record.outcome_type = "product_failure"
        return record

    missing = [artifact for artifact in spec.required_artifacts if artifact not in record.artifact_paths]
    if "human_review_acceptance" in record.artifact_paths and _has_direction_evidence(record):
        record.status = "direction_ready"
        record.outcome_type = "defensible_direction"
        return record
    if missing or record.blockers:
        record.status = "refusal_ready"
        record.outcome_type = "correct_refusal"
        for artifact in missing:
            blocker = f"research_refusal: missing required artifact {artifact}"
            if blocker not in record.blockers:
                record.blockers.append(blocker)
        return record
    record.status = "running"
    record.outcome_type = "unknown"
    return record


def build_acceptance_summary(record: PilotRunRecord, reviews: list[ExternalPilotReview] | None = None) -> PilotAcceptanceSummary:
    product_failures = _product_failures(record)
    accepted_direction_id = record.artifact_paths.get("accepted_direction_id", "")
    refusal_reason = _refusal_reason(record)
    review_records = reviews or []
    accepted_reviews = [review for review in review_records if review.accepted_outcome]
    rejected_reviews = [review for review in review_records if not review.accepted_outcome]
    if accepted_reviews:
        human_review_status = "accepted"
    elif rejected_reviews:
        human_review_status = "rejected"
    else:
        human_review_status = "missing"
    passed = (
        record.status == "accepted"
        and record.outcome_type in {"defensible_direction", "correct_refusal"}
        and not product_failures
        and bool(accepted_reviews)
        and not _fake_citation_or_result_issue(record, accepted_reviews)
    )
    return PilotAcceptanceSummary(
        pilot_id=record.id,
        passed=passed,
        outcome_type=record.outcome_type,
        accepted_direction_id=accepted_direction_id,
        refusal_reason=refusal_reason,
        product_failures=product_failures,
        human_review_status=human_review_status,
        release_gate_eligible=passed,
        provenance=Provenance(
            created_by_skill="pilot-acceptance",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Classified pilot acceptance without converting missing evidence into success.",
        ),
    )


def find_pilot_project(config: GapForgeConfig, spec: PilotSpec):
    topic_lower = spec.topic.lower()
    for project in ProjectMemoryManager(config).list_projects():
        project_id = project.id.lower()
        name = project.name.lower()
        description = project.description.lower()
        if project_id in PILOT_PROJECT_ALIASES:
            return project
        if "low" in project_id and "fpr" in project_id and "collusion" in project_id:
            return project
        if topic_lower in name or topic_lower in description:
            return project
        if "low-fpr" in name and "collusion" in name:
            return project
    return None


def _missing_project_status(config: GapForgeConfig, spec: PilotSpec) -> dict[str, Any]:
    project = find_pilot_project(config, spec)
    docs_dir = config.root / "docs" / "pilots" / spec.id
    if not docs_dir.exists():
        docs_dir = Path(__file__).resolve().parents[3] / "docs" / "pilots" / spec.id
    docs = {
        "spec": {"path": str(docs_dir / "PILOT_SPEC.md"), "exists": (docs_dir / "PILOT_SPEC.md").exists()},
        "acceptance": {
            "path": str(docs_dir / "ACCEPTANCE_CRITERIA.md"),
            "exists": (docs_dir / "ACCEPTANCE_CRITERIA.md").exists(),
        },
        "review": {"path": str(docs_dir / "REVIEW_CHECKLIST.md"), "exists": (docs_dir / "REVIEW_CHECKLIST.md").exists()},
    }
    if project is not None:
        return {
            "name": spec.name,
            "topic": spec.topic,
            "status": "missing_pilot_run_record",
            "project": {"id": project.id, "name": project.name, "root_dir": project.root_dir},
            "docs": docs,
            "outcome": "not_started",
        }
    return {
        "name": spec.name,
        "topic": spec.topic,
        "status": "missing_project",
        "project": None,
        "docs": docs,
        "required_outputs": {
            artifact: {"status": "missing", "path": "", "reason": "Pilot project has not been created."}
            for artifact in spec.required_artifacts
        },
        "outcome": "not_started",
        "next_commands": [
            "gapforge pilot-run --name low_fpr_collusion",
            "gapforge pilot-spec --name low_fpr_collusion",
        ],
    }


def _run_roots(config: GapForgeConfig, run_ids: list[str]) -> list[Path]:
    manager = ResearchStateManager(config)
    roots: list[Path] = []
    for run_id in run_ids:
        try:
            roots.append(Path(manager.load_run(run_id).run_dir))
        except FileNotFoundError:
            continue
    return roots


def _artifact_path(project_root: Path, run_roots: list[Path], config: GapForgeConfig, artifact: str) -> str:
    requirement = REQUIRED_ARTIFACT_LOCATIONS.get(artifact)
    if requirement is None:
        return ""
    if "project" in requirement:
        path = project_root / requirement["project"]
        return str(path) if path.exists() else ""
    if "data" in requirement:
        path = config.data_dir / requirement["data"]
        return str(path) if path.exists() else ""
    if "run" in requirement:
        for run_root in run_roots:
            path = run_root / requirement["run"]
            if path.exists():
                return str(path)
    return ""


def _has_direction_evidence(record: PilotRunRecord) -> bool:
    required = {
        "evidence_backed_gap",
        "closest_prior_work",
        "prior_work_recall_assessment",
        "experiment_protocol",
        "reviewer_panel",
    }
    return required.issubset(record.artifact_paths)


def _product_failures(record: PilotRunRecord) -> list[str]:
    failures = [blocker.removeprefix("product_failure:").strip() for blocker in record.blockers if blocker.startswith("product_failure:")]
    return failures or (record.blockers if record.outcome_type == "product_failure" or record.status == "product_failure" else [])


def _fake_citation_or_result_issue(record: PilotRunRecord, reviews: list[ExternalPilotReview]) -> bool:
    text = " ".join(record.blockers).lower()
    text += " " + " ".join(" ".join(review.major_concerns + review.required_fixes) for review in reviews).lower()
    return "fake citation" in text or "fake result" in text


def _refusal_reason(record: PilotRunRecord) -> str:
    if record.outcome_type != "correct_refusal":
        return ""
    reasons = [blocker.removeprefix("research_refusal:").strip() for blocker in record.blockers if blocker.startswith("research_refusal:")]
    return "; ".join(reasons or record.blockers)
