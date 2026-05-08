from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    ExperimentProtocol,
    ExternalPilotReview,
    IdeaGateAssessment,
    PilotRunRecord,
    ProjectMemoryRecord,
    Provenance,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchDirection,
    ReviewPanel,
)
from gapforge.pilots import ExternalPilotReviewManager, IdeaGate, PilotRunner, PilotStore, get_pilot_spec
from gapforge.pilots.outcome import assess_pilot_outcome
from gapforge.pilots.reports import render_pilot_report
from gapforge.pilots.status import build_acceptance_summary, classify_record
from gapforge.project_memory import ProjectMemoryManager


def test_pilot_runner_creates_project_and_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)

    record = PilotRunner(config).run("low_fpr_collusion")

    assert record.project_id
    assert record.campaign_id
    assert record.status == "refusal_ready"
    assert record.outcome_type == "correct_refusal"
    assert "project_record" in record.artifact_paths
    assert "campaign_record" in record.artifact_paths
    assert Path(record.artifact_paths["project_record"]).exists()
    assert Path(record.artifact_paths["campaign_record"]).exists()


def test_pilot_runner_records_refusal_outcome(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)

    record = PilotRunner(config).run("low_fpr_collusion")
    summary = build_acceptance_summary(record)

    assert record.outcome_type == "correct_refusal"
    assert any("research_refusal:" in blocker for blocker in record.blockers)
    assert summary.outcome_type == "correct_refusal"
    assert summary.refusal_reason
    assert summary.product_failures == []


def test_pilot_product_failure_outcome_recorded(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-low-fpr-product-failure",
        pilot_id="low_fpr_collusion",
        status="product_failure",
        outcome_type="product_failure",
        blockers=["product_failure: Codex output could not be validated/imported"],
        provenance=Provenance(created_by_skill="test"),
    )

    PilotStore(config).save_record(record)
    loaded = PilotStore(config).load_record(record.id)
    summary = build_acceptance_summary(loaded)

    assert loaded.status == "product_failure"
    assert loaded.outcome_type == "product_failure"
    assert summary.passed is False
    assert summary.product_failures == ["Codex output could not be validated/imported"]


def test_pilot_defensible_direction_outcome_recorded_from_fixture() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-low-fpr-direction-fixture",
        pilot_id=spec.id,
        status="running",
        outcome_type="unknown",
        artifact_paths={
            "evidence_backed_gap": "fixture/gap.json",
            "closest_prior_work": "fixture/closest_prior_work.json",
            "prior_work_recall_assessment": "fixture/prior_work_recall.md",
            "experiment_protocol": "fixture/experiment_protocol.md",
            "reviewer_panel": "fixture/review_panel.md",
            "human_review_acceptance": "fixture/human_review.json",
            "accepted_direction_id": "direction-low-fpr-monitoring",
        },
    )

    classified = classify_record(record, spec)
    classified.status = "accepted"
    summary = build_acceptance_summary(
        classified,
        reviews=[ExternalPilotReview(id="review-fixture", pilot_id=classified.id, accepted_outcome=True)],
    )

    assert classified.outcome_type == "defensible_direction"
    assert summary.passed is True
    assert summary.accepted_direction_id == "direction-low-fpr-monitoring"
    assert summary.release_gate_eligible is True


