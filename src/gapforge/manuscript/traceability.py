"""Claim-to-manuscript traceability audits."""

from __future__ import annotations

import json
import re

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.manuscript.models import (
    ManuscriptClaimUse,
    ManuscriptOverclaimWarning,
    ManuscriptSection,
    ManuscriptState,
    ManuscriptTraceabilityReport,
)
from gapforge.models import NoveltyDossier, PriorWorkRecallAssessment, Provenance, ResearchProgramState, ResearchRunState, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

WARNING_TYPES = {
    "unsupported",
    "overstrong_novelty",
    "result_without_artifact",
    "missing_citation",
    "hidden_limitation",
    "smoke_as_main_result",
}


class ManuscriptTraceabilityAuditor:
    """Audit manuscript claims against evidence/result/novelty trace links."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)

    def audit(self, manuscript_id: str) -> ManuscriptTraceabilityReport:
        state = self.manuscript_manager.load_state(manuscript_id)
        program = self.project_manager.load_project(state.manuscript.project_id)
        runs = _load_project_runs(self.state_manager, program)
        warnings: list[ManuscriptOverclaimWarning] = []
        unsupported_claims: list[str] = []
        supported_count = 0
        for claim_use in state.claim_uses:
            section = _section_for_claim(state, claim_use)
            claim_warnings = self._warnings_for_claim(state, claim_use, section, runs)
            warnings.extend(claim_warnings)
            if _claim_supported(claim_use, section, claim_warnings):
                supported_count += 1
            else:
                unsupported_claims.append(claim_use.claim_id)
        hidden_limitation = self._hidden_limitation_warning(state, program)
        if hidden_limitation is not None:
            warnings.append(hidden_limitation)
        blocking = _blocking_issues(state, warnings)
        report = ManuscriptTraceabilityReport(
            manuscript_id=manuscript_id,
            claim_count=len(state.claim_uses),
            supported_claim_count=supported_count,
            unsupported_claim_count=len(set(unsupported_claims)),
            empirical_claim_count=sum(1 for item in state.claim_uses if item.use_type == "result"),
            novelty_claim_count=sum(1 for item in state.claim_uses if item.use_type == "novelty"),
            limitation_claim_count=sum(1 for item in state.claim_uses if item.use_type == "limitation"),
            unsupported_claims=_unique(unsupported_claims),
            overclaim_warnings=warnings,
            blocking_issues=blocking,
            provenance=Provenance(
                created_by_skill="manuscript-traceability",
                source_ids=[manuscript_id, state.manuscript.project_id, *program.run_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Audited manuscript claim uses against trace links without mutating source evidence state.",
            ),
        )
        self._write_report(state, report)
        return report

    def overclaims_json(self, manuscript_id: str) -> str:
        report = self.audit(manuscript_id)
        return json.dumps(to_plain(report.overclaim_warnings), indent=2) + "\n"

    def soften_claims(self, manuscript_id: str, *, dry_run: bool = True) -> str:
        report = self.audit(manuscript_id)
        suggestions = [_softening_suggestion(warning) for warning in report.overclaim_warnings if warning.warning_type == "unsupported"]
        if not suggestions:
            return "No claim softening suggestions.\n"
        text = "# Manuscript Claim Softening Suggestions\n\n" + "\n".join(f"- {item}" for item in suggestions) + "\n"
        if not dry_run:
            state = self.manuscript_manager.load_state(manuscript_id)
            warning_claim_ids = {_claim_id_from_warning_text(warning.text) for warning in report.overclaim_warnings}
            for claim_use in state.claim_uses:
                if claim_use.claim_id in warning_claim_ids:
                    claim_use.requires_softening = True
            self.manuscript_manager._save_state(state)
        return text

    def render_markdown(self, report: ManuscriptTraceabilityReport) -> str:
        return render_traceability_markdown(report)

    def _warnings_for_claim(
        self,
        state: ManuscriptState,
        claim_use: ManuscriptClaimUse,
        section: ManuscriptSection,
        runs: list[ResearchRunState],
    ) -> list[ManuscriptOverclaimWarning]:
        warnings: list[ManuscriptOverclaimWarning] = []
        if _is_hypothesis_labeled(claim_use):
            return warnings
        if not _has_basic_trace(claim_use, section):
            warnings.append(
                _warning(
                    manuscript_id=state.manuscript.id,
                    section_id=section.id,
                    claim_id=claim_use.claim_id,
                    text=claim_use.claim_text,
                    warning_type="unsupported",
                    suggested_fix="Add evidence, citation, result/artifact links, or explicitly label this as a hypothesis/speculation.",
                    severity="blocking",
                )
            )
        if claim_use.use_type == "result":
            if not section.source_artifact_ids:
                warnings.append(
                    _warning(
                        manuscript_id=state.manuscript.id,
                        section_id=section.id,
                        claim_id=claim_use.claim_id,
                        text=claim_use.claim_text,
                        warning_type="result_without_artifact",
                        suggested_fix="Link the claim to an empirical result artifact or remove/soften the result language.",
                        severity="blocking",
                    )
                )
            if _is_sota_claim(claim_use.claim_text) and not _has_sota_support(section):
                warnings.append(
                    _warning(
                        manuscript_id=state.manuscript.id,
                        section_id=section.id,
                        claim_id=claim_use.claim_id,
                        text=claim_use.claim_text,
                        warning_type="result_without_artifact",
                        suggested_fix=(
                            "Do not make a SOTA claim unless benchmark comparison artifacts and a verified leaderboard record support it."
                        ),
                        severity="blocking",
                    )
                )
            if _smoke_or_pilot_overclaim(claim_use.claim_text, section):
                warnings.append(
                    _warning(
                        manuscript_id=state.manuscript.id,
                        section_id=section.id,
                        claim_id=claim_use.claim_id,
                        text=claim_use.claim_text,
                        warning_type="smoke_as_main_result",
                        suggested_fix="Phrase this as a smoke/pilot result or link main-run artifacts.",
                        severity="warning",
                    )
                )
        if claim_use.use_type == "novelty" and _is_strong_novelty_claim(claim_use.claim_text):
            if not _has_novelty_support(claim_use.claim_id, state.manuscript.direction_id, runs):
                warnings.append(
                    _warning(
                        manuscript_id=state.manuscript.id,
                        section_id=section.id,
                        claim_id=claim_use.claim_id,
                        text=claim_use.claim_text,
                        warning_type="overstrong_novelty",
                        suggested_fix="Link a novelty dossier and prior-work recall assessment, or soften the novelty claim.",
                        severity="blocking",
                    )
                )
        if claim_use.support_status in {"unsupported", "uncertain", ""} and not _is_hypothesis_labeled(claim_use):
            warnings.append(
                _warning(
                    manuscript_id=state.manuscript.id,
                    section_id=section.id,
                    claim_id=claim_use.claim_id,
                    text=claim_use.claim_text,
                    warning_type="unsupported",
                    suggested_fix="Soften the claim, add support, or mark it as hypothesis/speculation.",
                    severity="blocking",
                )
            )
        missing_non_result_citation = (
            not claim_use.citation_keys
            and not claim_use.evidence_locators
            and not section.source_paper_ids
            and claim_use.use_type not in {"result", "limitation"}
        )
        if missing_non_result_citation:
            warnings.append(
                _warning(
                    manuscript_id=state.manuscript.id,
                    section_id=section.id,
                    claim_id=claim_use.claim_id,
                    text=claim_use.claim_text,
                    warning_type="missing_citation",
                    suggested_fix="Add a citation key or evidence locator from a known paper record.",
                    severity="blocking",
                )
            )
        return _dedupe_warnings(warnings)

    def _hidden_limitation_warning(
        self,
        state: ManuscriptState,
        program: ResearchProgramState,
    ) -> ManuscriptOverclaimWarning | None:
        direction = next((item for item in program.research_directions if item.id == state.manuscript.direction_id), None)
        if direction is None or not direction.blocking_issues:
            return None
        has_limitation = any(item.use_type == "limitation" for item in state.claim_uses) or any(
            section.section_type == "limitations" for section in state.sections
        )
        if has_limitation:
            return None
        section_id = state.sections[0].id if state.sections else ""
        return _warning(
            manuscript_id=state.manuscript.id,
            section_id=section_id,
            claim_id=state.manuscript.direction_id,
            text="Known major blockers are not represented in manuscript limitations.",
            warning_type="hidden_limitation",
            suggested_fix="Add a limitations section or limitation claim that lists known major blockers.",
            severity="blocking",
        )

    def _write_report(self, state: ManuscriptState, report: ManuscriptTraceabilityReport) -> None:
        root = self.manuscript_manager.manuscript_root(state.manuscript.id)
        submission_dir = root / "submission"
        submission_dir.mkdir(parents=True, exist_ok=True)
        (submission_dir / "traceability_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (submission_dir / "traceability_report.md").write_text(render_traceability_markdown(report), encoding="utf-8")


def render_traceability_markdown(report: ManuscriptTraceabilityReport) -> str:
    lines = [
        f"# Manuscript Traceability `{report.manuscript_id}`",
        "",
        f"- Claim count: {report.claim_count}",
        f"- Supported claims: {report.supported_claim_count}",
        f"- Unsupported claims: {report.unsupported_claim_count}",
        f"- Empirical claims: {report.empirical_claim_count}",
        f"- Novelty claims: {report.novelty_claim_count}",
        f"- Limitation claims: {report.limitation_claim_count}",
        f"- Blocking issues: {len(report.blocking_issues)}",
        "",
    ]
    if report.blocking_issues:
        lines.extend(["## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in report.blocking_issues)
        lines.append("")
    if report.overclaim_warnings:
        lines.extend(["## Overclaim Warnings", ""])
        for warning in report.overclaim_warnings:
            lines.extend(
                [
                    f"- `{warning.warning_type}` ({warning.severity}) in `{warning.section_id}`: {warning.text}",
                    f"  Suggested fix: {warning.suggested_fix}",
                ]
            )
    else:
        lines.append("No overclaim warnings.")
    return "\n".join(lines).rstrip() + "\n"


def _section_for_claim(state: ManuscriptState, claim_use: ManuscriptClaimUse) -> ManuscriptSection:
    for section in state.sections:
        if section.id == claim_use.section_id:
            return section
    return ManuscriptSection(
        id=claim_use.section_id,
        manuscript_id=state.manuscript.id,
        section_type="appendix",
        title="Unknown Section",
        content_path="",
    )


def _claim_supported(
    claim_use: ManuscriptClaimUse,
    section: ManuscriptSection,
    warnings: list[ManuscriptOverclaimWarning],
) -> bool:
    if any(warning.severity == "blocking" for warning in warnings):
        return False
    if _is_hypothesis_labeled(claim_use):
        return True
    if claim_use.use_type == "result":
        return bool(section.source_artifact_ids)
    if claim_use.use_type == "limitation":
        return True
    return claim_use.support_status == "supported" and _has_basic_trace(claim_use, section)


def _has_basic_trace(claim_use: ManuscriptClaimUse, section: ManuscriptSection) -> bool:
    return bool(
        claim_use.evidence_locators
        or claim_use.citation_keys
        or section.source_paper_ids
        or section.source_result_ids
        or section.source_artifact_ids
        or claim_use.use_type == "limitation"
    )


def _is_hypothesis_labeled(claim_use: ManuscriptClaimUse) -> bool:
    text = claim_use.claim_text.lower()
    return (
        claim_use.use_type == "future_work"
        or claim_use.support_status in {"hypothesis", "speculation"}
        or "hypothes" in text
        or "speculat" in text
    )


def _is_strong_novelty_claim(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ["first", "novel", "new contribution", "unprecedented"])


def _is_sota_claim(text: str) -> bool:
    lowered = text.lower()
    return "sota" in lowered or "state-of-the-art" in lowered or "state of the art" in lowered or "leaderboard" in lowered


def _has_sota_support(section: ManuscriptSection) -> bool:
    artifacts = " ".join(section.source_artifact_ids).lower()
    has_benchmark_comparison = "benchmark-comparison" in artifacts or "benchmark_comparison" in artifacts
    return bool(section.source_result_ids) and "leaderboard" in artifacts and has_benchmark_comparison


def _smoke_or_pilot_overclaim(text: str, section: ManuscriptSection) -> bool:
    ids = " ".join([*section.source_result_ids, *section.source_artifact_ids]).lower()
    if "smoke" not in ids and "pilot" not in ids:
        return False
    lowered = text.lower()
    if "smoke" in lowered or "pilot" in lowered:
        return False
    return "main result" in lowered or "final result" in lowered or "shows" in lowered or "works" in lowered


def _has_novelty_support(claim_id: str, direction_id: str, runs: list[ResearchRunState]) -> bool:
    target_ids = {claim_id, direction_id}
    dossiers: list[NoveltyDossier] = []
    recall: list[PriorWorkRecallAssessment] = []
    for run in runs:
        dossiers.extend(item for item in run.novelty_dossiers if item.target_id in target_ids)
        recall.extend(item for item in run.prior_work_recall_assessments if item.target_id in target_ids)
    has_dossier = any(item.top_prior_work or item.candidates_considered or item.comparison_table for item in dossiers)
    has_recall = any(item.novelty_allowed and not item.missing_required_searches and not item.blocking_issues for item in recall)
    return has_dossier and has_recall


def _blocking_issues(state: ManuscriptState, warnings: list[ManuscriptOverclaimWarning]) -> list[str]:
    issues = [f"{warning.warning_type}: {warning.suggested_fix}" for warning in warnings if warning.severity == "blocking"]
    if state.manuscript.status == "submission_ready" and issues:
        issues.append("Manuscript is marked submission_ready while traceability blockers remain.")
    return _unique(issues)


def _warning(
    *,
    manuscript_id: str,
    section_id: str,
    claim_id: str,
    text: str,
    warning_type: str,
    suggested_fix: str,
    severity: str,
) -> ManuscriptOverclaimWarning:
    if warning_type not in WARNING_TYPES:
        raise ValueError(f"Unsupported overclaim warning type: {warning_type}")
    now = utc_now_iso()
    return ManuscriptOverclaimWarning(
        id=f"overclaim-{warning_type}-{_slug(claim_id)}",
        manuscript_id=manuscript_id,
        section_id=section_id,
        text=f"{claim_id}: {text}",
        warning_type=warning_type,
        suggested_fix=suggested_fix,
        severity=severity,
        provenance=Provenance(
            created_by_skill="manuscript-traceability",
            source_ids=[manuscript_id, section_id, claim_id],
            timestamp=now,
            reasoning_summary="Flagged a manuscript claim whose wording or support links need correction.",
        ),
    )


def _dedupe_warnings(warnings: list[ManuscriptOverclaimWarning]) -> list[ManuscriptOverclaimWarning]:
    result: list[ManuscriptOverclaimWarning] = []
    seen: set[tuple[str, str, str]] = set()
    for warning in warnings:
        key = (warning.warning_type, warning.text, warning.suggested_fix)
        if key not in seen:
            result.append(warning)
            seen.add(key)
    return result


def _softening_suggestion(warning: ManuscriptOverclaimWarning) -> str:
    return f"Soften `{_claim_id_from_warning_text(warning.text)}` or mark it as a hypothesis/speculation. {warning.suggested_fix}"


def _claim_id_from_warning_text(text: str) -> str:
    return text.split(":", 1)[0].strip()


def _load_project_runs(state_manager: ResearchStateManager, program: ResearchProgramState) -> list[ResearchRunState]:
    runs: list[ResearchRunState] = []
    for run_id in program.run_ids or program.project.run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return runs


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "claim"
