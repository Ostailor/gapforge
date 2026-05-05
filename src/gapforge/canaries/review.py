"""Human review harness for v0.3 Codex/GPT-5.4 canary runs."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.canaries.runner import CanaryRunManager
from gapforge.config import GapForgeConfig
from gapforge.models import CanaryAcceptanceSummary, CanaryHumanReview, CanaryRunRecord, Provenance, from_dict, to_plain
from gapforge.state import utc_now_compact, utc_now_iso


class CanaryReviewManager:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.run_manager = CanaryRunManager(config)

    def render_form(self, canary_id: str) -> str:
        record = self.run_manager.load_record(canary_id)
        return render_review_form(record)

    def review(
        self,
        canary_id: str,
        *,
        reviewer: str = "human",
        accept: bool = False,
        reject: bool = False,
        reason: str = "",
        notes: str = "",
        source_coverage_score: int = 0,
        full_text_grounding_score: int = 0,
        citation_grounding_score: int = 0,
        novelty_honesty_score: int = 0,
        gap_quality_score: int = 0,
        experiment_quality_score: int = 0,
        uncertainty_visibility_score: int = 0,
        fake_citation_found: bool = False,
        unsupported_high_confidence_claim_found: bool = False,
        obvious_prior_work_missed: bool = False,
        strict_report_behaved_correctly: bool = True,
    ) -> tuple[CanaryHumanReview, CanaryAcceptanceSummary]:
        if accept and reject:
            raise ValueError("Use either --accept or --reject, not both.")
        record = self.run_manager.load_record(canary_id)
        reasons = [reason] if reason else []
        required_fixes: list[str] = []
        if fake_citation_found:
            required_fixes.append("Remove or convert fake citations into search requests.")
        if unsupported_high_confidence_claim_found:
            required_fixes.append("Downgrade or support high-confidence claims with evidence.")
        if not strict_report_behaved_correctly:
            required_fixes.append("Fix strict report gating so it does not overclaim novelty or readiness.")
        if obvious_prior_work_missed:
            required_fixes.append("Expand closest-prior-work search and update novelty dossiers.")
        accepted = bool(accept and not required_fixes)
        if reject:
            accepted = False
        review = CanaryHumanReview(
            id=f"canary-review-{utc_now_compact()}-{canary_id}",
            canary_run_id=canary_id,
            reviewer=reviewer,
            reviewed_at=utc_now_iso(),
            source_coverage_score=source_coverage_score,
            full_text_grounding_score=full_text_grounding_score,
            citation_grounding_score=citation_grounding_score,
            novelty_honesty_score=novelty_honesty_score,
            gap_quality_score=gap_quality_score,
            experiment_quality_score=experiment_quality_score,
            uncertainty_visibility_score=uncertainty_visibility_score,
            fake_citation_found=fake_citation_found,
            unsupported_high_confidence_claim_found=unsupported_high_confidence_claim_found,
            obvious_prior_work_missed=obvious_prior_work_missed,
            strict_report_behaved_correctly=strict_report_behaved_correctly,
            accepted=accepted,
            reasons=reasons,
            required_fixes=required_fixes,
            notes=notes,
            provenance=Provenance(
                created_by_skill="canary-human-review",
                source_ids=[canary_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Human reviewed canary output using structured v0.3 acceptance criteria.",
            ),
        )
        summary = build_acceptance_summary(record, review, self.run_manager.artifact_paths(canary_id))
        self._save_review(record, review, summary)
        self._update_record_status(record, review, summary)
        return review, summary

    def summary(self, canary_id: str) -> CanaryAcceptanceSummary:
        path = self._record_dir(canary_id) / "acceptance_summary.json"
        if not path.exists():
            record = self.run_manager.load_record(canary_id)
            return build_acceptance_summary(record, None, self.run_manager.artifact_paths(canary_id))
        return from_dict(CanaryAcceptanceSummary, json.loads(path.read_text(encoding="utf-8")))

    def real_run_acceptance(self) -> dict[str, object]:
        summaries = []
        if self.run_manager.root.exists():
            for record_dir in sorted(self.run_manager.root.iterdir()):
                if record_dir.is_dir() and (record_dir / "record.json").exists():
                    try:
                        summaries.append(self.summary(record_dir.name))
                    except FileNotFoundError:
                        continue
        accepted = [summary for summary in summaries if summary.passed and summary.release_gate_status == "accepted"]
        real_accepted = []
        for summary in accepted:
            record = self.run_manager.load_record(summary.canary_run_id)
            if record.validation_summary.get("counts_as_actual_run") is not False:
                real_accepted.append(summary)
        return {
            "passed": bool(real_accepted),
            "accepted_canaries": [summary.canary_run_id for summary in real_accepted],
            "reviewed_canaries": [summary.canary_run_id for summary in summaries],
            "missing": [] if real_accepted else ["No human-reviewed actual Codex/GPT-5.4 canary has been accepted."],
        }

    def _save_review(
        self,
        record: CanaryRunRecord,
        review: CanaryHumanReview,
        summary: CanaryAcceptanceSummary,
    ) -> None:
        record_dir = self._record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        (record_dir / "human_review.json").write_text(json.dumps(to_plain(review), indent=2) + "\n", encoding="utf-8")
        (record_dir / "acceptance_summary.json").write_text(json.dumps(to_plain(summary), indent=2) + "\n", encoding="utf-8")
        (record_dir / "review_report.md").write_text(render_review_report(review, summary), encoding="utf-8")

    def _update_record_status(
        self,
        record: CanaryRunRecord,
        review: CanaryHumanReview,
        summary: CanaryAcceptanceSummary,
    ) -> None:
        record.status = "accepted" if summary.passed else "rejected"
        record.human_review_id = review.id
        record.validation_summary["human_review_accepted"] = review.accepted
        record.validation_summary["release_gate_status"] = summary.release_gate_status
        record.completed_at = utc_now_iso()
        self.run_manager.save_record(record)

    def _record_dir(self, canary_id: str) -> Path:
        return self.run_manager.root / canary_id


def render_review_form(record: CanaryRunRecord) -> str:
    lines = [
        f"# Canary Human Review: {record.id}",
        "",
        "Use this checklist for Level 5 human-reviewed acceptance. Do not accept a canary with fake citations, unsupported "
        "high-confidence claims, or strict-report overclaiming.",
        "",
        "## Checklist",
        "",
        "- [ ] Did it find real sources?",
        "- [ ] Did source coverage meet the source policy?",
        "- [ ] Did it distinguish abstract-only versus full-text evidence?",
        "- [ ] Did every high-confidence claim have evidence?",
        "- [ ] Did it invent citations?",
        "- [ ] Did novelty dossier include closest prior work?",
        "- [ ] Did it miss obvious prior work?",
        "- [ ] Did it reject or downgrade weak ideas?",
        "- [ ] Did strict mode refuse recommendations when coverage was weak?",
        "- [ ] Was the top gap meaningful?",
        "- [ ] Was the experiment concrete?",
        "- [ ] Were reviewer objections serious?",
        "- [ ] Did the report visibly state uncertainty?",
        "",
        "## CLI",
        "",
        f'```bash\ngapforge canary-review --canary-id {record.id} --reviewer "name" --accept\n```',
        f'```bash\ngapforge canary-review --canary-id {record.id} --reject --reason "blocking issue"\n```',
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_acceptance_summary(
    record: CanaryRunRecord,
    review: CanaryHumanReview | None,
    artifact_paths: list[str],
) -> CanaryAcceptanceSummary:
    blocking: list[str] = []
    scores = {}
    accepted_artifacts: list[str] = []
    rejected_artifacts: list[str] = []
    if review is None:
        blocking.append("Human review is missing.")
    else:
        scores = {
            "source_coverage": review.source_coverage_score,
            "full_text_grounding": review.full_text_grounding_score,
            "citation_grounding": review.citation_grounding_score,
            "novelty_honesty": review.novelty_honesty_score,
            "gap_quality": review.gap_quality_score,
            "experiment_quality": review.experiment_quality_score,
            "uncertainty_visibility": review.uncertainty_visibility_score,
        }
        if review.fake_citation_found:
            blocking.append("Fake citation found.")
        if review.unsupported_high_confidence_claim_found:
            blocking.append("Unsupported high-confidence claim found.")
        if review.obvious_prior_work_missed:
            blocking.append("Obvious prior work missed.")
        if not review.strict_report_behaved_correctly:
            blocking.append("Strict report overclaimed novelty or readiness.")
        if not review.accepted:
            blocking.append("Human reviewer did not accept the canary.")
        accepted_artifacts = artifact_paths if not blocking else []
        rejected_artifacts = [] if not blocking else artifact_paths
    passed = not blocking and review is not None and review.accepted
    return CanaryAcceptanceSummary(
        canary_run_id=record.id,
        passed=passed,
        blocking_failures=blocking,
        scores=scores,
        accepted_artifacts=accepted_artifacts,
        rejected_artifacts=rejected_artifacts,
        release_gate_status="accepted" if passed else "not_passed",
        provenance=Provenance(
            created_by_skill="canary-acceptance",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Built canary acceptance summary from structured human review.",
        ),
    )


def render_review_report(review: CanaryHumanReview, summary: CanaryAcceptanceSummary) -> str:
    lines = [
        f"# Canary Review Report: {review.canary_run_id}",
        "",
        f"- Reviewer: {review.reviewer}",
        f"- Reviewed at: {review.reviewed_at}",
        f"- Accepted by reviewer: {str(review.accepted).lower()}",
        f"- Release gate status: {summary.release_gate_status}",
        "",
        "## Scores",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in summary.scores.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend(f"- {item}" for item in summary.blocking_failures or ["none"])
    lines.extend(["", "## Required Fixes", ""])
    lines.extend(f"- {item}" for item in review.required_fixes or ["none"])
    lines.extend(["", "## Reasons", ""])
    lines.extend(f"- {item}" for item in review.reasons or ["none"])
    if review.notes:
        lines.extend(["", "## Notes", "", review.notes])
    return "\n".join(lines).rstrip() + "\n"