def test_pilot_report_renders(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunner(config).run(spec.name)
    summary = build_acceptance_summary(record)

    rendered = render_pilot_report(spec, record, summary)

    assert "# Pilot Report: low_fpr_collusion" in rendered
    assert f"- Pilot run: `{record.id}`" in rendered
    assert "- Outcome: `correct_refusal`" in rendered
    assert "## Blockers" in rendered


def test_pilot_status_command_loads_pilot_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunner(config).run("low_fpr_collusion")

    payload = json.loads(PilotStore(config).record_dir(record.id).joinpath("pilot_run_record.json").read_text(encoding="utf-8"))

    assert payload["id"] == record.id
    assert payload["outcome_type"] == "correct_refusal"


def test_pilot_outcome_defensible_fixture_classified_correctly() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-outcome-defensible",
        pilot_id=spec.id,
        status="accepted",
        outcome_type="defensible_direction",
        artifact_paths={
            "evidence_backed_gap": "fixture/gap.json",
            "related_work_matrix": "fixture/related_work.md",
            "novelty_dossiers": "fixture/novelty.md",
            "prior_work_recall_assessment": "fixture/recall.md",
            "experiment_protocol": "fixture/protocol.md",
            "reviewer_panel": "fixture/review.md",
            "human_review_acceptance": "fixture/human_review.json",
        },
    )

    assessment = assess_pilot_outcome(record, spec)

    assert assessment.outcome_type == "defensible_direction"
    assert assessment.recommended_next_version == "v0.9"
    assert assessment.blocking_issues == []


def test_pilot_outcome_refusal_fixture_classified_correctly() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-outcome-refusal",
        pilot_id=spec.id,
        status="accepted",
        outcome_type="correct_refusal",
        artifact_paths={
            "explicit_missing_searches_or_experiments": "fixture/refusal.md",
            "human_review_acceptance": "fixture/human_review.json",
        },
        blockers=[
            "research_refusal: source coverage insufficient for novelty claim",
            "research_refusal: missing experiment tractability evidence",
        ],
    )

    assessment = assess_pilot_outcome(record, spec)

    assert assessment.outcome_type == "correct_refusal"
    assert assessment.recommended_next_version == "v0.9"
    assert "source coverage insufficient for novelty claim" in assessment.blocking_issues


def test_pilot_outcome_product_failure_fixture_classified_correctly() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-outcome-product-failure",
        pilot_id=spec.id,
        status="product_failure",
        outcome_type="product_failure",
        blockers=["product_failure: release gate inconsistency accepted missing prior-work recall"],
    )

    assessment = assess_pilot_outcome(record, spec)

    assert assessment.outcome_type == "product_failure"
    assert assessment.recommended_next_version == "v0.9.1"
    assert assessment.required_fixes


def test_pilot_outcome_missing_review_is_incomplete() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-outcome-missing-review",
        pilot_id=spec.id,
        status="direction_ready",
        outcome_type="defensible_direction",
        artifact_paths={
            "evidence_backed_gap": "fixture/gap.json",
            "related_work_matrix": "fixture/related_work.md",
            "novelty_dossiers": "fixture/novelty.md",
            "prior_work_recall_assessment": "fixture/recall.md",
            "experiment_protocol": "fixture/protocol.md",
            "reviewer_panel": "fixture/review.md",
        },
    )

    assessment = assess_pilot_outcome(record, spec)

    assert assessment.outcome_type == "incomplete"
    assert assessment.recommended_next_version == "v0.9"
    assert "human review missing" in assessment.blocking_issues


def test_pilot_outcome_fake_citation_is_product_failure() -> None:
    spec = get_pilot_spec("low_fpr_collusion")
    record = PilotRunRecord(
        id="pilot-outcome-fake-citation",
        pilot_id=spec.id,
        status="accepted",
        outcome_type="defensible_direction",
        artifact_paths={
            "evidence_backed_gap": "fixture/gap.json",
            "related_work_matrix": "fixture/related_work.md",
            "novelty_dossiers": "fixture/novelty.md",
            "prior_work_recall_assessment": "fixture/recall.md",
            "experiment_protocol": "fixture/protocol.md",
            "reviewer_panel": "fixture/review.md",
            "human_review_acceptance": "fixture/human_review.json",
        },
        blockers=["product_failure: fake citation accepted by validation"],
    )

    assessment = assess_pilot_outcome(record, spec)

    assert assessment.outcome_type == "product_failure"
    assert assessment.recommended_next_version == "v0.9.1"
    assert assessment.required_fixes == ["Fix citation validation so fake citations cannot pass."]


