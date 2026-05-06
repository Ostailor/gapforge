"""Acceptance rules for v0.5 live-literature campaign profiles."""

from __future__ import annotations

from gapforge.models import LiveSourceDiagnostic, RealLiteratureCampaignProfile, RealLiteratureCampaignRecord, ResearchRunState
from gapforge.sources.health import source_name_key


def evaluate_real_literature_record(
    profile: RealLiteratureCampaignProfile,
    diagnostic: LiveSourceDiagnostic,
    record: RealLiteratureCampaignRecord,
    *,
    runs: list[ResearchRunState] | None = None,
) -> RealLiteratureCampaignRecord:
    """Apply fail-closed live-literature campaign quality gates."""

    summarized = summarize_run_quality(runs or [])
    if runs:
        record.real_paper_count = summarized["real_paper_count"]
        record.fallback_paper_count = summarized["fallback_paper_count"]
        record.full_text_count = summarized["full_text_count"]
        record.abstract_only_count = summarized["abstract_only_count"]
        record.novelty_dossier_count = summarized["novelty_dossier_count"]

    blockers = _acceptance_blockers(profile, diagnostic, record)
    is_undercovered_refusal = profile.id == "live_undercovered_refusal"
    fallback_heavy = record.fallback_paper_count > record.real_paper_count
    if is_undercovered_refusal and _has_live_checks(diagnostic) and diagnostic.blocking_issues and not fallback_heavy:
        record.accepted = True
        record.rejection_reason = ""
        return record

    record.accepted = not blockers
    record.rejection_reason = "; ".join(blockers)
    return record


def summarize_run_quality(runs: list[ResearchRunState]) -> dict[str, int]:
    real_paper_ids: set[str] = set()
    fallback_paper_ids: set[str] = set()
    full_text_paper_ids: set[str] = set()
    abstract_note_paper_ids: set[str] = set()
    novelty_dossier_count = 0
    for state in runs:
        for paper in state.papers:
            if _is_fallback_paper(paper.raw_metadata, paper.provenance.reasoning_summary):
                fallback_paper_ids.add(paper.id)
            else:
                real_paper_ids.add(paper.id)
        full_text_paper_ids.update(section.paper_id for section in state.paper_sections)
        abstract_note_paper_ids.update(
            note.paper_id
            for note in state.paper_notes
            if "abstract" in note.source_basis.lower() and "full text" not in note.source_basis.lower()
        )
        novelty_dossier_count += len(state.novelty_dossiers)
    return {
        "real_paper_count": len(real_paper_ids),
        "fallback_paper_count": len(fallback_paper_ids),
        "full_text_count": len(full_text_paper_ids),
        "abstract_only_count": len(abstract_note_paper_ids - full_text_paper_ids),
        "novelty_dossier_count": novelty_dossier_count,
    }


def _acceptance_blockers(
    profile: RealLiteratureCampaignProfile,
    diagnostic: LiveSourceDiagnostic,
    record: RealLiteratureCampaignRecord,
) -> list[str]:
    blockers: list[str] = []
    if not _has_live_checks(diagnostic):
        blockers.append("Live source diagnostics did not run against enabled sources.")
    if not diagnostic.minimum_coverage_met:
        blockers.append("Source coverage minimum was not met.")
    missing_required = _missing_required_live_sources(profile, diagnostic)
    if missing_required:
        blockers.append(f"Required live sources are not healthy: {', '.join(missing_required)}.")
    if record.fallback_paper_count > record.real_paper_count:
        blockers.append("Most retrieved papers are fallback artifacts.")
    if record.real_paper_count < profile.min_real_papers:
        blockers.append(f"Only {record.real_paper_count} real papers found; profile requires {profile.min_real_papers}.")
    note_count = record.full_text_count + record.abstract_only_count
    if note_count < profile.min_full_text_or_abstract_notes:
        blockers.append(
            f"Only {note_count} full-text or abstract notes available; profile requires {profile.min_full_text_or_abstract_notes}."
        )
    if record.novelty_dossier_count < profile.min_closest_prior_work:
        blockers.append(
            f"Only {record.novelty_dossier_count} novelty dossier(s) available; profile requires {profile.min_closest_prior_work}."
        )
    return blockers


def _missing_required_live_sources(profile: RealLiteratureCampaignProfile, diagnostic: LiveSourceDiagnostic) -> list[str]:
    healthy = {source_name_key(name) for name in diagnostic.usable_sources}
    return [source for source in profile.required_live_sources if source_name_key(source) not in healthy]


def _has_live_checks(diagnostic: LiveSourceDiagnostic) -> bool:
    return any(check.status != "disabled" and "No GapForge connector" not in check.error for check in diagnostic.source_health_checks)


def _is_fallback_paper(raw_metadata: dict[str, object], provenance_summary: str) -> bool:
    return bool(raw_metadata.get("fallback")) or "fallback" in provenance_summary.lower()