def test_external_pilot_review_record_created(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-review-record",
        pilot_id="low_fpr_collusion",
        status="refusal_ready",
        outcome_type="correct_refusal",
        blockers=["research_refusal: missing experiment tractability evidence"],
    )
    store = PilotStore(config)
    store.save_record(record)

    review = ExternalPilotReviewManager(config).create_review(record.id, reviewer_name="Pilot Reviewer", reviewer_role="user")

    assert review.reviewer_name == "Pilot Reviewer"
    assert review.reviewer_role == "user"
    assert review.reviewed_at
    assert (store.record_dir(record.id) / "external_reviews" / f"{review.id}.json").exists()


def test_external_pilot_review_accepts_direction(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-review-direction",
        pilot_id="low_fpr_collusion",
        status="direction_ready",
        outcome_type="defensible_direction",
        artifact_paths={"accepted_direction_id": "direction-low-fpr-monitoring"},
    )
    store = PilotStore(config)
    store.save_record(record)

    review = ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="domain_expert")
    loaded = store.load_record(record.id)
    summary = store.load_acceptance(record.id)

    assert review.accepted_outcome is True
    assert loaded.status == "accepted"
    assert loaded.artifact_paths["human_review_acceptance"].endswith(f"{review.id}.json")
    assert summary.passed is True
    assert summary.human_review_status == "accepted"


def test_external_pilot_review_accepts_refusal(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-review-refusal",
        pilot_id="low_fpr_collusion",
        status="refusal_ready",
        outcome_type="correct_refusal",
        artifact_paths={"explicit_missing_searches_or_experiments": "fixture/refusal.md"},
        blockers=[
            "research_refusal: source coverage insufficient for novelty claim",
            "research_refusal: missing experiment tractability evidence",
        ],
    )
    store = PilotStore(config)
    store.save_record(record)

    review = ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="external_reviewer")
    loaded = store.load_record(record.id)
    summary = store.load_acceptance(record.id)

    assert review.accepted_outcome is True
    assert loaded.status == "accepted"
    assert summary.passed is True
    assert summary.outcome_type == "correct_refusal"


def test_external_pilot_review_rejects_product_failure(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-review-product-failure",
        pilot_id="low_fpr_collusion",
        status="product_failure",
        outcome_type="product_failure",
        blockers=["product_failure: fake result accepted by validation"],
    )
    store = PilotStore(config)
    store.save_record(record)

    review = ExternalPilotReviewManager(config).create_review(
        record.id,
        accept_outcome=True,
        reason="fake result accepted by validation",
    )
    loaded = store.load_record(record.id)
    summary = store.load_acceptance(record.id)

    assert review.accepted_outcome is False
    assert any("fake citation/result" in fix for fix in review.required_fixes)
    assert loaded.status == "product_failure"
    assert summary.passed is False
    assert summary.human_review_status == "rejected"


def test_pilot_acceptance_uses_external_review(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    record = PilotRunRecord(
        id="pilot-review-required",
        pilot_id="low_fpr_collusion",
        status="accepted",
        outcome_type="defensible_direction",
        artifact_paths={
            "human_review_acceptance": "fixture/self-certified-human-review.json",
            "accepted_direction_id": "direction-low-fpr-monitoring",
        },
    )
    store = PilotStore(config)
    store.save_record(record)

    summary_without_review = store.load_acceptance(record.id)
    ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="user")
    summary_with_review = store.load_acceptance(record.id)

    assert summary_without_review.passed is False
    assert summary_without_review.human_review_status == "missing"
    assert summary_with_review.passed is True
    assert summary_with_review.human_review_status == "accepted"


def test_idea_gate_multiple_candidates_selects_one(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = _idea_gate_project(config)
    _add_direction_fixture(program, "direction-strong", accepted=True)
    _add_direction_fixture(program, "direction-generic", title="Better framework", summary="A novel approach", accepted=True)
    ProjectMemoryManager(config).save_project(program)

    assessment = IdeaGate(config).assess_project(program.project.id, pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "accepted"
    assert assessment.selected_direction_id == "direction-strong"
    assert assessment.rejected_direction_ids == ["direction-generic"]


def test_idea_gate_generic_idea_rejected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = _idea_gate_project(config)
    _add_direction_fixture(program, "direction-generic", title="Better framework", summary="A novel approach", accepted=True)
    ProjectMemoryManager(config).save_project(program)

    assessment = IdeaGate(config).assess_project(program.project.id, pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "refusal"
    assert assessment.selected_direction_id == ""
    assert assessment.rejected_direction_ids == ["direction-generic"]
    assert any("generic idea" in blocker for blocker in assessment.blockers)


def test_idea_gate_no_candidate_creates_refusal(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = _idea_gate_project(config)
    ProjectMemoryManager(config).save_project(program)

    assessment = IdeaGate(config).assess_project(program.project.id, pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "refusal"
    assert assessment.candidate_direction_ids == []
    assert assessment.rejected_direction_ids == []
    assert assessment.blockers == ["No candidate research directions exist."]


def test_idea_gate_missing_experiment_rejected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = _idea_gate_project(config)
    _add_direction_fixture(program, "direction-no-experiment", accepted=True, include_protocol=False)
    ProjectMemoryManager(config).save_project(program)

    assessment = IdeaGate(config).assess_project(program.project.id, pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "refusal"
    assert any("missing measurable experiment" in blocker for blocker in assessment.blockers)


def test_idea_gate_accepted_direction_requires_human_review(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = _idea_gate_project(config)
    _add_direction_fixture(program, "direction-no-review", accepted=False)
    ProjectMemoryManager(config).save_project(program)

    assessment = IdeaGate(config).assess_project(program.project.id, pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "refusal"
    assert any("missing human review acceptance" in blocker for blocker in assessment.blockers)


def test_idea_gate_assessment_model_imported() -> None:
    assessment = IdeaGateAssessment(pilot_id="pilot-fixture")

    assert assessment.acceptance_status == "refusal"


def _idea_gate_project(config: GapForgeConfig):
    return ProjectMemoryManager(config).create_project("idea gate fixture")


def _add_direction_fixture(
    program,
    direction_id: str,
    *,
    title: str = "Low-FPR collusion monitor with calibrated negative controls",
    summary: str = "Detect covert coordination with calibrated false-positive controls and measurable baselines.",
    accepted: bool,
    include_protocol: bool = True,
) -> None:
    program.research_directions.append(
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title=title,
            summary=summary,
            linked_gap_ids=[f"gap-{direction_id}"],
            linked_novelty_dossier_ids=[f"novelty-{direction_id}"],
            supporting_paper_ids=[f"paper-{direction_id}"],
            maturity="experiment_ready",
            readiness_score=0.8,
        )
    )
    program.related_work_matrices.append(
        RelatedWorkMatrix(
            direction_id=direction_id,
            entries=[
                RelatedWorkEntry(
                    direction_id=direction_id,
                    paper_id=f"paper-prior-{direction_id}",
                    relationship="closest_prior_work",
                    relevance_score=0.9,
                )
            ],
            must_read_paper_ids=[f"paper-prior-{direction_id}"],
        )
    )
    if include_protocol:
        program.experiment_protocols.append(
            ExperimentProtocol(
                id=f"protocol-{direction_id}",
                direction_id=direction_id,
                linked_experiment_plan_id=f"experiment-{direction_id}",
                objective="Measure low false-positive collusion detection.",
                hypothesis="Calibrated monitor improves false-positive control over heuristic baseline.",
                datasets=["fixture-agent-dialogues"],
                metrics=["false positive rate", "recall"],
                evaluation_script_outline=["run detector", "compute false positive rate"],
            )
        )
    program.review_panels.append(ReviewPanel(experiment_or_direction_id=direction_id, decision_risk="medium"))
    if accepted:
        program.memory_records.append(
            ProjectMemoryRecord(
                id=f"memory-accept-{direction_id}",
                project_id=program.project.id,
                record_type="decision",
                text=f"accept direction {direction_id} for pilot continuation",
                linked_object_ids=[direction_id],
                status="accepted",
                confidence="high",
            )
        )
